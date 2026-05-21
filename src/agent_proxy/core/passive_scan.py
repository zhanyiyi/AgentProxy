"""Passive scanner — runs cheap regex/header checks on every captured flow.

Goal: surface "interesting" requests so the agent doesn't have to inspect
hundreds of flows manually. Rule definitions live in the YAML rule pack
(see `src/agent_proxy/config/defaults.yaml`); this module is just the engine
that applies them.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from mitmproxy import http

from ..config import RuleConfig


class PassiveScanner:
    """Stateless scanner — call scan(flow, db) on each completed flow.

    Rules are pulled from a `RuleConfig` (YAML-backed). Pass `rules=None` to
    fall back to the bundled defaults.
    """

    def __init__(self, rules: Optional[RuleConfig] = None):
        if rules is None:
            from ..config import load_rule_config
            rules = load_rule_config()
        self.rules = rules

    def scan(self, flow: http.HTTPFlow, db) -> int:
        """Returns number of findings written for this flow."""
        if not flow.request:
            return 0
        count = 0
        try:
            count += self._scan_url_and_params(flow, db)
            count += self._scan_response(flow, db)
        except Exception:
            return count
        return count

    def _scan_url_and_params(self, flow: http.HTTPFlow, db) -> int:
        n = 0
        url = flow.request.url
        parsed = urlparse(url)
        path = parsed.path or ""

        m = self.rules.debug_paths.search(path)
        if m:
            db.add_finding(flow.id, "debug_endpoint", "high",
                           "exposure", f"path:{m.group(0)}", kind="finding")
            n += 1

        params = list(parse_qs(parsed.query).keys())
        try:
            ct = (flow.request.headers.get("content-type", "") or "").lower()
            if "json" in ct and flow.request.content:
                import json as _json
                try:
                    body_obj = _json.loads(flow.request.content.decode("utf-8", errors="replace"))
                    if isinstance(body_obj, dict):
                        params += list(body_obj.keys())
                except Exception:
                    pass
            elif "x-www-form-urlencoded" in ct and flow.request.content:
                from urllib.parse import parse_qsl
                params += [k for k, _ in parse_qsl(
                    flow.request.content.decode("utf-8", errors="replace"))]
        except Exception:
            pass

        sensitive = self.rules.sensitive_param_names
        for p in params:
            if p.lower() in sensitive:
                db.add_finding(flow.id, "sensitive_param", "medium",
                               "input_surface", f"param:{p}", kind="signal")
                n += 1
        return n

    def _scan_response(self, flow: http.HTTPFlow, db) -> int:
        if not flow.response:
            return 0
        n = 0
        resp = flow.response
        headers = {k.lower(): v for k, v in resp.headers.items()}
        ct = headers.get("content-type", "")

        # CORS misconfig — wildcard or reflected origin + credentials
        acao = headers.get("access-control-allow-origin", "")
        acac = headers.get("access-control-allow-credentials", "").lower()
        if acac == "true" and acao:
            req_origin = ""
            try:
                req_origin = flow.request.headers.get("origin", "") or ""
            except Exception:
                pass
            if acao == "*" or (req_origin and acao == req_origin):
                db.add_finding(flow.id, "cors_misconfig", "high",
                               "header_misconfig", f"ACAO:{acao}|ACAC:true", kind="finding")
                n += 1

        # Set-Cookie missing flags (only for https flows)
        try:
            if flow.request.url.startswith("https://"):
                for raw in resp.headers.get_all("set-cookie") or []:
                    low = raw.lower()
                    missing = []
                    if "secure" not in low:
                        missing.append("Secure")
                    if "httponly" not in low:
                        missing.append("HttpOnly")
                    if missing:
                        cookie_name = raw.split("=", 1)[0].strip()[:80]
                        db.add_finding(flow.id, "cookie_insecure", "low",
                                       "header_misconfig",
                                       f"{cookie_name} missing:{','.join(missing)}",
                                       kind="signal")
                        n += 1
        except Exception:
            pass

        # Missing CSP on HTML responses
        if "text/html" in ct.lower() and "content-security-policy" not in headers:
            db.add_finding(flow.id, "missing_csp", "info",
                           "header_misconfig", "no Content-Security-Policy",
                           kind="signal")
            n += 1

        # Body-based regex rules (loaded from YAML) — only for text-ish responses
        body = None
        text_like = any(t in ct.lower() for t in ("text", "json", "xml", "html", "javascript"))
        if text_like:
            try:
                raw = resp.content
                if raw:
                    body = raw[: 256 * 1024].decode("utf-8", errors="replace")
            except Exception:
                body = None
        if body:
            for rule in self.rules.body_rules:
                m = rule.pattern.search(body)
                if m:
                    snippet = m.group(0)[:120]
                    db.add_finding(flow.id, rule.id, rule.severity, rule.category,
                                   snippet, kind=rule.kind)
                    n += 1
        return n


def scan_existing_flows(db, scanner: "PassiveScanner | None" = None) -> int:
    """Re-scan already-stored flows (used after enabling new rules)."""
    scanner = scanner or PassiveScanner()
    count = 0
    flows = db.get_all_for_analysis(lightweight=False)
    for f in flows:
        # Build a minimal mitmproxy-flow-like adapter
        class _Adapter:
            class _Msg:
                def __init__(self, headers, content):
                    self.headers = _HeaderShim(headers or {})
                    self.content = (content or "").encode("utf-8", errors="replace") if isinstance(content, str) else (content or b"")
            def __init__(self, fid, req, resp):
                self.id = fid
                self.request = self._build_req(req)
                self.response = self._build_resp(resp) if resp else None
            def _build_req(self, r):
                msg = _Adapter._Msg(r.get("headers", {}), r.get("body"))
                msg.url = r.get("url", "")
                msg.method = r.get("method", "GET")
                return msg
            def _build_resp(self, r):
                msg = _Adapter._Msg(r.get("headers", {}), r.get("body"))
                msg.status_code = r.get("status_code")
                return msg
        adapter = _Adapter(f["id"], f.get("request", {}), f.get("response"))
        count += scanner.scan(adapter, db)
    return count


class _HeaderShim:
    def __init__(self, d):
        self._d = d or {}
    def get(self, k, default=None):
        if k in self._d:
            return self._d[k]
        kl = k.lower()
        for hk, hv in self._d.items():
            if hk.lower() == kl:
                return hv
        return default
    def items(self):
        return self._d.items()
    def get_all(self, k):
        kl = k.lower()
        return [v for hk, v in self._d.items() if hk.lower() == kl]
