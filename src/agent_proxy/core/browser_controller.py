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
        unsafe_disable_web_security: bool = False,
    ):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.headless = headless
        self.ignore_https_errors = ignore_https_errors
        self.timeout = timeout
        self.profile_dir = profile_dir
        self.unsafe_disable_web_security = unsafe_disable_web_security
        self._playwright = None
        self._browser: Optional[Browser] = None
        # Multi-context support: each named context is fully isolated (cookies/storage),
        # but shares the same Browser process and proxy. Keeps memory cost low.
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.active: str = "default"
        self._console_logs: List[str] = []
        self._console_max = 500
        self.running = False

    @property
    def _context(self) -> Optional[BrowserContext]:
        return self.contexts.get(self.active)

    @property
    def _page(self) -> Optional[Page]:
        return self.pages.get(self.active)

    def _storage_state_path(self, name: str = "default") -> Optional[str]:
        if not self.profile_dir:
            return None
        return os.path.join(self.profile_dir, f"{name}_state.json")

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

        launch_args = [
            "--ignore-certificate-errors",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        if self.unsafe_disable_web_security:
            launch_args.append("--disable-web-security")
            logger.warning("browser launched with --disable-web-security; CORS validation disabled")

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            proxy={"server": proxy_url},
            args=launch_args,
        )

        await self._create_named_context("default")
        self.running = True
        logger.info("browser_started proxy=%s headless=%s", proxy_url, self.headless)
        return f"Browser started with proxy {proxy_url} (headless={self.headless})"

    async def _create_named_context(self, name: str, from_profile: bool = True) -> BrowserContext:
        """Create a new isolated browser context tagged with X-AgentProxy-Context.
        If profile_dir + <name>_state.json exists and from_profile is True, restore it."""
        ctx_kwargs: Dict[str, Any] = {
            "ignore_https_errors": self.ignore_https_errors,
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        state_path = self._storage_state_path(name)
        if from_profile and state_path and os.path.exists(state_path):
            ctx_kwargs["storage_state"] = state_path
            logger.info("storage_state_loaded context=%s path=%s", name, state_path)

        ctx = await self._browser.new_context(**ctx_kwargs)
        ctx.set_default_timeout(self.timeout)
        # Tag every request from this context so the MITM layer can label flows.
        await ctx.set_extra_http_headers({"X-AgentProxy-Context": name})
        page = await ctx.new_page()
        self._attach_console(page)
        self.contexts[name] = ctx
        self.pages[name] = page
        return ctx

    async def create_context(self, name: str, from_profile: bool = True) -> str:
        if not self.running or not self._browser:
            return "Browser not started"
        if name in self.contexts:
            return f"Context '{name}' already exists"
        await self._create_named_context(name, from_profile=from_profile)
        return f"Created context '{name}' (active still '{self.active}')"

    def use_context(self, name: str) -> str:
        if name not in self.contexts:
            return f"Unknown context '{name}'. Available: {list(self.contexts)}"
        self.active = name
        return f"Active context now '{name}'"

    def list_contexts(self) -> List[str]:
        return list(self.contexts.keys())

    async def connect_cdp(self, endpoint_url: str = "http://127.0.0.1:9222") -> str:
        if self.running:
            return "Browser already running"

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(endpoint_url)

        if self._browser.contexts:
            ctx = self._browser.contexts[0]
        else:
            ctx = await self._browser.new_context(ignore_https_errors=self.ignore_https_errors)

        ctx.set_default_timeout(self.timeout)
        # CDP mode: user manages their own profile via --user-data-dir; we still
        # tag the context so flow labelling stays consistent.
        try:
            await ctx.set_extra_http_headers({"X-AgentProxy-Context": "default"})
        except Exception:
            pass
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()
        self._attach_console(page)
        self.contexts["default"] = ctx
        self.pages["default"] = page
        self.running = True
        logger.info("browser_connected_cdp endpoint=%s", endpoint_url)
        return f"Browser connected over CDP: {endpoint_url}"

    async def save_storage_state(self, name: Optional[str] = None, path: Optional[str] = None) -> str:
        """Snapshot a context's storage_state to disk.
        - name=None  -> snapshot the active context, save to <profile_dir>/<active>_state.json
        - name="foo" with live foo context -> snapshot foo, save to <profile_dir>/foo_state.json
        - name="foo" without live foo context -> snapshot the active context, save to
          <profile_dir>/foo_state.json (handy for "save current state under a new label")
        """
        target_name = name or self.active
        ctx = self.contexts.get(target_name) or self._context
        if not ctx:
            return f"No live context to snapshot (asked '{target_name}')"
        target = path or self._storage_state_path(target_name)
        if not target:
            return "No profile_dir configured and no path supplied"
        os.makedirs(os.path.dirname(target), exist_ok=True)
        await ctx.storage_state(path=target)
        return f"Saved storage state for '{target_name}' to {target}"

    async def stop(self) -> str:
        if not self.running:
            return "Browser is not running"
        try:
            # Best-effort dump of every named context's storage_state
            if self.profile_dir:
                for name, ctx in self.contexts.items():
                    try:
                        path = self._storage_state_path(name)
                        if path:
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            await ctx.storage_state(path=path)
                    except Exception as e:
                        logger.warning("storage_state save failed for '%s': %s", name, e)
            for ctx in list(self.contexts.values()):
                try:
                    await ctx.close()
                except Exception:
                    pass
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error("Error stopping browser: %s", e)
        finally:
            self.contexts.clear()
            self.pages.clear()
            self.active = "default"
            self._browser = None
            self._playwright = None
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
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an HTTP request through a browser context (reuses cookies/session).
        If `context` is None, uses the active one. Returns a dict shape that
        replay_via_browser packages further."""
        ctx = self.contexts.get(context) if context else self._context
        if ctx is None:
            raise RuntimeError(f"Browser context not available (asked: {context!r})")
        kwargs: Dict[str, Any] = {"method": method.upper()}
        if headers:
            kwargs["headers"] = headers
        if data is not None:
            kwargs["data"] = data
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = await ctx.request.fetch(url, **kwargs)
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

    async def ensure_context_from_profile(self, name: str) -> bool:
        """Cold-start: if `name` context isn't live but a state.json exists, hydrate it.
        Returns True iff the context is now available."""
        if name in self.contexts:
            return True
        if not self._browser or not self.profile_dir:
            return False
        path = self._storage_state_path(name)
        if not path or not os.path.exists(path):
            return False
        await self._create_named_context(name, from_profile=True)
        logger.info("context_hydrated name=%s", name)
        return True

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
