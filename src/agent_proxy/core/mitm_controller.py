import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, parse_qsl
from collections import Counter

import structlog
from mitmproxy import options, http
from mitmproxy.tools.dump import DumpMaster
from curl_cffi.requests import AsyncSession
from jsonpath_ng import parse as parse_jsonpath
from bs4 import BeautifulSoup

from ..models import InterceptionRule, ScopeConfig
from ..config import RuleConfig, load_rule_config
from .traffic_db import TrafficDB
from .passive_scan import PassiveScanner

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logging.basicConfig(format="%(message)s", level=logging.INFO)

logger = structlog.get_logger()


class ScopeManager:
    def __init__(self, config: ScopeConfig):
        self.config = config

    def update_domains(self, domains: List[str]):
        self.config.allowed_domains = domains

    def is_allowed(self, flow: http.HTTPFlow) -> bool:
        if flow.request.method.upper() in {m.upper() for m in self.config.ignore_methods}:
            return False
        parsed = urlparse(flow.request.url)
        path = (parsed.path or "").lower()
        for ext in self.config.ignore_extensions:
            if path.endswith(ext):
                return False
        if not self.config.allowed_domains:
            return True
        hostname = parsed.hostname or ""
        return any(hostname == d or hostname.endswith(f".{d}") for d in self.config.allowed_domains)


class TrafficInterceptor:
    def __init__(self):
        self.rules: Dict[str, InterceptionRule] = {}
        self._compiled_patterns: Dict[str, Dict[str, Any]] = {}

    def add_rule(self, rule: InterceptionRule) -> bool:
        patterns = {}
        try:
            if rule.url_pattern:
                patterns["url"] = re.compile(rule.url_pattern)
            if rule.search_pattern:
                patterns["search"] = re.compile(rule.search_pattern)
        except re.error as e:
            logger.warning("Failed to compile regex for rule %s: %s", rule.id, e)
            return False
        self.rules[rule.id] = rule
        self._compiled_patterns[rule.id] = patterns
        return True

    def remove_rule(self, rule_id: str):
        self.rules.pop(rule_id, None)
        self._compiled_patterns.pop(rule_id, None)

    def clear_rules(self):
        self.rules.clear()
        self._compiled_patterns.clear()

    def request(self, flow: http.HTTPFlow):
        self._apply_rules(flow, "request")

    def response(self, flow: http.HTTPFlow):
        self._apply_rules(flow, "response")

    def _apply_rules(self, flow: http.HTTPFlow, phase: str):
        message = getattr(flow, phase)
        if not message:
            return
        for rule in self.rules.values():
            if not rule.active or rule.phase != phase:
                continue
            if rule.method and flow.request.method != rule.method:
                continue
            compiled = self._compiled_patterns.get(rule.id, {})
            url_pattern = compiled.get("url")
            if url_pattern and not url_pattern.search(flow.request.url):
                continue
            try:
                if rule.action_type == "inject_header" and rule.key and rule.value:
                    message.headers[rule.key] = rule.value
                elif rule.action_type == "replace_body" and rule.search_pattern and rule.value:
                    text = TrafficDB._get_safe_text(message)
                    if text is not None:
                        search_pattern = compiled.get("search")
                        if search_pattern:
                            message.text = search_pattern.sub(rule.value, text)
                elif rule.action_type == "block":
                    flow.kill()
            except Exception as e:
                logger.error("Error applying rule %s: %s", rule.id, e)


