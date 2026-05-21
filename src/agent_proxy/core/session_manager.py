import json
import logging
import os
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
        self.mitm = MitmController(db_path="agent_proxy_traffic.db", rules=self.rules)
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

        proxy_result = await self.mitm.start(port=port, host=self.config.proxy_host)
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

        proxy_result = await self.mitm.start(port=port, host=self.config.proxy_host)
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

    async def api_discover(self, domain: Optional[str] = None) -> str:
        if not self._session_active:
            return "No active session"
        return self.mitm.get_api_patterns(domain=domain)

    async def security_scan(self, flow_id: str, target_param: str, param_type: str = "query", payload_categories: Optional[List[str]] = None) -> str:
        if not self._session_active:
            return "No active session"

        categories = payload_categories or ["sqli", "xss", "path_traversal"]
        all_results = {}

        for category in categories:
            result = await self.mitm.fuzz_endpoint(
                flow_id=flow_id,
                target_param=target_param,
                param_type=param_type,
                payload_category=category,
            )
            all_results[category] = result

        return json.dumps(all_results, indent=2)

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_active": self._session_active,
            "proxy_running": self.mitm.running,
            "browser_running": self.browser.running,
            "proxy_port": self.mitm.port,
            "traffic_count": len(self.mitm.db.get_summary(limit=9999)),
            "interception_rules": len(self.mitm.interceptor.rules),
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
        }

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
                    new_flow_id = self.mitm.db.find_replay_match(flow_obj.url, target_method, before_ts)
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
