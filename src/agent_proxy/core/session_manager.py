import json
import logging
from typing import Any, Dict, List, Optional

from .mitm_controller import MitmController
from .browser_controller import BrowserController
from ..models import SessionConfig

logger = logging.getLogger("agent_proxy.session")


class SessionManager:
    def __init__(self, config: Optional[SessionConfig] = None):
        self.config = config or SessionConfig()
        self.mitm = MitmController(db_path="agent_proxy_traffic.db")
        self.browser = BrowserController(
            proxy_host=self.config.proxy_host,
            proxy_port=self.config.proxy_port,
            headless=self.config.headless,
            ignore_https_errors=self.config.ignore_https_errors,
            timeout=self.config.browser_timeout,
            profile_dir=self.config.profile_dir,
        )
        self._session_active = False

    async def start_session(self, proxy_port: Optional[int] = None, headless: Optional[bool] = None, profile_dir: Optional[str] = None) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        hl = headless if headless is not None else self.config.headless

        self.mitm.port = port
        self.browser.proxy_port = port
        self.browser.headless = hl
        if profile_dir is not None:
            self.browser.profile_dir = profile_dir or None

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
        }

    async def replay_via_browser(
        self,
        flow_id: str,
        method: Optional[str] = None,
        headers_override: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout_ms: int = 30000,
    ) -> str:
        """Replay using the live browser context — reuses cookies/session naturally.
        Falls back to curl_cffi replay if the browser is not running."""
        if not self.browser.running or not self.browser._context:
            return await self.mitm.replay_request(
                flow_id=flow_id, method=method,
                headers=headers_override, body=body,
                timeout=timeout_ms / 1000.0,
            )
        flow_obj = self.mitm.db.get_flow_object(flow_id)
        if not flow_obj:
            return "Flow not found"
        target_method = (method or flow_obj.method).upper()
        target_headers = dict(flow_obj.headers or {})
        for k in ("Host", "Content-Length", "Content-Encoding", "Cookie"):
            target_headers.pop(k, None)
            target_headers.pop(k.lower(), None)
        if headers_override:
            target_headers.update(headers_override)
        target_body = body if body is not None else flow_obj.body
        try:
            result = await self.browser.request_fetch(
                url=flow_obj.url,
                method=target_method,
                headers=target_headers,
                data=target_body,
                timeout=timeout_ms,
            )
            return json.dumps({
                "via": "browser_context",
                "status": result["status"],
                "size": result["body_size"],
                "headers": result["headers"],
                "body_preview": (result["body"] or "")[:2000],
            }, indent=2)
        except Exception as e:
            return f"Replay via browser failed: {str(e)}"