class TrafficRecorder:
    def __init__(self, scope: ScopeManager, db: TrafficDB, scanner: Optional[PassiveScanner] = None):
        self.scope = scope
        self.db = db
        self.scanner = scanner or PassiveScanner()

    @staticmethod
    def _strip_context_label(flow: http.HTTPFlow) -> Optional[str]:
        """Pop our internal X-AgentProxy-Context header before it leaves the proxy.
        Returned value (if any) is stored as flows.profile_label."""
        try:
            label = flow.request.headers.pop("X-AgentProxy-Context", None)
            if label is None:
                # mitmproxy header objects are case-insensitive but pop() above
                # only removes the exact key; defensively try lowercase too
                for hk in list(flow.request.headers.keys()):
                    if hk.lower() == "x-agentproxy-context":
                        label = flow.request.headers[hk]
                        del flow.request.headers[hk]
                        break
            return label
        except Exception:
            return None

    def request(self, flow: http.HTTPFlow):
        # Always strip our internal label header so the target server never sees it.
        label = self._strip_context_label(flow)
        if label:
            flow.metadata["profile_label"] = label
        if self.scope.is_allowed(flow):
            try:
                self.db.save_flow(flow, profile_label=flow.metadata.get("profile_label"))
            except Exception as e:
                logger.error("Failed to save request flow: %s", e)

    def response(self, flow: http.HTTPFlow):
        if self.scope.is_allowed(flow):
            try:
                self.db.save_flow(flow, profile_label=flow.metadata.get("profile_label"))
                self.scanner.scan(flow, self.db)
            except Exception as e:
                logger.error("Failed to save flow: %s", e)

    def error(self, flow: http.HTTPFlow):
        if self.scope.is_allowed(flow):
            try:
                self.db.save_flow(flow, profile_label=flow.metadata.get("profile_label"))
            except Exception as e:
                logger.error("Failed to save flow error: %s", e)


