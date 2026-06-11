"""Read-only analysis over captured traffic.

Everything here operates purely on the TrafficDB — no proxy, no network. It is
split out of MitmController so the controller stays focused on running the proxy
and the active-testing paths (replay / fuzz), while these endpoint-clustering,
diffing, auth-detection and reporting helpers live on their own seam and are
trivially unit-testable with just a DB.
"""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs
from collections import Counter

from .traffic_db import TrafficDB


# ── Cross-flow data-flow correlation ───────────────────────────────────────
# High-signal token shapes that are worth tracking as they pass from one flow's
# RESPONSE (where a value is minted) into a later flow's REQUEST (where it is
# replayed). Ordered specific→generic; the generic base64url/​hex catch-alls
# have high length floors and are tamed by the frequency caps in
# correlate_dataflow (a value minted or consumed everywhere is low-signal).
_TOKEN_RE = re.compile(
    r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}"          # JWT
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"  # UUID
    r"|AK[A-Z]{2}[0-9A-Za-z]{12,40}"                                        # cloud AK (AKIA/AKID/AKLT)
    r"|LTAI[0-9A-Za-z]{12,30}"                                              # Aliyun AK
    r"|[0-9a-f]{32,64}"                                                     # long hex (sig/md5/sha)
    # Opaque token (oauth code/state, pskey). Bounded by non-token chars on
    # both sides so we lift a whole value, not a 28-char slice out of a longer
    # base64/HTML blob; floor raised to 28 to cut generic false positives.
    r"|(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{28,128}(?![A-Za-z0-9_-])"
)

# A token is "secret-shaped" (worth a cross-identity-reuse finding) if it looks
# like a credential/signature rather than a generic opaque id.
_SECRET_TOKEN_RE = re.compile(
    r"^(?:eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}"
    r"|AK[A-Z]{2}[0-9A-Za-z]{12,40}"
    r"|LTAI[0-9A-Za-z]{12,30}"
    r"|[0-9a-f]{32,64})$"
)


def _extract_tokens(text: str, cap: int = 400) -> set:
    """Pull up to `cap` distinct high-signal tokens out of an arbitrary blob."""
    if not text:
        return set()
    out = set()
    for m in _TOKEN_RE.finditer(text):
        out.add(m.group(0))
        if len(out) >= cap:
            break
    return out



