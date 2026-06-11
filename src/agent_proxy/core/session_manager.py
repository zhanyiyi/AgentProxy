import json
import logging
import os
import socket
import time
from typing import Any, Dict, List, Optional

from .mitm_controller import MitmController
from .browser_controller import BrowserController
from ..models import SessionConfig
from ..config import RuleConfig, load_rule_config

logger = logging.getLogger("agent_proxy.session")


class SessionManager:
    def __init__(self, config: Optional[SessionConfig] = None,
                 rule_config: Optional[RuleConfig] = None,
                 user_config_path: Optional[str] = None):
        self.config = config or SessionConfig()
        # Rule pack: explicit > path-loaded > bundled defaults.
        if rule_config is not None:
            self.rules = rule_config
        else:
            self.rules = load_rule_config(user_config_path)
        self.mitm = MitmController(db_path=self.config.db_path, rules=self.rules)
        self.browser = BrowserController(
            proxy_host=self.config.proxy_host,
            proxy_port=self.config.proxy_port,
            headless=self.config.headless,
            ignore_https_errors=self.config.ignore_https_errors,
            timeout=self.config.browser_timeout,
            profile_dir=self.config.profile_dir,
            unsafe_disable_web_security=self.config.unsafe_disable_web_security,
        )
        self._session_active = False
        self._last_mitm_error: Optional[str] = None

    async def _safe_mitm_start(self, port: int) -> Optional[str]:
        """Try to start the mitm proxy. Returns the success string on bind,
        or None on failure (caller renders an error payload). Centralised so
        all three session entry points report port-conflict errors the same
        way."""
        try:
            return await self.mitm.start(port=port, host=self.config.proxy_host)
        except Exception as e:
            logger.error("mitm proxy start failed on port %s: %s", port, e)
            self._last_mitm_error = str(e)
            return None

    def _mitm_start_error_payload(self, port: int, mode: str) -> str:
        return json.dumps({
            "status": "error",
            "mode": mode,
            "error": self._last_mitm_error or "mitmproxy failed to start",
            "proxy_port": port,
            "hint": (
                f"Check whether something else is bound to "
                f"{self.config.proxy_host}:{port} "
                f"(`ss -ltnp 'sport = :{port}'`) or pick a different port."
            ),
        })

    async def start_session(self, proxy_port: Optional[int] = None, headless: Optional[bool] = None, profile_dir: Optional[str] = None, unsafe_disable_web_security: Optional[bool] = None) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        hl = headless if headless is not None else self.config.headless

        self.mitm.port = port
        self.browser.proxy_port = port
        self.browser.headless = hl
        if profile_dir is not None:
            self.browser.profile_dir = profile_dir or None
        if unsafe_disable_web_security is not None:
            self.browser.unsafe_disable_web_security = unsafe_disable_web_security

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="full")
        logger.info("Proxy started: %s", proxy_result)

        try:
            browser_result = await self.browser.start()
            logger.info("Browser started: %s", browser_result)
        except Exception:
            await self.browser.stop()
            await self.mitm.stop()
            raise

        self._session_active = True
        return json.dumps({
            "status": "session_started",
            "proxy": proxy_result,
            "browser": browser_result,
            "proxy_port": port,
            "headless": hl,
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
            "unsafe_disable_web_security": self.browser.unsafe_disable_web_security,
        })

    async def connect_cdp_session(self, endpoint_url: str = "http://127.0.0.1:9222", proxy_port: Optional[int] = None) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        self.mitm.port = port
        self.browser.proxy_port = port

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="cdp")
        logger.info("Proxy started: %s", proxy_result)

        try:
            browser_result = await self.browser.connect_cdp(endpoint_url=endpoint_url)
            logger.info("Browser connected over CDP: %s", browser_result)
        except Exception:
            await self.browser.stop()
            await self.mitm.stop()
            raise

        self._session_active = True
        return json.dumps({
            "status": "session_started",
            "mode": "cdp",
            "proxy": proxy_result,
            "browser": browser_result,
            "proxy_port": port,
            "cdp_endpoint": endpoint_url,
        })

    async def start_mitm_only(self, proxy_port: Optional[int] = None) -> str:
        """Start only the mitmproxy listener — no Playwright browser, no CDP.
        For passive capture from external clients (system Chrome/Firefox, mobile
        device, curl, scripts) that point their HTTP(S) proxy at us. The agent
        keeps full read-only access to traffic via traffic_*/site_map/findings.

        browser_*/browse_and_capture/traffic_replay_via_browser will fail (no
        live page); traffic_replay (curl_cffi) still works."""
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        self.mitm.port = port

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="mitm_only")
        logger.info("Proxy started (browser-less): %s", proxy_result)
        self._session_active = True

        return json.dumps({
            "status": "session_started",
            "mode": "mitm_only",
            "proxy": proxy_result,
            "proxy_port": port,
            "proxy_host": self.config.proxy_host,
            "hint": (
                f"Point browsers / curl / mobile devices at "
                f"http://{self.config.proxy_host}:{port}. For HTTPS, install "
                f"~/.mitmproxy/mitmproxy-ca-cert.pem (see README "
                f"'HTTPS pages load but the address bar shows Not Secure')."
            ),
        })

    async def attach_browser(
        self,
        headless: Optional[bool] = None,
        profile_dir: Optional[str] = None,
        unsafe_disable_web_security: Optional[bool] = None,
        hydrate_host: Optional[str] = None,
    ) -> str:
        """Hot-attach a Playwright browser to an existing mitm-only session.
        The mitm proxy is reused at its current port (no restart, no flow
        loss). Required state: mitm running, browser NOT running.

        Use it to upgrade a passive capture session into an active one
        without losing the flows you've already collected — common when
        you started with the external browser logged in and now want the
        agent to drive a context against the same target.

        Args:
            headless / profile_dir / unsafe_disable_web_security: same
                semantics as session_start; default to the SessionConfig
                values.
            hydrate_host: optional shortcut — after the browser starts,
                hydrate the default context with cookies + auth headers
                from the traffic DB for this host. Equivalent to calling
                browser_hydrate_from_traffic afterwards."""
        if not self._session_active or not self.mitm.running:
            return json.dumps({
                "status": "error",
                "error": (
                    "No active mitm session to attach to. Call "
                    "session_start_proxy_only first, or use session_start "
                    "to do both at once."
                ),
            })
        if self.browser.running:
            return json.dumps({
                "status": "error",
                "error": (
                    "Browser is already running. Use session_stop and a "
                    "fresh session_start if you need to reconfigure it."
                ),
            })

        # Reuse the live mitm port (do NOT restart the proxy).
        self.browser.proxy_port = self.mitm.port
        if headless is not None:
            self.browser.headless = headless
        if profile_dir is not None:
            self.browser.profile_dir = profile_dir or None
        if unsafe_disable_web_security is not None:
            self.browser.unsafe_disable_web_security = unsafe_disable_web_security

        try:
            browser_result = await self.browser.start()
            logger.info("Browser attached: %s", browser_result)
        except Exception as e:
            # Don't drop the mitm — caller can still use it passively.
            await self.browser.stop()
            return json.dumps({
                "status": "error",
                "error": f"browser failed to start: {e}",
                "mitm_still_running": True,
            })

        result: Dict[str, Any] = {
            "status": "browser_attached",
            "browser": browser_result,
            "proxy_port": self.mitm.port,
            "headless": self.browser.headless,
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
        }
        if hydrate_host:
            hydrate_raw = await self.hydrate_browser_from_traffic(host=hydrate_host)
            result["hydrate"] = json.loads(hydrate_raw)
        return json.dumps(result, indent=2)

    async def stop_session(self) -> str:
        if not self._session_active and not self.browser.running and not self.mitm.running:
            return "No active session"

        browser_result = await self.browser.stop()
        proxy_result = await self.mitm.stop()
        self._session_active = False

        return json.dumps({
            "status": "session_stopped",
            "proxy": proxy_result,
            "browser": browser_result,
        })

    async def browse_and_capture(self, url: str, wait_until: str = "domcontentloaded", actions: Optional[List[Dict]] = None) -> str:
        if not self._session_active:
            return "No active session. Use session_start first."

        nav_result = await self.browser.navigate(url, wait_until=wait_until)

        if actions:
            for action in actions:
                action_type = action.get("type")
                if action_type == "click":
                    await self.browser.click(action["selector"])
                elif action_type == "fill":
                    await self.browser.fill(action["selector"], action["value"])
                elif action_type == "wait":
                    import asyncio
                    await asyncio.sleep(action.get("duration", 1))
                elif action_type == "press":
                    await self.browser.press_key(action.get("key", "Enter"))

        traffic = self.mitm.db.get_summary(limit=20)

        return json.dumps({
            "navigation": nav_result if isinstance(nav_result, str) else json.loads(nav_result),
            "captured_requests": len(traffic),
            "recent_traffic": traffic[:10],
        })

    def _proxy_listening(self) -> bool:
        """TCP probe the proxy port. Distinguishes 'we think it's running'
        from 'it's actually accepting connections' — surfaces the case where
        mitmproxy crashed silently or never bound."""
        if not self.mitm.running:
            return False
        try:
            with socket.create_connection((self.config.proxy_host, self.mitm.port), timeout=0.3):
                return True
        except OSError:
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_active": self._session_active,
            "proxy_running": self.mitm.running,
            "proxy_listening": self._proxy_listening(),
            "browser_running": self.browser.running,
            "proxy_port": self.mitm.port,
            "proxy_host": self.config.proxy_host,
            "traffic_count": self.mitm.db.count_flows(),
            "interception_rules": len(self.mitm.interceptor.rules),
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
        }

    async def hydrate_browser_from_traffic(
        self,
        host: str,
        context: str = "default",
        limit: int = 200,
    ) -> str:
        """Seed a live browser context with cookies + auth headers extracted
        from the traffic DB for `host`. Use case: external browser was
        already logged in, mitm captured the session, now we want the
        internal Playwright context to replay against the same target
        without re-doing the login.

        Cookies go into the context (so requests originated from any page
        in the context carry them). Auth headers are injected via a
        host-scoped route handler so they ride ONLY on requests to `host`
        (or its subdomains) — never leaking the credential cross-origin.

        Returns a JSON status payload."""
        if not self.browser.running:
            return json.dumps({
                "status": "error",
                "error": "Browser is not running. Use session_start or session_attach_browser first.",
            })
        ctx = self.browser.contexts.get(context)
        page = self.browser.pages.get(context)
        if ctx is None or page is None:
            return json.dumps({
                "status": "error",
                "error": f"Unknown context '{context}'. Available: {self.browser.list_contexts()}",
            })

        state = self.mitm.db.collect_session_state(host=host, limit=limit)
        if not state["cookies"] and not state["headers"]:
            return json.dumps({
                "status": "no_state_found",
                "host": state["host"],
                "stats": state["stats"],
                "hint": (
                    f"No cookies / auth headers seen for '{host}' in the "
                    f"last {limit} flows. Drive the external browser through "
                    f"a logged-in page first, then retry."
                ),
            })

        injected_cookies = 0
        if state["cookies"]:
            try:
                await ctx.add_cookies(state["cookies"])
                injected_cookies = len(state["cookies"])
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "error": f"add_cookies failed: {e}",
                    "host": state["host"],
                })

        injected_headers = {}
        if state["headers"]:
            try:
                # Host-scoped injection — do NOT use page.set_extra_http_headers,
                # which would attach these credentials to every origin the page
                # touches (cross-origin credential leak).
                await self.browser.add_scoped_auth_headers(
                    context, state["host"], state["headers"]
                )
                injected_headers = state["headers"]
            except Exception as e:
                return json.dumps({
                    "status": "partial",
                    "host": state["host"],
                    "cookies_injected": injected_cookies,
                    "headers_error": str(e),
                })

        return json.dumps({
            "status": "ok",
            "host": state["host"],
            "context": context,
            "cookies_injected": injected_cookies,
            "headers_injected": list(injected_headers.keys()),
            "stats": state["stats"],
        }, indent=2)

    async def replay_via_browser(
        self,
        flow_id: str,
        method: Optional[str] = None,
        headers_override: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout_ms: int = 30000,
        context: str = "default",
    ) -> str:
        """Replay using a named browser context (cookies/session live).
        Cold-hot resolution:
          1. Live context with this name -> use it.
          2. Cold profile_dir/<name>_state.json on disk -> hydrate a fresh context, use it.
          3. Cold profile but no live browser -> curl_cffi + storage_state cookies fallback.
          4. Nothing matches -> plain curl_cffi replay (default identity)."""
        flow_obj = self.mitm.db.get_flow_object(flow_id)
        if not flow_obj:
            return json.dumps({"error": "Flow not found"})
        target_method = (method or flow_obj.method).upper()
        target_headers = dict(flow_obj.headers or {})
        for k in ("Host", "Content-Length", "Content-Encoding", "Cookie"):
            target_headers.pop(k, None)
            target_headers.pop(k.lower(), None)
        if headers_override:
            target_headers.update(headers_override)
        target_body = body if body is not None else flow_obj.body

        # Replay-correlation nonce — stripped by the recorder before forwarding
        # and stored on the captured flow, so we map the result back even under
        # concurrent replays to the same endpoint.
        import uuid as _uuid
        replay_nonce = _uuid.uuid4().hex
        target_headers["X-AgentProxy-Replay"] = replay_nonce

        # Step 1: live context
        ctx_label = context
        if self.browser.running and self.browser._browser is not None:
            if context not in self.browser.contexts:
                # Step 2: try cold hydrate
                hydrated = await self.browser.ensure_context_from_profile(context)
                if not hydrated:
                    return json.dumps({
                        "error": f"context '{context}' has no live session and no saved profile. "
                                 "Login first or use session_create_context.",
                    })
            try:
                before_ts = time.time()
                result = await self.browser.request_fetch(
                    url=flow_obj.url,
                    method=target_method,
                    headers=target_headers,
                    data=target_body,
                    timeout=timeout_ms,
                    context=context,
                )
                # Find the matching captured flow (proxy already labelled it).
                import asyncio as _aio
                new_flow_id = None
                for _ in range(10):
                    new_flow_id = (self.mitm.db.find_replay_match_by_nonce(replay_nonce)
                                   or self.mitm.db.find_replay_match(flow_obj.url, target_method, before_ts))
                    if new_flow_id:
                        break
                    await _aio.sleep(0.1)
                return json.dumps({
                    "via": "browser_context",
                    "context": ctx_label,
                    "status_code": result["status"],
                    "size": result["body_size"],
                    "new_flow_id": new_flow_id,
                    "headers": result["headers"],
                    "body_preview": (result["body"] or "")[:2000],
                }, indent=2)
            except Exception as e:
                return json.dumps({"via": "browser_context", "error": str(e)})

        # Step 3: browser not running, but maybe a saved profile exists
        if self.browser.profile_dir:
            state_path = os.path.join(self.browser.profile_dir, f"{context}_state.json")
            if os.path.exists(state_path):
                return await self.mitm.replay_with_storage_state(
                    flow_id=flow_id,
                    storage_state_path=state_path,
                    method=method,
                    headers=headers_override,
                    body=body,
                    timeout=timeout_ms / 1000.0,
                    context_label=context,
                )

        # Step 4: nothing — fall back to default-identity replay
        return await self.mitm.replay_request(
            flow_id=flow_id, method=method,
            headers=headers_override, body=body,
            timeout=timeout_ms / 1000.0,
        )