class MitmController:
    def __init__(self, db_path: str = "agent_proxy_traffic.db",
                 rules: Optional[RuleConfig] = None):
        self.master: Optional[DumpMaster] = None
        self.proxy_task: Optional[asyncio.Task] = None
        self.scope_config = ScopeConfig()
        self.scope_manager = ScopeManager(self.scope_config)
        self.db = TrafficDB(db_path)
        self.rules = rules or load_rule_config()
        self.recorder = TrafficRecorder(self.scope_manager, self.db,
                                        scanner=PassiveScanner(rules=self.rules))
        self.interceptor = TrafficInterceptor()
        self.running = False
        self.port = 8080
        self.host = "127.0.0.1"
        self.session_variables: Dict[str, str] = {}

    def _get_verify_param(self, verify_override: Optional[bool] = None) -> Any:
        if verify_override is not None:
            return verify_override
        cert_path = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")
        if os.path.exists(cert_path):
            return cert_path
        return True

    async def start(self, port: int = 8080, host: str = "127.0.0.1") -> str:
        if self.running:
            return f"MITM proxy already running on port {self.port}"

        self.port = port
        self.host = host
        opts = options.Options(listen_host=host, listen_port=port)
        self.master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        self.master.addons.add(self.recorder)
        self.master.addons.add(self.interceptor)

        self.proxy_task = asyncio.create_task(self.master.run())
        self.running = True
        logger.info("proxy_started", host=host, port=port)
        return f"Started MITM proxy on {host}:{port}"

    async def stop(self) -> str:
        if not self.running or not self.master:
            return "Proxy is not running"
        try:
            ps_addon = self.master.addons.get("proxyserver")
            if ps_addon:
                for handler in list(ps_addon.connections.values()):
                    try:
                        for transport_io in list(handler.transports.values()):
                            if transport_io.writer and not transport_io.writer.is_closing():
                                transport_io.writer.close()
                    except Exception:
                        pass
                for instance in list(ps_addon.servers._instances.values()):
                    try:
                        await instance.stop()
                    except Exception:
                        pass
                ps_addon.servers._instances.clear()
        except Exception:
            pass
        self.master.shutdown()
        if self.proxy_task:
            done, _ = await asyncio.wait({self.proxy_task}, timeout=5.0)
            if not done:
                self.proxy_task.cancel()
                try:
                    await self.proxy_task
                except (asyncio.CancelledError, Exception):
                    pass
            self.proxy_task = None
        self.running = False
        logger.info("proxy_stopped")
        return "Stopped MITM proxy"

    async def replay_request(
        self,
        flow_id: str,
        method: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout: float = 30.0,
    ) -> str:
        flow_data = self.db.get_detail(flow_id)
        if not flow_data:
            return "Flow not found"

        original_request = flow_data["request"]
        target_url = original_request["url"]
        target_method = method if method else original_request["method"]

        target_headers = dict(original_request["headers"])
        target_headers.pop("Host", None)
        target_headers.pop("Content-Length", None)
        target_headers.pop("Content-Encoding", None)

        if headers:
            target_headers.update(headers)

        target_content = None
        if body is not None:
            target_content = body
        else:
            flow_obj = self.db.get_flow_object(flow_id)
            if flow_obj and flow_obj.body is not None:
                target_content = flow_obj.body
            else:
                target_content = original_request.get("body")
            if not target_content:
                target_content = None

        proxy_url = f"http://{self.host}:{self.port}"

        before_ts = time.time()
        try:
            async with AsyncSession(
                impersonate="chrome120",
                proxies={"http": proxy_url, "https": proxy_url},
                verify=self._get_verify_param(),
                timeout=timeout,
            ) as client:
                request_kwargs = {
                    "method": target_method,
                    "url": target_url,
                    "headers": target_headers,
                }
                if target_content is not None:
                    request_kwargs["data"] = target_content
                response = await client.request(**request_kwargs)

            # Give mitmproxy a beat to flush the response into SQLite, then
            # look up the freshly captured flow id so the agent can chain into diff/evidence.
            new_flow_id = None
            for _ in range(10):
                new_flow_id = self.db.find_replay_match(target_url, target_method, before_ts)
                if new_flow_id:
                    break
                await asyncio.sleep(0.1)

            return json.dumps({
                "via": "curl_cffi",
                "status_code": response.status_code,
                "size": len(response.content) if response.content else 0,
                "new_flow_id": new_flow_id,
            })
        except Exception as e:
            logger.error("Replay failed: %s", e)
            return json.dumps({"via": "curl_cffi", "error": str(e)})

    async def replay_with_storage_state(
        self,
        flow_id: str,
        storage_state_path: str,
        method: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout: float = 30.0,
        context_label: Optional[str] = None,
    ) -> str:
        """Cold replay path: load cookies from a Playwright storage_state.json,
        then send via curl_cffi. Used when no live browser context exists for the
        target identity but a saved profile does."""
        if not os.path.exists(storage_state_path):
            return json.dumps({"error": f"storage_state not found: {storage_state_path}"})
        try:
            with open(storage_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            return json.dumps({"error": f"Failed to read storage_state: {e}"})

        flow_data = self.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
        if not flow_data:
            return json.dumps({"error": "Flow not found"})

        original = flow_data["request"]
        target_url = original["url"]
        target_method = (method or original["method"]).upper()
        target_headers = dict(original.get("headers") or {})
        for k in ("Host", "Content-Length", "Content-Encoding", "Cookie"):
            target_headers.pop(k, None)
            target_headers.pop(k.lower(), None)
        if headers:
            target_headers.update(headers)

        # Build cookie dict from storage_state for matching domain
        parsed = urlparse(target_url)
        target_host = parsed.hostname or ""
        cookies: Dict[str, str] = {}
        for c in state.get("cookies", []):
            dom = (c.get("domain") or "").lstrip(".")
            if not dom or target_host == dom or target_host.endswith(f".{dom}"):
                cookies[c["name"]] = c["value"]

        target_body = body if body is not None else original.get("body")
        proxy_url = f"http://{self.host}:{self.port}"
        before_ts = time.time()
        try:
            async with AsyncSession(
                impersonate="chrome120",
                proxies={"http": proxy_url, "https": proxy_url},
                verify=self._get_verify_param(),
                timeout=timeout,
                cookies=cookies,
            ) as client:
                kwargs: Dict[str, Any] = {"method": target_method, "url": target_url, "headers": target_headers}
                if target_body is not None:
                    kwargs["data"] = target_body
                resp = await client.request(**kwargs)

            new_flow_id = None
            for _ in range(10):
                new_flow_id = self.db.find_replay_match(target_url, target_method, before_ts)
                if new_flow_id:
                    break
                await asyncio.sleep(0.1)
            # The cold path can't inject X-AgentProxy-Context (no live browser),
            # so backfill profile_label here.
            if new_flow_id and context_label:
                with self.db._get_conn() as conn:
                    conn.execute("UPDATE flows SET profile_label = ? WHERE id = ?",
                                 (context_label, new_flow_id))
            return json.dumps({
                "via": "curl_cffi+storage_state",
                "context": context_label,
                "status_code": resp.status_code,
                "size": len(resp.content) if resp.content else 0,
                "new_flow_id": new_flow_id,
            })
        except Exception as e:
            logger.error("Storage-state replay failed: %s", e)
            return json.dumps({"error": str(e)})

    async def fuzz_endpoint(
        self,
        flow_id: str,
        target_param: str,
        param_type: str,
        payload_category: str,
        timeout: float = 10.0,
    ) -> str:
        flow_data = self.db.get_detail(flow_id)
        if not flow_data:
            return "Flow not found"

        payloads_map = self.rules.fuzz_payloads
        if payload_category not in payloads_map:
            return f"Unknown payload category. Use: {', '.join(sorted(payloads_map.keys()))}"

        payloads = payloads_map[payload_category]
        original_request = flow_data["request"]
        base_url = original_request["url"]
        method = original_request["method"]
        target_headers = dict(original_request["headers"])
        target_headers.pop("Host", None)
        target_headers.pop("Content-Length", None)
        target_headers.pop("Content-Encoding", None)

        baseline_status = 200
        baseline_len = 0
        baseline_flow = self.db.get_flow_object(flow_id)
        if baseline_flow:
            flow_detail = self.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
            if flow_detail and flow_detail.get("response"):
                baseline_status = flow_detail["response"].get("status_code", 200)
                baseline_body = flow_detail["response"].get("body", "") or ""
                baseline_len = len(baseline_body)

        proxy_url = f"http://{self.host}:{self.port}"
        anomalies = []

        async with AsyncSession(
            impersonate="chrome120",
            proxies={"http": proxy_url, "https": proxy_url},
            verify=self._get_verify_param(),
            timeout=timeout,
        ) as client:
            tasks = []
            for payload in payloads:
                req_url = base_url
                req_body = None

                if param_type == "query":
                    parsed_url = urlparse(base_url)
                    qs = parse_qsl(parsed_url.query)
                    new_qs = [(k, payload if k == target_param else v) for k, v in qs]
                    if target_param not in [k for k, v in qs]:
                        new_qs.append((target_param, payload))
                    req_url = parsed_url._replace(query=urlencode(new_qs)).geturl()
                    flow_obj = self.db.get_flow_object(flow_id)
                    if flow_obj and flow_obj.body:
                        req_body = flow_obj.body
                    else:
                        req_body = original_request.get("body")

                elif param_type == "json_body":
                    flow_obj = self.db.get_flow_object(flow_id)
                    body_content = flow_obj.body if flow_obj else None
                    if not body_content:
                        body_content = original_request.get("body", "")
                    try:
                        if isinstance(body_content, bytes):
                            body_content = body_content.decode("utf-8")
                        body_data = json.loads(body_content)
                        body_data[target_param] = payload
                        req_body = json.dumps(body_data)
                    except Exception as e:
                        return f"Failed to parse JSON body: {str(e)}"
                else:
                    return "Unknown param_type. Use 'query' or 'json_body'"

                async def run_req(p=payload, u=req_url, b=req_body):
                    try:
                        request_kwargs = {"method": method, "url": u, "headers": target_headers}
                        if b is not None:
                            request_kwargs["data"] = b
                        resp = await client.request(**request_kwargs)
                        status = resp.status_code
                        content = resp.content or b""
                        content_len = len(content)
                        try:
                            body_text = content.decode("utf-8", errors="replace")
                        except Exception:
                            body_text = ""
                        reflected = bool(p) and p in body_text

                        anomaly = None
                        if status >= 500:
                            anomaly = {"payload": p, "anomaly": "Server Error (5xx)", "status": status}
                        elif status != baseline_status:
                            anomaly = {"payload": p, "anomaly": f"Status Code Deviation ({baseline_status} -> {status})", "status": status}
                        elif baseline_len > 0:
                            diff_ratio = abs(content_len - baseline_len) / baseline_len
                            if diff_ratio > 0.2:
                                anomaly = {"payload": p, "anomaly": "Content Length Deviation (>20%)", "status": status, "len": content_len}
                        if reflected and anomaly is None:
                            anomaly = {"payload": p, "anomaly": "Payload Reflected in Response", "status": status, "len": content_len}
                        if anomaly is not None:
                            anomaly["reflected"] = reflected
                            return anomaly
                        return None
                    except Exception as e:
                        return {"payload": p, "anomaly": f"Request Failed: {str(e)}"}

                tasks.append(run_req())

            results = await asyncio.gather(*tasks)
            for r in results:
                if r:
                    anomalies.append(r)

        if not anomalies:
            return "Fuzzing complete. No significant anomalies detected."

        return json.dumps({
            "baseline_status": baseline_status,
            "baseline_len": baseline_len,
            "anomalies": anomalies,
        }, indent=2)

    def detect_auth_patterns(self, flow_ids: Optional[List[str]] = None) -> Dict:
        if flow_ids:
            flows = self.db.get_by_ids(flow_ids)
        else:
            flows = self.db.get_all_for_analysis()

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

            query_params = parse_qs(parsed.query)
            for param in query_params.keys():
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
        patterns_json = self.get_api_patterns(domain, limit)
        clusters = json.loads(patterns_json)

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

            if path not in spec["paths"]:
                spec["paths"][path] = {}

            operation = {
                "summary": f"{method.upper()} {path}",
                "parameters": [],
                "responses": {},
            }

            for param in cluster["path_params"]:
                operation["parameters"].append({"name": param, "in": "path", "required": True, "schema": {"type": "string"}})
            for param in cluster["query_params"]:
                operation["parameters"].append({"name": param, "in": "query", "schema": {"type": "string"}})

            for status_code, count in cluster["status_codes"].items():
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

    def generate_scraper_code(self, flow_ids: List[str], target_framework: str = "curl_cffi") -> str:
        flows_data = []
        for fid in flow_ids:
            data = self.db.get_detail(fid, level="full", body_preview_length=256 * 1024)
            if data:
                flows_data.append(data)

        if not flows_data:
            return "No valid flows found"

        if target_framework == "curl_cffi":
            code = [
                "import asyncio",
                "import json",
                "from curl_cffi.requests import AsyncSession",
                "",
                "async def run_scraper():",
                "    async with AsyncSession(impersonate='chrome120', verify=False) as client:",
            ]
            for i, flow in enumerate(flows_data):
                req = flow["request"]
                url = req["url"]
                method = req["method"]
                headers = dict(req["headers"])
                headers.pop("Host", None)
                headers.pop("Content-Length", None)
                headers.pop("Content-Encoding", None)
                body = req.get("body")

                flow_obj = self.db.get_flow_object(flow["id"])
                if flow_obj and flow_obj.body:
                    body = flow_obj.body

                code.append(f"        # Step {i + 1}: {method} {url[:60]}")
                code.append(f"        headers_{i} = {json.dumps(headers, indent=12).strip()}")
                kwargs = f"method={json.dumps(method)}, url={json.dumps(url)}, headers=headers_{i}"
                if body and body != "<binary data omitted>":
                    code.append(f"        data_{i} = {json.dumps(body)}")
                    kwargs += f", data=data_{i}"
                code.append(f"        try:")
                code.append(f"            response_{i} = await client.request({kwargs})")
                code.append(f"            print(f'Status: {{response_{i}.status_code}}')")
                code.append(f"        except Exception as e:")
                code.append(f"            print(f'Error: {{e}}')")
                code.append("")

            code.extend(["if __name__ == '__main__':", "    asyncio.run(run_scraper())"])
            return "\n".join(code)

        elif target_framework == "playwright":
            code = [
                "import asyncio",
                "import json",
                "from playwright.async_api import async_playwright",
                "",
                "async def run_scraper():",
                "    async with async_playwright() as p:",
                "        browser = await p.chromium.launch(headless=True)",
                "        context = await browser.new_context(ignore_https_errors=True)",
                "        page = await context.new_page()",
            ]
            for i, flow in enumerate(flows_data):
                req = flow["request"]
                url = req["url"]
                method = req["method"]
                headers = dict(req["headers"])
                headers.pop("Host", None)
                headers.pop("Content-Length", None)
                headers.pop("Content-Encoding", None)
                body = req.get("body")
                flow_obj = self.db.get_flow_object(flow["id"])
                if flow_obj and flow_obj.body:
                    body = flow_obj.body

                code.append(f"        # Step {i + 1}: {method} {url[:60]}")
                code.append(f"        headers_{i} = {json.dumps(headers, indent=12).strip()}")
                kwargs = f"{json.dumps(url)}, method={json.dumps(method)}, headers=headers_{i}"
                if body and body != "<binary data omitted>":
                    code.append(f"        data_{i} = {json.dumps(body)}")
                    kwargs += f", data=data_{i}"
                code.append(f"        try:")
                code.append(f"            response_{i} = await context.request.fetch({kwargs})")
                code.append(f"            print(f'Status: {{response_{i}.status}}')")
                code.append(f"        except Exception as e:")
                code.append(f"            print(f'Error: {{e}}')")
                code.append("")

            code.extend(["        await browser.close()", "", "if __name__ == '__main__':", "    asyncio.run(run_scraper())"])
            return "\n".join(code)

        return f"Framework '{target_framework}' not supported. Use 'curl_cffi' or 'playwright'"

    @staticmethod
    def _normalize_path(path: str):
        segments = path.split("/")
        normalized = []
        params = []
        for seg in segments:
            if not seg:
                normalized.append("")
                continue
            if re.match(r"^\d+$", seg):
                normalized.append("{id}")
                params.append("id")
            elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", seg, re.I):
                normalized.append("{uuid}")
                params.append("uuid")
            elif re.match(r"^[0-9a-f]{24}$", seg, re.I):
                normalized.append("{objectId}")
                params.append("objectId")
            elif len(seg) > 20 and re.match(r"^[a-zA-Z0-9_-]+$", seg):
                normalized.append("{token}")
                params.append("token")
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
            "size": [
                len(ra.get("body") or ""), len(rb.get("body") or "")
            ],
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
        flows = self.db.get_all_for_analysis(lightweight=True)
        if domain:
            flows = [f for f in flows if domain in f["request"]["url"]]

        with self.db._get_conn() as conn:
            conn.row_factory = __import__("sqlite3").Row
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
        # de-dup, preserve order
        seen = set()
        ordered_ids = [x for x in ordered_ids if not (x in seen or seen.add(x))]

        lines: List[str] = []
        lines.append(f"# Evidence Bundle — root flow `{flow_id[:8]}…`")
        lines.append("")
        if chain["tags"]:
            lines.append("**Root tags:** " + ", ".join(f"`{t}`" for t in chain["tags"]))
            lines.append("")
        lines.append(f"**Chain size:** {len(ordered_ids)} flow(s) (depth={depth})")
        lines.append("")

        for fid in ordered_ids:
            data = self.db.get_detail(fid, level="preview")
            if not data:
                continue
            req = data.get("request") or {}
            resp = data.get("response") or {}
            tags = self.db.get_tags(fid)
            findings = self.db.list_findings(flow_id=fid, kind="all", limit=20)
            note = self.db.get_note(fid)

            marker = " (root)" if fid == flow_id else ""
            lines.append(f"## Flow `{fid[:8]}…`{marker}")
            lines.append("")
            lines.append(f"- **{req.get('method')}** `{req.get('url')}`")
            if resp:
                lines.append(f"- Status: `{resp.get('status_code')}`")
            label = None
            with self.db._get_conn() as conn:
                row = conn.execute("SELECT profile_label FROM flows WHERE id = ?", (fid,)).fetchone()
                if row and row[0]:
                    label = row[0]
            if label:
                lines.append(f"- Profile: `{label}`")
            if tags:
                lines.append(f"- Tags: " + ", ".join(f"`{t}`" for t in tags))
            if findings:
                lines.append(f"- Findings:")
                for f in findings:
                    lines.append(f"  - `{f['kind']}/{f['severity']}` **{f['rule_id']}** — {f.get('evidence','')}")
            if note:
                lines.append("")
                lines.append(f"**Triage note** — verdict: `{note['verdict']}`")
                for label_, key in [("Scenario", "scenario"),
                                    ("Sensitive fields", "sensitive_fields"),
                                    ("Test steps", "test_steps"),
                                    ("Conclusion", "conclusion")]:
                    val = note.get(key)
                    if val:
                        lines.append(f"- *{label_}*: {val}")
            lines.append("")
            lines.append("**Request body (preview):**")
            lines.append("```")
            lines.append((req.get("body") or "")[:1000] or "<empty>")
            lines.append("```")
            if resp:
                lines.append("**Response body (preview):**")
                lines.append("```")
                lines.append((resp.get("body") or "")[:1000] or "<empty>")
                lines.append("```")
            lines.append("**Reproduce:**")
            lines.append("```bash")
            lines.append(data.get("curl_command") or "")
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
