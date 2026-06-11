import asyncio
import json
import logging
import os
import re
import socket
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlencode, parse_qsl

import structlog
from mitmproxy import options, http
from mitmproxy.tools.dump import DumpMaster
from curl_cffi.requests import AsyncSession

from ..models import InterceptionRule, ScopeConfig
from ..config import RuleConfig, load_rule_config
from .traffic_db import TrafficDB
from .passive_scan import PassiveScanner
from .flow_writer import FlowWriter
from .traffic_analysis import TrafficAnalyzer

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

    # THREADING INVARIANT: both update_domains (from the scope_set tool) and
    # is_allowed (from the recorder's request/response/error hooks) run on the
    # single MCP asyncio event loop — mitmproxy's DumpMaster is an asyncio task,
    # not a separate thread. The only thing that crosses threads is FlowWriter,
    # and it touches neither scope nor session_variables (only a thread-safe
    # queue.Queue + the WAL'd DB). So scope state needs no lock; a swap of the
    # allowed_domains list reference is atomic under the GIL. If capture is ever
    # moved off the loop into its own thread, revisit this.
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
    def __init__(self, scope: ScopeManager, db: TrafficDB, scanner: Optional[PassiveScanner] = None,
                 writer: Optional["FlowWriter"] = None):
        self.scope = scope
        self.db = db
        self.scanner = scanner or PassiveScanner()
        # Background writer keeps SQLite + passive scan off the event loop.
        # Falls back to inline writes if no writer is wired (e.g. unit tests).
        self.writer = writer

    @staticmethod
    def _pop_internal_header(flow: http.HTTPFlow, name: str) -> Optional[str]:
        """Pop one of our internal X-AgentProxy-* headers before the request
        leaves the proxy, so the target server never sees it."""
        try:
            val = flow.request.headers.pop(name, None)
            if val is None:
                lname = name.lower()
                for hk in list(flow.request.headers.keys()):
                    if hk.lower() == lname:
                        val = flow.request.headers[hk]
                        del flow.request.headers[hk]
                        break
            return val
        except Exception:
            return None

    @classmethod
    def _strip_context_label(cls, flow: http.HTTPFlow) -> Optional[str]:
        """Pop our internal X-AgentProxy-Context header before it leaves the proxy.
        Returned value (if any) is stored as flows.profile_label."""
        return cls._pop_internal_header(flow, "X-AgentProxy-Context")

    def request(self, flow: http.HTTPFlow):
        # Always strip our internal headers so the target server never sees
        # them. This MUST stay inline — it mutates the live request before
        # mitmproxy forwards it.
        label = self._strip_context_label(flow)
        if label:
            flow.metadata["profile_label"] = label
        # Replay correlation nonce — injected by replay tools so we can map the
        # captured flow back to the exact replay (url+method+timestamp is
        # ambiguous under concurrent replays to the same endpoint).
        nonce = self._pop_internal_header(flow, "X-AgentProxy-Replay")
        if nonce:
            flow.metadata["replay_nonce"] = nonce
        if self.scope.is_allowed(flow):
            self._record(flow, scan=False)

    def response(self, flow: http.HTTPFlow):
        if self.scope.is_allowed(flow):
            self._record(flow, scan=True)

    def error(self, flow: http.HTTPFlow):
        if self.scope.is_allowed(flow):
            self._record(flow, scan=False)

    def _record(self, flow: http.HTTPFlow, scan: bool):
        """Offload persistence + scan to the background writer when available,
        otherwise fall back to a synchronous write (keeps tests/embedded use
        working without a running writer)."""
        if self.writer is not None:
            self.writer.submit(flow, scan=scan)
            return
        try:
            self.db.save_flow(flow, profile_label=flow.metadata.get("profile_label"))
            if scan and flow.response is not None:
                self.scanner.scan(flow, self.db)
        except Exception as e:
            logger.error("Failed to save flow: %s", e)