class TrafficAnalyzer:
    # Cap full-body analysis loads so a long capture session can't pull the
    # entire flow table (with bodies) into memory in one shot.
    MAX_ANALYSIS_FLOWS = 2000

    def __init__(self, db: TrafficDB):
        self.db = db

    def detect_auth_patterns(self, flow_ids: Optional[List[str]] = None) -> Dict:
        if flow_ids:
            flows = self.db.get_by_ids(flow_ids)
        else:
            flows = self.db.get_all_for_analysis(limit=self.MAX_ANALYSIS_FLOWS)

        auth_signals = {
            "oauth2": {"detected": False, "signals": [], "flows": []},
            "jwt": {"detected": False, "signals": [], "flows": []},
            "api_key": {"detected": False, "signals": [], "flows": []},
            "session_cookie": {"detected": False, "signals": [], "flows": []},
            "csrf": {"detected": False, "signals": [], "flows": []},
            "basic_auth": {"detected": False, "signals": [], "flows": []},
            "bearer_token": {"detected": False, "signals": [], "flows": []},
        }

        for f in flows:
            headers = f.get("request", {}).get("headers", {})
            if isinstance(headers, list):
                headers = {k: v for k, v in headers}

            path = urlparse(f.get("request", {}).get("url", "")).path.lower()
            auth_header = headers.get("Authorization", headers.get("authorization", ""))

            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                auth_signals["bearer_token"]["detected"] = True
                auth_signals["bearer_token"]["flows"].append(f["id"])
                if token.count(".") == 2:
                    auth_signals["jwt"]["detected"] = True
                    auth_signals["jwt"]["signals"].append("Bearer token appears to be JWT format")
                    auth_signals["jwt"]["flows"].append(f["id"])

            if auth_header.startswith("Basic "):
                auth_signals["basic_auth"]["detected"] = True
                auth_signals["basic_auth"]["flows"].append(f["id"])

            for h, v in headers.items():
                h_lower = h.lower()
                if any(k in h_lower for k in ["x-api-key", "api-key", "apikey", "x-auth-token"]):
                    auth_signals["api_key"]["detected"] = True
                    auth_signals["api_key"]["signals"].append(f"Header: {h}")
                    auth_signals["api_key"]["flows"].append(f["id"])

            if any(p in path for p in ["/oauth", "/token", "/authorize", "/auth/callback"]):
                auth_signals["oauth2"]["detected"] = True
                auth_signals["oauth2"]["signals"].append(f"OAuth endpoint: {path}")
                auth_signals["oauth2"]["flows"].append(f["id"])

            cookie_header = headers.get("Cookie", headers.get("cookie", ""))
            if cookie_header:
                for cookie in cookie_header.split(";"):
                    c_name = cookie.strip().split("=")[0].lower() if "=" in cookie else ""
                    if any(s in c_name for s in ["session", "sid", "sess", "auth"]):
                        auth_signals["session_cookie"]["detected"] = True
                        auth_signals["session_cookie"]["signals"].append(f"Session cookie: {c_name}")
                        auth_signals["session_cookie"]["flows"].append(f["id"])

            for h in headers:
                h_lower = h.lower()
                if any(c in h_lower for c in ["csrf", "xsrf", "x-csrf", "x-xsrf"]):
                    auth_signals["csrf"]["detected"] = True
                    auth_signals["csrf"]["signals"].append(f"CSRF header: {h}")
                    auth_signals["csrf"]["flows"].append(f["id"])

        for key in auth_signals:
            auth_signals[key]["flows"] = list(set(auth_signals[key]["flows"]))[:5]
            auth_signals[key]["signals"] = list(set(auth_signals[key]["signals"]))

        detected = [k for k, v in auth_signals.items() if v["detected"]]
        return {"detected_auth_types": detected, "details": auth_signals}

    def extract_from_flow(self, flow_id: str, json_path: Optional[str] = None, css_selector: Optional[str] = None) -> str:
        from jsonpath_ng import parse as parse_jsonpath
        from bs4 import BeautifulSoup

        flow_data = self.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
        if not flow_data:
            return "Flow not found"

        response = flow_data.get("response")
        body_content = response.get("body") if response else None
        if not body_content:
            return "Flow has no response body"

        if json_path:
            try:
                data = json.loads(body_content)
                jsonpath_expr = parse_jsonpath(json_path)
                matches = [match.value for match in jsonpath_expr.find(data)]
                return json.dumps(matches, indent=2)
            except json.JSONDecodeError:
                return "Response body is not valid JSON"
            except Exception as e:
                return f"JSONPath error: {str(e)}"

        if css_selector:
            try:
                soup = BeautifulSoup(body_content, "html.parser")
                elements = soup.select(css_selector)
                result = [{"text": el.get_text(strip=True), "html": str(el), "attrs": el.attrs} for el in elements]
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"CSS selector error: {str(e)}"

        return "Must provide json_path or css_selector"

    def get_api_patterns(self, domain: Optional[str] = None, limit: Optional[int] = None) -> str:
        flows = self.db.get_all_for_analysis(lightweight=True)
        if domain:
            flows = [f for f in flows if domain in f["request"]["url"]]
        if limit is not None:
            flows = flows[:limit]

        endpoint_clusters: Dict[str, Dict[str, Any]] = {}
        for f in flows:
            parsed = urlparse(f["request"]["url"])
            normalized_path, path_params = self._normalize_path(parsed.path)
            method = f["request"]["method"]
            key = f"{method} {normalized_path}"

            if key not in endpoint_clusters:
                endpoint_clusters[key] = {
                    "method": method,
                    "path_pattern": normalized_path,
                    "path_params": path_params,
                    "query_params": set(),
                    "status_codes": Counter(),
                    "content_types": Counter(),
                    "count": 0,
                    "sample_flow_ids": [],
                }

            cluster = endpoint_clusters[key]
            cluster["count"] += 1
            cluster["sample_flow_ids"].append(f["id"])

            for param in parse_qs(parsed.query).keys():
                cluster["query_params"].add(param)

            if f["response"]:
                ct_key = self._detect_content_type(f["response"].get("headers", {}))
                cluster["status_codes"][f["response"].get("status_code", 0)] += 1
                cluster["content_types"][ct_key] += 1

        result = []
        for key, cluster in sorted(endpoint_clusters.items(), key=lambda x: -x[1]["count"]):
            result.append({
                "endpoint": key,
                "method": cluster["method"],
                "path_pattern": cluster["path_pattern"],
                "path_params": cluster["path_params"],
                "query_params": list(cluster["query_params"]),
                "status_codes": dict(cluster["status_codes"]),
                "content_types": dict(cluster["content_types"]),
                "request_count": cluster["count"],
                "sample_flow_ids": cluster["sample_flow_ids"][:3],
            })

        return json.dumps(result, indent=2)

    def export_openapi_spec(self, domain: Optional[str] = None, limit: Optional[int] = None) -> str:
        clusters = json.loads(self.get_api_patterns(domain, limit))
        spec = {
            "openapi": "3.0.0",
            "info": {"title": f"Reconstructed API - {domain if domain else 'All'}", "version": "1.0.0"},
            "paths": {},
        }
        for cluster in clusters:
            path = cluster["path_pattern"]
            if not path.startswith("/"):
                path = "/" + path
            method = cluster["method"].lower()
            spec["paths"].setdefault(path, {})

            operation = {"summary": f"{method.upper()} {path}", "parameters": [], "responses": {}}
            for param in cluster["path_params"]:
                operation["parameters"].append({"name": param, "in": "path", "required": True, "schema": {"type": "string"}})
            for param in cluster["query_params"]:
                operation["parameters"].append({"name": param, "in": "query", "schema": {"type": "string"}})
            for status_code in cluster["status_codes"]:
                content_types = cluster["content_types"]
                resp_obj = {"description": f"Response with status {status_code}"}
                if content_types:
                    resp_obj["content"] = {}
                    for ct in content_types:
                        media_type = "application/json" if ct == "json" else "text/plain"
                        resp_obj["content"][media_type] = {"schema": {"type": "object"}}
                operation["responses"][str(status_code)] = resp_obj
            spec["paths"][path][method] = operation

        return json.dumps(spec, indent=2)

    @staticmethod
    def _normalize_path(path: str):
        segments = path.split("/")
        normalized, params = [], []
        for seg in segments:
            if not seg:
                normalized.append("")
                continue
            if re.match(r"^\d+$", seg):
                normalized.append("{id}"); params.append("id")
            elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", seg, re.I):
                normalized.append("{uuid}"); params.append("uuid")
            elif re.match(r"^[0-9a-f]{24}$", seg, re.I):
                normalized.append("{objectId}"); params.append("objectId")
            elif len(seg) > 20 and re.match(r"^[a-zA-Z0-9_-]+$", seg):
                normalized.append("{token}"); params.append("token")
            else:
                normalized.append(seg)
        return "/".join(normalized), params

    @staticmethod
    def _detect_content_type(headers: Dict[str, Any]) -> str:
        ct = headers.get("content-type", headers.get("Content-Type", ""))
        if "json" in ct.lower():
            return "json"
        elif "form" in ct.lower():
            return "form"
        elif "xml" in ct.lower():
            return "xml"
        return "unknown"

    def _scraper_steps(self, flows_data, framework):
        """Yield code lines for each flow's request reconstruction (shared by
        both frameworks)."""
        for i, flow in enumerate(flows_data):
            req = flow["request"]
            url, method = req["url"], req["method"]
            headers = dict(req["headers"])
            for h in ("Host", "Content-Length", "Content-Encoding"):
                headers.pop(h, None)
            body = req.get("body")
            flow_obj = self.db.get_flow_object(flow["id"])
            if flow_obj and flow_obj.body:
                body = flow_obj.body
            yield from self._emit_step(i, method, url, headers, body, framework)

    @staticmethod
    def _emit_step(i, method, url, headers, body, framework):
        lines = [
            f"        # Step {i + 1}: {method} {url[:60]}",
            f"        headers_{i} = {json.dumps(headers, indent=12).strip()}",
        ]
        if framework == "playwright":
            kwargs = f"{json.dumps(url)}, method={json.dumps(method)}, headers=headers_{i}"
            call, status = f"context.request.fetch({{kw}})", "status"
        else:
            kwargs = f"method={json.dumps(method)}, url={json.dumps(url)}, headers=headers_{i}"
            call, status = f"client.request({{kw}})", "status_code"
        if body and body != "<binary data omitted>":
            lines.append(f"        data_{i} = {json.dumps(body)}")
            kwargs += f", data=data_{i}"
        lines += [
            "        try:",
            f"            response_{i} = await {call.format(kw=kwargs)}",
            f"            print(f'Status: {{response_{i}.{status}}}')",
            "        except Exception as e:",
            "            print(f'Error: {e}')",
            "",
        ]
        return lines

    def generate_scraper_code(self, flow_ids: List[str], target_framework: str = "curl_cffi") -> str:
        if target_framework not in ("curl_cffi", "playwright"):
            return f"Framework '{target_framework}' not supported. Use 'curl_cffi' or 'playwright'"
        flows_data = [d for fid in flow_ids
                      if (d := self.db.get_detail(fid, level="full", body_preview_length=256 * 1024))]
        if not flows_data:
            return "No valid flows found"

        if target_framework == "curl_cffi":
            code = ["import asyncio", "import json",
                    "from curl_cffi.requests import AsyncSession", "",
                    "async def run_scraper():",
                    "    async with AsyncSession(impersonate='chrome120', verify=False) as client:"]
            code += list(self._scraper_steps(flows_data, "curl_cffi"))
            code += ["if __name__ == '__main__':", "    asyncio.run(run_scraper())"]
            return "\n".join(code)

        code = ["import asyncio", "import json",
                "from playwright.async_api import async_playwright", "",
                "async def run_scraper():", "    async with async_playwright() as p:",
                "        browser = await p.chromium.launch(headless=True)",
                "        context = await browser.new_context(ignore_https_errors=True)",
                "        page = await context.new_page()"]
        code += list(self._scraper_steps(flows_data, "playwright"))
        code += ["        await browser.close()", "", "if __name__ == '__main__':", "    asyncio.run(run_scraper())"]
        return "\n".join(code)

    def diff_flows(self, flow_a: str, flow_b: str, max_lines: int = 50) -> str:
        a = self.db.get_detail(flow_a, level="full")
        b = self.db.get_detail(flow_b, level="full")
        if not a or not b:
            return json.dumps({"error": "one or both flows not found"})

        def _resp(d):
            return d.get("response") or {}
        ra, rb = _resp(a), _resp(b)
        diff = {
            "a": flow_a,
            "b": flow_b,
            "status": [ra.get("status_code"), rb.get("status_code")],
            "size": [len(ra.get("body") or ""), len(rb.get("body") or "")],
            "content_type": [
                self._detect_content_type(ra.get("headers", {}) or {}),
                self._detect_content_type(rb.get("headers", {}) or {}),
            ],
        }
        body_a, body_b = ra.get("body") or "", rb.get("body") or ""
        ct_a = (ra.get("headers", {}) or {}).get("content-type",
                (ra.get("headers", {}) or {}).get("Content-Type", "")).lower()
        if "json" in ct_a:
            try:
                ja, jb = json.loads(body_a or "{}"), json.loads(body_b or "{}")
                diff["json_diff"] = self._json_field_diff(ja, jb)
            except Exception:
                pass
        if "json_diff" not in diff:
            import difflib
            lines_a = body_a.splitlines()[:5000]
            lines_b = body_b.splitlines()[:5000]
            udiff = list(difflib.unified_diff(
                lines_a, lines_b, fromfile="a", tofile="b", lineterm=""))[:max_lines]
            diff["text_diff"] = udiff
        return json.dumps(diff, indent=2)

    @staticmethod
    def _json_field_diff(a, b, prefix: str = "") -> Dict[str, List[str]]:
        added: List[str] = []
        removed: List[str] = []
        changed: List[str] = []

        def walk(x, y, p):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in y:
                    if k not in x:
                        added.append(f"{p}.{k}" if p else k)
                    else:
                        walk(x[k], y[k], f"{p}.{k}" if p else k)
                for k in x:
                    if k not in y:
                        removed.append(f"{p}.{k}" if p else k)
            elif isinstance(x, list) and isinstance(y, list):
                if len(x) != len(y):
                    changed.append(f"{p}[len {len(x)}->{len(y)}]")
                for i in range(min(len(x), len(y))):
                    walk(x[i], y[i], f"{p}[{i}]")
            else:
                if x != y:
                    changed.append(p or "<root>")

        walk(a, b, prefix)
        return {"added": added[:50], "removed": removed[:50], "changed": changed[:50]}

    def site_map(self, domain: Optional[str] = None) -> str:
        """Group endpoints by host with finding counts. Flat structure, agent-friendly."""
        import sqlite3
        flows = self.db.get_all_for_analysis(lightweight=True)
        if domain:
            flows = [f for f in flows if domain in f["request"]["url"]]

        with self.db._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            finding_rows = conn.execute(
                "SELECT flow_id, COUNT(*) c FROM findings GROUP BY flow_id"
            ).fetchall()
        findings_count = {r["flow_id"]: r["c"] for r in finding_rows}

        host_map: Dict[str, Dict[str, Any]] = {}
        for f in flows:
            parsed = urlparse(f["request"]["url"])
            host = parsed.hostname or "unknown"
            normalized_path, _ = self._normalize_path(parsed.path)
            method = f["request"]["method"]
            key = f"{method} {normalized_path}"

            host_entry = host_map.setdefault(host, {"host": host, "endpoints": {}, "flow_count": 0, "findings": 0})
            host_entry["flow_count"] += 1
            host_entry["findings"] += findings_count.get(f["id"], 0)

            ep = host_entry["endpoints"].setdefault(key, {
                "method": method,
                "path": normalized_path,
                "params": set(),
                "status_dist": Counter(),
                "auth_required": False,
                "count": 0,
                "findings": 0,
                "sample_flow_id": f["id"],
            })
            ep["count"] += 1
            ep["findings"] += findings_count.get(f["id"], 0)
            for p in parse_qs(parsed.query).keys():
                ep["params"].add(p)
            req_headers = f["request"].get("headers", {}) or {}
            if any(k.lower() in ("authorization", "cookie", "x-api-key", "x-auth-token") for k in req_headers):
                ep["auth_required"] = True
            if f["response"]:
                ep["status_dist"][f["response"].get("status_code", 0)] += 1

        result = []
        for host, entry in sorted(host_map.items(), key=lambda x: -x[1]["flow_count"]):
            endpoints = []
            for _, ep in sorted(entry["endpoints"].items(), key=lambda x: -x[1]["count"]):
                endpoints.append({
                    "method": ep["method"],
                    "path": ep["path"],
                    "params": sorted(ep["params"]),
                    "status_dist": dict(ep["status_dist"]),
                    "auth_required": ep["auth_required"],
                    "count": ep["count"],
                    "findings": ep["findings"],
                    "sample_flow_id": ep["sample_flow_id"],
                })
            result.append({
                "host": host,
                "flow_count": entry["flow_count"],
                "findings": entry["findings"],
                "endpoints": endpoints,
            })
        return json.dumps(result, indent=2)

    def evidence_bundle(self, flow_id: str, depth: int = 3) -> str:
        """Walk the link DAG around `flow_id` (configurable depth) and emit a
        Markdown report containing every related flow's request/response summary,
        tags, findings, and a curl reproducer. The agent uses this as the final
        artifact — drop it into a SRC report or a PoC PR.

        Pure string concat; no template engine. Output stays under ~30 KB even
        for chains of ~10 flows because each body is preview-sized.
        """
        chain = self.db.get_chain(flow_id, depth=depth)
        ordered_ids: List[str] = []
        for u in reversed(chain.get("upstream", [])):
            ordered_ids.append(u["flow_id"])
        ordered_ids.append(flow_id)
        for d in chain.get("downstream", []):
            ordered_ids.append(d["flow_id"])
        seen = set()
        ordered_ids = [x for x in ordered_ids if not (x in seen or seen.add(x))]

        lines: List[str] = [f"# Evidence Bundle — root flow `{flow_id[:8]}…`", ""]
        if chain["tags"]:
            lines.append("**Root tags:** " + ", ".join(f"`{t}`" for t in chain["tags"]))
            lines.append("")
        lines.append(f"**Chain size:** {len(ordered_ids)} flow(s) (depth={depth})")
        lines.append("")
        for fid in ordered_ids:
            lines.extend(self._evidence_flow_section(fid, root_id=flow_id))
        return "\n".join(lines)

    def _evidence_flow_section(self, fid: str, root_id: str) -> List[str]:
        import sqlite3
        data = self.db.get_detail(fid, level="preview")
        if not data:
            return []
        req = data.get("request") or {}
        resp = data.get("response") or {}
        tags = self.db.get_tags(fid)
        findings = self.db.list_findings(flow_id=fid, kind="all", limit=20)
        note = self.db.get_note(fid)

        marker = " (root)" if fid == root_id else ""
        lines = [f"## Flow `{fid[:8]}…`{marker}", "", f"- **{req.get('method')}** `{req.get('url')}`"]
        if resp:
            lines.append(f"- Status: `{resp.get('status_code')}`")
        with self.db._get_conn() as conn:
            row = conn.execute("SELECT profile_label FROM flows WHERE id = ?", (fid,)).fetchone()
        if row and row[0]:
            lines.append(f"- Profile: `{row[0]}`")
        if tags:
            lines.append("- Tags: " + ", ".join(f"`{t}`" for t in tags))
        if findings:
            lines.append("- Findings:")
            for f in findings:
                lines.append(f"  - `{f['kind']}/{f['severity']}` **{f['rule_id']}** — {f.get('evidence','')}")
        if note:
            lines.append("")
            lines.append(f"**Triage note** — verdict: `{note['verdict']}`")
            for label_, key in [("Scenario", "scenario"), ("Sensitive fields", "sensitive_fields"),
                                ("Test steps", "test_steps"), ("Conclusion", "conclusion")]:
                val = note.get(key)
                if val:
                    lines.append(f"- *{label_}*: {val}")
        lines += ["", "**Request body (preview):**", "```",
                  (req.get("body") or "")[:1000] or "<empty>", "```"]
        if resp:
            lines += ["**Response body (preview):**", "```",
                      (resp.get("body") or "")[:1000] or "<empty>", "```"]
        lines += ["**Reproduce:**", "```bash", data.get("curl_command") or "", "```", ""]
        return lines

    # ── Cross-flow data-flow correlation (the ② layer) ─────────────────────
    def correlate_dataflow(self, limit: Optional[int] = None,
                           freq_cap: int = 8, max_edges: int = 200) -> str:
        """Find values minted in one flow's RESPONSE that reappear in a later
        flow's REQUEST — the data-flow taint that underlies OAuth code-leak,
        echoed SSRF, param-passthrough and COS-credential-reuse bugs.

        Pure read over the DB; the only writes are into the EXISTING flow_links
        and findings tables, so the result feeds straight into traffic_chain /
        evidence_bundle. Two outputs:
          • flow_link(relation="value_passthrough") + a `dataflow_passthrough`
            signal, for every source→consumer edge.
          • a `cross_identity_secret_reuse` high finding when a secret-shaped
            value is seen under more than one profile_label (cross-tenant /
            cross-account secret exposure).

        Noise control: a value minted in > freq_cap flows is treated as global
        (session cookie, static asset hash) and skipped; edges are capped.
        """
        limit = limit if limit is not None else self.MAX_ANALYSIS_FLOWS
        import sqlite3
        with self.db._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, url, method, request_headers, request_body, "
                "response_headers, response_body, profile_label, timestamp "
                "FROM flows ORDER BY timestamp ASC LIMIT ?", (limit,),
            ).fetchall()

        # Pass A — index every token minted in a response → its source flows.
        # value -> {flow_id: (timestamp, profile_label)}
        minted: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            resp_blob = " ".join(filter(None, (r["response_headers"], r["response_body"])))
            for tok in _extract_tokens(resp_blob):
                minted.setdefault(tok, {})[r["id"]] = (r["timestamp"], r["profile_label"])

        # Drop globals: a value handed out by too many flows is low-signal.
        minted = {v: srcs for v, srcs in minted.items() if 1 <= len(srcs) <= freq_cap}
        return self._correlate_consume(rows, minted, max_edges)

    def _correlate_consume(self, rows, minted: Dict[str, Dict[str, Any]],
                           max_edges: int) -> str:
        """Pass B: scan each flow's REQUEST for minted tokens and emit edges /
        findings. Split out of correlate_dataflow to keep each method small."""
        edges: List[Dict[str, Any]] = []
        seen_edges = set()
        cross_identity: List[Dict[str, Any]] = []
        cross_seen = set()

        for r in rows:
            consumer_id = r["id"]
            req_blob = " ".join(filter(None, (r["url"], r["request_headers"], r["request_body"])))
            if not req_blob:
                continue
            for tok in _extract_tokens(req_blob):
                srcs = minted.get(tok)
                if not srcs:
                    continue
                for src_id, (src_ts, src_label) in srcs.items():
                    # An edge is source→consumer where the consumer's request
                    # carries a value the source's response minted, and the
                    # consumer came no earlier than the source (causality).
                    if src_id == consumer_id:
                        continue
                    if r["timestamp"] is not None and src_ts is not None and r["timestamp"] < src_ts:
                        continue
                    key = (src_id, consumer_id)
                    if key in seen_edges:
                        continue
                    seen_edges.add(key)
                    if len(edges) < max_edges:
                        self.db.add_link(src_id, consumer_id, "value_passthrough")
                        self.db.add_finding(
                            consumer_id, "dataflow_passthrough", "medium", "dataflow",
                            f"value from {src_id[:8]} reused: {tok[:16]}…", kind="signal")
                        edges.append({"source": src_id, "target": consumer_id,
                                      "evidence": tok[:24]})

                # Cross-identity secret reuse: a secret-shaped value minted /
                # consumed under differing profile_labels.
                if _SECRET_TOKEN_RE.match(tok):
                    labels = {lbl for _, lbl in srcs.values() if lbl}
                    if r["profile_label"]:
                        labels.add(r["profile_label"])
                    if len(labels) > 1 and tok not in cross_seen:
                        cross_seen.add(tok)
                        src_id = next(iter(srcs))
                        self.db.add_finding(
                            src_id, "cross_identity_secret_reuse", "high", "secret_leak",
                            f"secret {tok[:12]}… seen under labels {sorted(labels)}",
                            kind="finding")
                        cross_identity.append({"value": tok[:24],
                                               "labels": sorted(labels),
                                               "source": src_id})

        # seen_edges counts every unique candidate; edges only those actually
        # written. The gap (if any) is edges suppressed by max_edges — surface
        # it rather than silently dropping, so the agent knows to raise the cap.
        suppressed = len(seen_edges) - len(edges)
        return json.dumps({
            "flows_scanned": len(rows),
            "values_tracked": len(minted),
            "edges_created": len(edges),
            "edges_capped": suppressed > 0,
            "edges_suppressed": suppressed,
            "edges": edges[:50],
            "cross_identity_secret_reuse": cross_identity,
            "note": ("value_passthrough links + dataflow_passthrough signals written; "
                     "walk them with traffic_chain / evidence_bundle. Edges are "
                     "candidates — confirm the business meaning before reporting."
                     + (" Hit max_edges — raise it to see the rest." if suppressed else "")),
        }, indent=2)








