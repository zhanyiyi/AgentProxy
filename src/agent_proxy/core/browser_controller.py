import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("agent_proxy.browser")


class BrowserController:
    def __init__(
        self,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 8080,
        headless: bool = True,
        ignore_https_errors: bool = True,
        timeout: int = 30000,
        profile_dir: Optional[str] = None,
    ):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.headless = headless
        self.ignore_https_errors = ignore_https_errors
        self.timeout = timeout
        self.profile_dir = profile_dir
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._console_logs: List[str] = []
        self._console_max = 500
        self.running = False

    def _storage_state_path(self) -> Optional[str]:
        if not self.profile_dir:
            return None
        return os.path.join(self.profile_dir, "state.json")

    def _attach_console(self, page: Page):
        def _on_console(msg):
            try:
                self._console_logs.append(f"[{msg.type}] {msg.text}")
                if len(self._console_logs) > self._console_max:
                    del self._console_logs[: -self._console_max]
            except Exception:
                pass
        page.on("console", _on_console)

    async def start(self) -> str:
        if self.running:
            return "Browser already running"

        self._playwright = await async_playwright().start()
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            proxy={"server": proxy_url},
            args=[
                "--ignore-certificate-errors",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        ctx_kwargs: Dict[str, Any] = {
            "ignore_https_errors": self.ignore_https_errors,
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        state_path = self._storage_state_path()
        if state_path and os.path.exists(state_path):
            ctx_kwargs["storage_state"] = state_path
            logger.info("browser_storage_state_loaded path=%s", state_path)

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(self.timeout)
        self._page = await self._context.new_page()
        self._attach_console(self._page)
        self.running = True
        logger.info("browser_started proxy=%s headless=%s", proxy_url, self.headless)
        return f"Browser started with proxy {proxy_url} (headless={self.headless})"

    async def connect_cdp(self, endpoint_url: str = "http://127.0.0.1:9222") -> str:
        if self.running:
            return "Browser already running"

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(endpoint_url)

        if self._browser.contexts:
            self._context = self._browser.contexts[0]
        else:
            self._context = await self._browser.new_context(ignore_https_errors=self.ignore_https_errors)

        self._context.set_default_timeout(self.timeout)

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        self._attach_console(self._page)
        self.running = True
        logger.info("browser_connected_cdp endpoint=%s", endpoint_url)
        return f"Browser connected over CDP: {endpoint_url}"

    async def save_storage_state(self, path: Optional[str] = None) -> str:
        if not self._context:
            return "Browser not started"
        target = path or self._storage_state_path()
        if not target:
            return "No profile_dir configured and no path supplied"
        os.makedirs(os.path.dirname(target), exist_ok=True)
        await self._context.storage_state(path=target)
        return f"Saved storage state to {target}"

    async def stop(self) -> str:
        if not self.running:
            return "Browser is not running"
        try:
            state_path = self._storage_state_path()
            if state_path and self._context:
                try:
                    os.makedirs(os.path.dirname(state_path), exist_ok=True)
                    await self._context.storage_state(path=state_path)
                except Exception as e:
                    logger.warning("storage_state save failed: %s", e)
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error("Error stopping browser: %s", e)
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None
            self.running = False
        return "Browser stopped"

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> str:
        if not self._page:
            return "Browser not started. Use session_start first."
        try:
            response = await self._page.goto(url, wait_until=wait_until, timeout=self.timeout)
            title = await self._page.title()
            status = response.status if response else "N/A"
            return json.dumps({
                "status": "ok",
                "url": self._page.url,
                "title": title,
                "http_status": status,
            })
        except Exception as e:
            return f"Navigation failed: {str(e)}"

    async def click(self, selector: str) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.click(selector, timeout=self.timeout)
            return f"Clicked: {selector}"
        except Exception as e:
            return f"Click failed: {str(e)}"

    async def fill(self, selector: str, value: str) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.fill(selector, value, timeout=self.timeout)
            return f"Filled: {selector} = {value[:50]}"
        except Exception as e:
            return f"Fill failed: {str(e)}"

    async def type_text(self, selector: str, value: str, delay: int = 50) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.type(selector, value, delay=delay, timeout=self.timeout)
            return f"Typed into: {selector}"
        except Exception as e:
            return f"Type failed: {str(e)}"

    async def select_option(self, selector: str, value: str) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.select_option(selector, value, timeout=self.timeout)
            return f"Selected: {selector} = {value}"
        except Exception as e:
            return f"Select failed: {str(e)}"

    async def screenshot(self, full_page: bool = False) -> str:
        if not self._page:
            return "Browser not started"
        try:
            screenshot_bytes = await self._page.screenshot(full_page=full_page)
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            return f"Screenshot failed: {str(e)}"

    async def get_text(self, selector: Optional[str] = None) -> str:
        if not self._page:
            return "Browser not started"
        try:
            if selector:
                text = await self._page.text_content(selector, timeout=self.timeout)
                return text or ""
            else:
                return await self._page.inner_text("body")
        except Exception as e:
            return f"Get text failed: {str(e)}"

    async def get_html(self, selector: Optional[str] = None) -> str:
        if not self._page:
            return "Browser not started"
        try:
            if selector:
                return await self._page.inner_html(selector, timeout=self.timeout)
            else:
                return await self._page.content()
        except Exception as e:
            return f"Get HTML failed: {str(e)}"

    async def execute_js(self, script: str) -> str:
        if not self._page:
            return "Browser not started"
        try:
            result = await self._page.evaluate(script)
            return json.dumps(result, default=str)
        except Exception as e:
            return f"JS execution failed: {str(e)}"

    async def press_key(self, key: str) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.keyboard.press(key)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key press failed: {str(e)}"

    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.wait_for_selector(selector, timeout=timeout or self.timeout)
            return f"Selector found: {selector}"
        except Exception as e:
            return f"Wait failed: {str(e)}"

    async def get_cookies(self) -> str:
        if not self._context:
            return "Browser not started"
        try:
            cookies = await self._context.cookies()
            return json.dumps(cookies, indent=2)
        except Exception as e:
            return f"Get cookies failed: {str(e)}"

    async def set_cookies(self, cookies: List[Dict]) -> str:
        if not self._context:
            return "Browser not started"
        try:
            await self._context.add_cookies(cookies)
            return f"Set {len(cookies)} cookie(s)"
        except Exception as e:
            return f"Set cookies failed: {str(e)}"

    async def get_url(self) -> str:
        if not self._page:
            return "Browser not started"
        return self._page.url

    async def get_title(self) -> str:
        if not self._page:
            return "Browser not started"
        try:
            return await self._page.title()
        except Exception:
            return ""

    async def go_back(self) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.go_back(timeout=self.timeout)
            return f"Went back to: {self._page.url}"
        except Exception as e:
            return f"Go back failed: {str(e)}"

    async def go_forward(self) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.go_forward(timeout=self.timeout)
            return f"Went forward to: {self._page.url}"
        except Exception as e:
            return f"Go forward failed: {str(e)}"

    async def reload(self) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.reload(timeout=self.timeout)
            return f"Reloaded: {self._page.url}"
        except Exception as e:
            return f"Reload failed: {str(e)}"

    async def get_accessibility_tree(self) -> str:
        if not self._page:
            return "Browser not started"
        try:
            snapshot = await self._page.accessibility.snapshot()
            return json.dumps(snapshot, indent=2, default=str)
        except Exception as e:
            return f"Accessibility tree failed: {str(e)}"

    async def get_console_logs(self, clear: bool = False) -> str:
        if not self.running:
            return "Browser not started"
        try:
            logs = list(self._console_logs)
            if clear:
                self._console_logs.clear()
            return json.dumps(logs, indent=2)
        except Exception as e:
            return f"Console logs failed: {str(e)}"

    async def request_fetch(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send an HTTP request through the live browser context (reuses cookies/session)."""
        if not self._context:
            raise RuntimeError("Browser context not available")
        kwargs: Dict[str, Any] = {"method": method.upper()}
        if headers:
            kwargs["headers"] = headers
        if data is not None:
            kwargs["data"] = data
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = await self._context.request.fetch(url, **kwargs)
        body_bytes = await resp.body()
        body_text: Optional[str]
        try:
            body_text = body_bytes.decode("utf-8", errors="replace")
        except Exception:
            body_text = None
        return {
            "status": resp.status,
            "headers": dict(resp.headers),
            "body": body_text,
            "body_size": len(body_bytes) if body_bytes else 0,
        }

    async def set_extra_http_headers(self, headers: Dict[str, str]) -> str:
        if not self._page:
            return "Browser not started"
        try:
            await self._page.set_extra_http_headers(headers)
            return f"Set extra headers: {list(headers.keys())}"
        except Exception as e:
            return f"Set headers failed: {str(e)}"

    async def set_offline(self, offline: bool = True) -> str:
        if not self._context:
            return "Browser not started"
        try:
            await self._context.set_offline(offline)
            return f"Browser offline: {offline}"
        except Exception as e:
            return f"Set offline failed: {str(e)}"

    async def get_status(self) -> Dict[str, Any]:
        if not self.running or not self._page:
            return {"running": False, "url": "", "title": ""}
        try:
            return {
                "running": True,
                "url": self._page.url,
                "title": await self._page.title(),
                "headless": self.headless,
                "proxy": f"http://{self.proxy_host}:{self.proxy_port}",
            }
        except Exception:
            return {"running": False, "url": "", "title": ""}