class MitmController:
    def __init__(self, db_path: str = "agent_proxy_traffic.db",
                 rules: Optional[RuleConfig] = None):
        self.master: Optional[DumpMaster] = None
        self.proxy_task: Optional[asyncio.Task] = None
        self.scope_config = ScopeConfig()
        self.scope_manager = ScopeManager(self.scope_config)
        self.db = TrafficDB(db_path)
        self.rules = rules or load_rule_config()
        self._scanner = PassiveScanner(rules=self.rules)
        self.flow_writer = FlowWriter(self.db, self._scanner)
        self.recorder = TrafficRecorder(self.scope_manager, self.db,
                                        scanner=self._scanner,
                                        writer=self.flow_writer)
        self.interceptor = TrafficInterceptor()
        self.analyzer = TrafficAnalyzer(self.db)
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

        # Pre-flight: try to bind the port ourselves and immediately release.
        # mitmproxy's DumpMaster handles bind errors via SystemExit on a
        # background task, which is hostile to error reporting from an MCP
        # tool — so check up front. There's a small TOCTOU window between
        # this check and DumpMaster's own bind, but for the realistic case
        # ("agent already has a server on 8080") it gives a clean error.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind((host, port))
        except OSError as e:
            raise RuntimeError(
                f"cannot bind {host}:{port} ({e}). "
                f"Check `ss -ltnp 'sport = :{port}'` or pick a different port."
            ) from e

        self.port = port
        self.host = host
        opts = options.Options(listen_host=host, listen_port=port)
        self.master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        self.master.addons.add(self.recorder)
        self.master.addons.add(self.interceptor)

        self.proxy_task = asyncio.create_task(self.master.run())

        # Wait until the proxy is actually accepting connections. mitmproxy's
        # bind happens inside an addon coroutine after master.run() starts,
        # so even after create_task returns, listen_addrs() may briefly be
        # empty. Without this poll, callers race the bind and lose traffic.
        ps_addon = self.master.addons.get("proxyserver")
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            if self.proxy_task.done():
                exc = self.proxy_task.exception()
                self.master = None
                self.proxy_task = None
                if exc is not None:
                    raise RuntimeError(f"mitmproxy failed to start on {host}:{port}: {exc}") from exc
                raise RuntimeError(f"mitmproxy exited immediately on {host}:{port}")
            if ps_addon and ps_addon.listen_addrs():
                break
            if asyncio.get_event_loop().time() > deadline:
                self.master.shutdown()
                try:
                    await asyncio.wait_for(self.proxy_task, timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    self.proxy_task.cancel()
                self.master = None
                self.proxy_task = None
                raise RuntimeError(
                    f"mitmproxy did not bind {host}:{port} within 5s"
                )
            await asyncio.sleep(0.05)

        self.running = True
        self.flow_writer.start()
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
        # Proxy has stopped accepting connections; drain any flows still queued
        # in the background writer before returning so nothing is lost.
        self.flow_writer.stop(timeout=5.0)
        logger.info("proxy_stopped",
                    dropped=self.flow_writer.dropped,
                    write_errors=self.flow_writer.write_errors)
        return "Stopped MITM proxy"

    @staticmethod
    def _strip_hop_headers(headers: Dict[str, str], drop_cookie: bool = False) -> Dict[str, str]:
        """Drop headers that must be recomputed by the transport (Host,
        Content-Length, Content-Encoding) and optionally the Cookie header
        (when identity comes from a cookie jar instead)."""
        out = dict(headers or {})
        drop = ["Host", "Content-Length", "Content-Encoding"]
        if drop_cookie:
            drop.append("Cookie")
        for k in drop:
            out.pop(k, None)
            out.pop(k.lower(), None)
        return out

    async def _send_replay(
        self,
        target_url: str,
        target_method: str,
        target_headers: Dict[str, str],
        target_content: Optional[str],
        timeout: float,
        via: str,
        cookies: Optional[Dict[str, str]] = None,
        context_label: Optional[str] = None,
    ) -> str:
        """Shared replay core: inject the correlation nonce, send via curl_cffi
        through our own proxy, poll for the freshly-captured flow id, and (for
        cold/identity replays) backfill profile_label. Both replay_request and
        replay_with_storage_state funnel through here."""
        replay_nonce = uuid.uuid4().hex
        target_headers["X-AgentProxy-Replay"] = replay_nonce
        proxy_url = f"http://{self.host}:{self.port}"
        before_ts = time.time()
        session_kwargs: Dict[str, Any] = {
            "impersonate": "chrome120",
            "proxies": {"http": proxy_url, "https": proxy_url},
            "verify": self._get_verify_param(),
            "timeout": timeout,
        }
        if cookies is not None:
            session_kwargs["cookies"] = cookies
        try:
            async with AsyncSession(**session_kwargs) as client:
                request_kwargs: Dict[str, Any] = {
                    "method": target_method,
                    "url": target_url,
                    "headers": target_headers,
                }
                if target_content is not None:
                    request_kwargs["data"] = target_content
                response = await client.request(**request_kwargs)

            # Give mitmproxy a beat to flush the response into SQLite, then look
            # up the freshly captured flow id so the agent can chain into
            # diff/evidence. Nonce match is exact; url+method+ts is the fallback.
            new_flow_id = None
            for _ in range(10):
                new_flow_id = (self.db.find_replay_match_by_nonce(replay_nonce)
                               or self.db.find_replay_match(target_url, target_method, before_ts))
                if new_flow_id:
                    break
                await asyncio.sleep(0.1)
            # Cold/identity paths can't inject X-AgentProxy-Context (no live
            # browser), so backfill profile_label here.
            if new_flow_id and context_label:
                with self.db._get_conn() as conn:
                    conn.execute("UPDATE flows SET profile_label = ? WHERE id = ?",
                                 (context_label, new_flow_id))
            result: Dict[str, Any] = {
                "via": via,
                "status_code": response.status_code,
                "size": len(response.content) if response.content else 0,
                "new_flow_id": new_flow_id,
            }
            if context_label:
                result["context"] = context_label
            return json.dumps(result)
        except Exception as e:
            logger.error("Replay failed (%s): %s", via, e)
            err: Dict[str, Any] = {"via": via, "error": str(e)}
            return json.dumps(err)

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
        target_headers = self._strip_hop_headers(original_request["headers"])
        if headers:
            target_headers.update(headers)

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

        return await self._send_replay(
            target_url, target_method, target_headers, target_content,
            timeout, via="curl_cffi",
        )

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
        target_headers = self._strip_hop_headers(original.get("headers"), drop_cookie=True)
        if headers:
            target_headers.update(headers)

        # Build cookie dict from storage_state for the matching domain.
        parsed = urlparse(target_url)
        target_host = parsed.hostname or ""
        cookies: Dict[str, str] = {}
        for c in state.get("cookies", []):
            dom = (c.get("domain") or "").lstrip(".")
            if not dom or target_host == dom or target_host.endswith(f".{dom}"):
                cookies[c["name"]] = c["value"]

        target_body = body if body is not None else original.get("body")
        return await self._send_replay(
            target_url, target_method, target_headers, target_body,
            timeout, via="curl_cffi+storage_state",
            cookies=cookies, context_label=context_label,
        )

    def _build_fuzz_request(self, flow_id, original_request, base_url,
                            target_param, param_type, payload):
        """Return (url, body) for one fuzz payload, or (None, error_str) on
        failure. Substitutes `payload` into the named query/json param."""
        if param_type == "query":
            parsed_url = urlparse(base_url)
            qs = parse_qsl(parsed_url.query)
            new_qs = [(k, payload if k == target_param else v) for k, v in qs]
            if target_param not in [k for k, _ in qs]:
                new_qs.append((target_param, payload))
            req_url = parsed_url._replace(query=urlencode(new_qs)).geturl()
            flow_obj = self.db.get_flow_object(flow_id)
            req_body = (flow_obj.body if flow_obj and flow_obj.body
                        else original_request.get("body"))
            return req_url, req_body
        if param_type == "json_body":
            flow_obj = self.db.get_flow_object(flow_id)
            body_content = (flow_obj.body if flow_obj else None) or original_request.get("body", "")
            try:
                if isinstance(body_content, bytes):
                    body_content = body_content.decode("utf-8")
                body_data = json.loads(body_content)
                body_data[target_param] = payload
                return base_url, json.dumps(body_data)
            except Exception as e:
                return None, f"Failed to parse JSON body: {e}"
        return None, "Unknown param_type. Use 'query' or 'json_body'"

    @staticmethod
    def _classify_fuzz_response(payload, status, content, baseline_status, baseline_len):
        """Return an anomaly dict for a fuzz response, or None if it matches
        the baseline. Reflection is the strongest single signal."""
        content = content or b""
        content_len = len(content)
        try:
            reflected = bool(payload) and payload in content.decode("utf-8", errors="replace")
        except Exception:
            reflected = False
        anomaly = None
        if status >= 500:
            anomaly = {"payload": payload, "anomaly": "Server Error (5xx)", "status": status}
        elif status != baseline_status:
            anomaly = {"payload": payload, "anomaly": f"Status Code Deviation ({baseline_status} -> {status})", "status": status}
        elif baseline_len > 0 and abs(content_len - baseline_len) / baseline_len > 0.2:
            anomaly = {"payload": payload, "anomaly": "Content Length Deviation (>20%)", "status": status, "len": content_len}
        if reflected and anomaly is None:
            anomaly = {"payload": payload, "anomaly": "Payload Reflected in Response", "status": status, "len": content_len}
        if anomaly is not None:
            anomaly["reflected"] = reflected
        return anomaly

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
        target_headers = self._strip_hop_headers(original_request["headers"])

        baseline_status, baseline_len = 200, 0
        flow_detail = self.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
        if flow_detail and flow_detail.get("response"):
            baseline_status = flow_detail["response"].get("status_code", 200)
            baseline_len = len(flow_detail["response"].get("body", "") or "")

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
                req_url, req_body = self._build_fuzz_request(
                    flow_id, original_request, base_url, target_param, param_type, payload)
                if req_url is None:
                    return req_body  # error string

                async def run_req(p=payload, u=req_url, b=req_body):
                    try:
                        kwargs = {"method": method, "url": u, "headers": target_headers}
                        if b is not None:
                            kwargs["data"] = b
                        resp = await client.request(**kwargs)
                        return self._classify_fuzz_response(
                            p, resp.status_code, resp.content, baseline_status, baseline_len)
                    except Exception as e:
                        return {"payload": p, "anomaly": f"Request Failed: {str(e)}"}

                tasks.append(run_req())

            for r in await asyncio.gather(*tasks):
                if r:
                    anomalies.append(r)

        if not anomalies:
            return "Fuzzing complete. No significant anomalies detected."
        return json.dumps({
            "baseline_status": baseline_status,
            "baseline_len": baseline_len,
            "anomalies": anomalies,
        }, indent=2)

    # ── Read-only analysis (delegated to TrafficAnalyzer) ──────────────────
    # These all operate purely on the DB; the implementations live in
    # traffic_analysis.py. Thin pass-throughs keep existing call sites working.
    MAX_ANALYSIS_FLOWS = TrafficAnalyzer.MAX_ANALYSIS_FLOWS

    def detect_auth_patterns(self, flow_ids=None):
        return self.analyzer.detect_auth_patterns(flow_ids)

    def extract_from_flow(self, flow_id, json_path=None, css_selector=None):
        return self.analyzer.extract_from_flow(flow_id, json_path=json_path, css_selector=css_selector)

    def get_api_patterns(self, domain=None, limit=None):
        return self.analyzer.get_api_patterns(domain=domain, limit=limit)

    def export_openapi_spec(self, domain=None, limit=None):
        return self.analyzer.export_openapi_spec(domain=domain, limit=limit)

    def generate_scraper_code(self, flow_ids, target_framework="curl_cffi"):
        return self.analyzer.generate_scraper_code(flow_ids, target_framework=target_framework)

    def diff_flows(self, flow_a, flow_b, max_lines=50):
        return self.analyzer.diff_flows(flow_a, flow_b, max_lines=max_lines)

    def site_map(self, domain=None):
        return self.analyzer.site_map(domain=domain)

    def evidence_bundle(self, flow_id, depth=3):
        return self.analyzer.evidence_bundle(flow_id, depth=depth)

    def correlate_dataflow(self, limit=None, freq_cap=8, max_edges=200):
        return self.analyzer.correlate_dataflow(limit=limit, freq_cap=freq_cap, max_edges=max_edges)
