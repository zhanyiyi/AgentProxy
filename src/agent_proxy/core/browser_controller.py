import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .browser_events import BrowserEvents

logger = logging.getLogger("agent_proxy.browser")

MITMPROXY_CA_PATH = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")


def _mitmproxy_ca_spki_b64(cert_path: str = MITMPROXY_CA_PATH) -> Optional[str]:
    """base64(SHA256(SubjectPublicKeyInfo DER)) for Chromium's
    --ignore-certificate-errors-spki-list. Returns None if the CA file
    isn't on disk yet (first run before mitmproxy generated it)."""
    if not os.path.exists(cert_path):
        return None
    try:
        # mitmproxy already pulls in `cryptography`; safe to import.
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        spki_der = cert.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(hashlib.sha256(spki_der).digest()).decode("ascii")
    except Exception as e:
        logger.warning("mitmproxy CA SPKI hash failed: %s", e)
        return None


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
        # Host-scoped auth headers per context: {ctx_name: {host: {hdr: val}}}.
        # A single route handler per context consults this map, so repeated
        # hydration of different hosts accumulates rather than shadowing.
        self._scoped_auth: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._scoped_routes: set = set()
        self._console_logs: List[str] = []
        self._console_max = 500
        # CDP connections borrow the browser and its pre-existing contexts.
        # Ownership is recorded as soon as a resource is acquired, before any
        # subsequent initialization can fail.
        self._owns_browser = False
        self._owned_contexts = set()
        self._owned_pages = set()
        self._tabs: Dict[str, Dict[str, Any]] = {}
        self._page_ids = {}
        self._tab_counter = 0
        self._context_handlers = {}
        self._scoped_route_handlers = {}
        self._action_tasks = set()
        self._driver_stop_task = None
        self._action_lock = asyncio.Lock()
        self.download_dir: Optional[str] = None
        self.cleanup_timeout = 5.0
        self.shutdown_timeout = 15.0
        self._events = BrowserEvents(lambda: self.download_dir)
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
        try:
            return await self._start()
        except BaseException:
            try:
                await self.stop()
            except Exception as exc:
                logger.warning("browser_start_cleanup_incomplete error=%s", exc)
            raise

    async def _start(self) -> str:
        if self.running:
            return "Browser already running"

        self._playwright = await async_playwright().start()
        host_display = f"[{self.proxy_host}]" if ":" in self.proxy_host and not self.proxy_host.startswith("[") else self.proxy_host
        proxy_url = f"http://{host_display}:{self.proxy_port}"

        launch_args = [
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        spki = _mitmproxy_ca_spki_b64()
        if spki:
            # Pin Chromium's trust to mitmproxy's CA only — fixes the "Not
            # Secure" lock without globally disabling cert validation.
            launch_args.append(f"--ignore-certificate-errors-spki-list={spki}")
        else:
            # mitmproxy hasn't generated its CA yet (first run, or homedir
            # cleared). Fall back to the blanket bypass so traffic still
            # captures; the lock will read "Not Secure" until the CA is on
            # disk and the browser is restarted.
            launch_args.append("--ignore-certificate-errors")
            logger.warning(
                "mitmproxy CA not found at %s; using --ignore-certificate-errors fallback. "
                "Restart the session once mitmproxy generates the CA for a clean lock.",
                MITMPROXY_CA_PATH,
            )
        if self.unsafe_disable_web_security:
            launch_args.append("--disable-web-security")
            logger.warning("browser launched with --disable-web-security; CORS validation disabled")

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            proxy={"server": proxy_url},
            args=launch_args,
        )
        self._owns_browser = True
        self._track_browser_connection()

        await self._create_named_context("default")
        self.running = True
        logger.info("browser_started proxy=%s headless=%s", proxy_url, self.headless)
        return f"Browser started with proxy {proxy_url} (headless={self.headless})"

    def _track_browser_connection(self):
        browser = self._browser
        def on_disconnected(*_):
            if self._browser is browser:
                self.running = False
                self._events.record("browser_disconnected", owned=self._owns_browser)
        browser.on("disconnected", on_disconnected)

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
        self.contexts[name] = ctx
        self._owned_contexts.add(ctx)
        self._track_context(name, ctx)
        ctx.set_default_timeout(self.timeout)
        # Tag every request from this context so the MITM layer can label flows.
        await ctx.set_extra_http_headers({"X-AgentProxy-Context": name})
        page = await ctx.new_page()
        self._register_page(name, page, owned=True)
        self.pages[name] = page
        return ctx

    def _track_context(self, name: str, ctx: BrowserContext):
        if name in self._context_handlers:
            return
        def on_page(page):
            self._register_page(name, page, owned=ctx in self._owned_contexts)
        ctx.on("page", on_page)
        self._context_handlers[name] = on_page

    def _register_page(self, context: str, page: Page, owned: bool = False) -> str:
        existing = self._page_ids.get(page)
        if existing:
            if owned:
                self._owned_pages.add(page)
                self._tabs[existing]["owned"] = True
            return existing
        self._tab_counter += 1
        tab_id = f"tab_{self._tab_counter}"
        self._page_ids[page] = tab_id
        self._tabs[tab_id] = {"page": page, "context": context, "owned": owned}
        if owned:
            self._owned_pages.add(page)
        self._attach_console(page)
        page.on("dialog", lambda dialog: self._events.on_dialog(dialog, tab_id))
        page.on("download", lambda download: self._events.on_download(download, tab_id))
        def on_close(*_):
            self._tabs.pop(tab_id, None)
            self._page_ids.pop(page, None)
            self._owned_pages.discard(page)
            self._events.drop_tab_dialogs(tab_id)
            if self.pages.get(context) is page:
                replacement = next((tab["page"] for tab in self._tabs.values()
                                    if tab["context"] == context), None)
                if replacement is None:
                    self.pages.pop(context, None)
                else:
                    self.pages[context] = replacement
            self._events.record("tab_closed", tab_id=tab_id, context=context)
        page.on("close", on_close)
        self._events.record("tab_opened", tab_id=tab_id, context=context,
                            url=page.url, owned=owned)
        return tab_id

    async def create_context(self, name: str, from_profile: bool = True) -> str:
        if not self.running or not self._browser:
            return "Browser not started"
        if name in self.contexts:
            return f"Context '{name}' already exists"
        await self._create_named_context(name, from_profile=from_profile)
        return f"Created context '{name}' (active still '{self.active}')"

    async def add_scoped_auth_headers(self, context: str, host: str,
                                      headers: Dict[str, str]) -> int:
        """Inject auth headers ONLY on requests to `host` (or its subdomains).

        Playwright's `set_extra_http_headers` is NOT host-scoped — it attaches
        the given headers to *every* request the page makes, so hydrating with
        a target's `Authorization` / `X-Auth-Token` would leak that credential
        to any third-party origin the page touches (analytics, CDN, an
        attacker-controlled page). This records the headers in a per-context
        host→headers map consulted by ONE route handler, so hydrating multiple
        hosts accumulates instead of shadowing. Returns the number of headers
        that will be injected for this host.
        """
        ctx = self.contexts.get(context)
        if ctx is None or not headers:
            return 0
        host = (host or "").lower().lstrip(".")
        host_map = self._scoped_auth.setdefault(context, {})
        host_map.setdefault(host, {}).update(headers)

        def _headers_for(req_host: str) -> Dict[str, str]:
            req_host = (req_host or "").lower()
            merged: Dict[str, str] = {}
            for h, hdrs in host_map.items():
                if req_host == h or req_host.endswith("." + h):
                    merged.update(hdrs)
            return merged

        # Register the route handler exactly once per context.
        if context not in self._scoped_routes:
            async def _handler(route):
                try:
                    req = route.request
                    req_host = urlsplit(req.url).hostname or ""
                    extra = _headers_for(req_host)
                    if extra:
                        merged = dict(req.headers)  # preserves context tag etc.
                        merged.update(extra)
                        await route.continue_(headers=merged)
                    else:
                        await route.continue_()
                except Exception:
                    # Never let a routing error wedge the page; fall through.
                    try:
                        await route.continue_()
                    except Exception:
                        pass

            await ctx.route("**/*", _handler)
            self._scoped_routes.add(context)
            self._scoped_route_handlers[context] = _handler
        return len(headers)

    def use_context(self, name: str) -> str:
        if name not in self.contexts:
            return f"Unknown context '{name}'. Available: {list(self.contexts)}"
        self.active = name
        return f"Active context now '{name}'"

    def list_contexts(self) -> List[str]:
        return list(self.contexts.keys())

    async def connect_cdp(self, endpoint_url: str = "http://127.0.0.1:9222") -> str:
        try:
            return await self._connect_cdp(endpoint_url)
        except BaseException:
            try:
                await self.stop()
            except Exception as exc:
                logger.warning("browser_cdp_cleanup_incomplete error=%s", exc)
            raise

    async def _connect_cdp(self, endpoint_url: str) -> str:
        if self.running:
            return "Browser already running"

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(endpoint_url, no_defaults=True)
        self._track_browser_connection()

        if self._browser.contexts:
            ctx = self._browser.contexts[0]
        else:
            ctx = await self._browser.new_context(ignore_https_errors=self.ignore_https_errors)
            self._owned_contexts.add(ctx)

        self.contexts["default"] = ctx
        self._track_context("default", ctx)
        ctx.set_default_timeout(self.timeout)
        # Do not overwrite headers of a context borrowed from the user.
        if ctx in self._owned_contexts:
            await ctx.set_extra_http_headers({"X-AgentProxy-Context": "default"})
        pages = ctx.pages
        for existing in pages:
            self._register_page("default", existing, owned=ctx in self._owned_contexts)
        if pages:
            page = pages[0]
        else:
            page = await ctx.new_page()
            self._register_page("default", page, owned=True)
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
        # A failed/cancelled start can hold live resources while running=False.
        # Attempt independent releases even when an earlier release fails.
        cancelled = False
        deadline = time.monotonic() + self.shutdown_timeout
        async def release(label, awaitable, *, driver=False):
            nonlocal cancelled
            remaining = deadline - time.monotonic()
            # Reserve a little of the total budget for stopping the driver,
            # even if an owned context refuses to close.
            if not driver:
                remaining -= min(1.0, self.shutdown_timeout / 4)
            if remaining <= 0:
                if hasattr(awaitable, "close"):
                    awaitable.close()
                elif hasattr(awaitable, "cancel"):
                    awaitable.cancel()
                logger.warning("browser_cleanup_budget_exhausted resource=%s", label)
                return False
            try:
                await asyncio.wait_for(awaitable, timeout=min(self.cleanup_timeout, remaining))
                return True
            except asyncio.CancelledError:
                cancelled = True
            except Exception as exc:
                logger.warning("browser_cleanup_failed resource=%s error=%s", label, exc)
            return False

        self.running = False
        for task in tuple(self._action_tasks):
            task.cancel()
        if self._action_tasks:
            await release("actions", asyncio.gather(*self._action_tasks, return_exceptions=True))
        await release("downloads", self._events.stop())
        if self.profile_dir:
            for name, ctx in list(self.contexts.items()):
                if ctx not in self._owned_contexts:
                    continue
                path = self._storage_state_path(name)
                if path:
                    async def save(ctx=ctx, path=path):
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        await ctx.storage_state(path=path)
                    await release(f"storage_state:{name}", save())
        for name, ctx in list(self.contexts.items()):
            handler = self._scoped_route_handlers.get(name)
            if handler:
                await release(f"route:{name}", ctx.unroute("**/*", handler))
            page_handler = self._context_handlers.get(name)
            if page_handler:
                try:
                    ctx.remove_listener("page", page_handler)
                except Exception as exc:
                    logger.warning("context_listener_cleanup_failed context=%s error=%s", name, exc)
        remote_resources_released = True
        for page in list(self._owned_pages):
            if not any(tab["page"] is page and self.contexts.get(tab["context"]) in self._owned_contexts
                       for tab in self._tabs.values()):
                closed = await release("owned_page", page.close())
                remote_resources_released = closed and remote_resources_released
        for ctx in list(self._owned_contexts):
            closed = await release("owned_context", ctx.close())
            remote_resources_released = closed and remote_resources_released
            if closed:
                self._owned_contexts.discard(ctx)
        if not self._owns_browser and not remote_resources_released:
            # A borrowed browser survives driver shutdown. Keep the connection
            # so a failed close of our own remote resources can be retried.
            if cancelled:
                raise asyncio.CancelledError()
            raise RuntimeError("Owned CDP resources could not be closed; connection retained for retry")
        if self._browser and self._owns_browser:
            await release("owned_browser", self._browser.close())
        driver_stopped = True
        if self._playwright:
            # In CDP mode this disconnects the driver; it does not close the
            # browser or borrowed contexts/pages. Playwright.stop sets its own
            # exit flag before finishing; cancelling it would make a retry look
            # successful without actually waiting for the original cleanup.
            if self._driver_stop_task is None:
                self._driver_stop_task = asyncio.create_task(self._playwright.stop())
                self._driver_stop_task.add_done_callback(
                    lambda task: None if task.cancelled() else task.exception())
            driver_stopped = await release("playwright_driver", asyncio.shield(self._driver_stop_task), driver=True)
        if not driver_stopped:
            # Retain handles so SessionManager can retry a timed-out cleanup.
            if cancelled:
                raise asyncio.CancelledError()
            raise RuntimeError("Browser driver cleanup incomplete; resources retained for retry")
        self.contexts.clear()
        self.pages.clear()
        self._owned_contexts.clear()
        self._owned_pages.clear()
        self._tabs.clear()
        self._page_ids.clear()
        self._context_handlers.clear()
        self._scoped_routes.clear()
        self._scoped_auth.clear()
        self._scoped_route_handlers.clear()
        self._action_tasks.clear()
        self._owns_browser = False
        self.active = "default"
        self._browser = None
        self._playwright = None
        self._driver_stop_task = None
        if cancelled:
            raise asyncio.CancelledError()
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
        try:
            return json.dumps(await self.act("click", selector=selector))
        except Exception as e:
            return f"Click failed: {str(e)}"

    async def fill(self, selector: str, value: str) -> str:
        try:
            return json.dumps(await self.act("fill", selector=selector, value=value))
        except Exception as e:
            return f"Fill failed: {str(e)}"

    async def type_text(self, selector: str, value: str, delay: int = 50) -> str:
        try:
            return json.dumps(await self.act("type", selector=selector, value=value, delay=delay))
        except Exception as e:
            return f"Type failed: {str(e)}"

    async def select_option(self, selector: str, value: str) -> str:
        try:
            return json.dumps(await self.act("select", selector=selector, value=value))
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

    # Cap page-content getters so a single call on a large SPA can't flood the
    # agent's context. Caller can request more, but never unbounded by default.
    MAX_CONTENT_CHARS = 40000

    @classmethod
    def _truncate_content(cls, text: str, max_chars: Optional[int]) -> str:
        limit = cls.MAX_CONTENT_CHARS if max_chars is None else max_chars
        if limit and len(text) > limit:
            return text[:limit] + f"\n...[truncated {len(text) - limit} chars of {len(text)}]"
        return text

    async def get_text(self, selector: Optional[str] = None,
                       max_chars: Optional[int] = None) -> str:
        if not self._page:
            return "Browser not started"
        try:
            if selector:
                text = await self._page.text_content(selector, timeout=self.timeout)
                text = text or ""
            else:
                text = await self._page.inner_text("body")
            return self._truncate_content(text, max_chars)
        except Exception as e:
            return f"Get text failed: {str(e)}"

    async def get_html(self, selector: Optional[str] = None,
                       max_chars: Optional[int] = None) -> str:
        if not self._page:
            return "Browser not started"
        try:
            if selector:
                html = await self._page.inner_html(selector, timeout=self.timeout)
            else:
                html = await self._page.content()
            return self._truncate_content(html, max_chars)
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
        try:
            return json.dumps(await self.act("press", value=key))
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
        try:
            return json.dumps(await self.snapshot(), indent=2, default=str)
        except Exception as e:
            return f"Accessibility tree failed: {str(e)}"

    def _require_page(self) -> Page:
        if not self.running or not self._page:
            raise RuntimeError("Browser not started or active context has no open tab")
        return self._page

    def _tab_info(self, tab_id: str) -> Dict[str, Any]:
        tab = self._tabs.get(tab_id)
        if tab is None:
            raise ValueError(f"Unknown tab: {tab_id}")
        return {"tab_id": tab_id, "context": tab["context"], "url": tab["page"].url,
                "owned": tab["owned"], "active": self._page is tab["page"]}

    def list_tabs(self) -> List[Dict[str, Any]]:
        return [self._tab_info(tab_id) for tab_id in self._tabs]

    async def select_tab(self, tab_id: str) -> Dict[str, Any]:
        self._tab_info(tab_id)  # Validate before changing the active context.
        tab = self._tabs[tab_id]
        self.active = tab["context"]
        self.pages[self.active] = tab["page"]
        self._events.record("tab_selected", tab_id=tab_id, context=self.active)
        return self._tab_info(tab_id)

    async def close_tab(self, tab_id: str) -> Dict[str, Any]:
        info = self._tab_info(tab_id)
        if not info["owned"]:
            raise ValueError("Cannot close a tab borrowed from the user's browser")
        await self._tabs[tab_id]["page"].close()
        return {**info, "status": "closed"}

    async def snapshot(self, frame: Optional[str] = None) -> Dict[str, Any]:
        page = self._require_page()
        tab_id = self._page_ids[page]
        pending = self._events.pending_dialogs(tab_id)
        if pending:
            return {"status": "dialog_pending", "page": self._tab_info(tab_id), "dialogs": pending}
        scope = page.frame_locator(frame) if frame else page
        waiter = self._events.dialog_waiter(tab_id)
        capture = asyncio.create_task(scope.locator("body").aria_snapshot(timeout=self.timeout))
        try:
            await asyncio.wait({capture, waiter}, return_when=asyncio.FIRST_COMPLETED)
            pending = self._events.pending_dialogs(tab_id)
            if pending:
                return {"status": "dialog_pending", "page": self._tab_info(tab_id), "dialogs": pending}
            if not capture.done():
                raise RuntimeError("Browser snapshot interrupted before capture completed")
            aria = await capture
        except Exception as exc:
            raise RuntimeError(f"Browser snapshot failed: {exc}") from exc
        finally:
            waiter.cancel()
            if not capture.done():
                capture.cancel()
            await asyncio.gather(capture, return_exceptions=True)
        return {"status": "ok", "page": self._tab_info(tab_id), "frame": frame,
                "snapshot": self._truncate_content(aria, self.MAX_CONTENT_CHARS),
                "truncated": len(aria) > self.MAX_CONTENT_CHARS}

    async def handle_dialog(self, accept: bool, prompt_text: Optional[str] = None) -> Dict[str, Any]:
        page = self._require_page()
        try:
            return await self._events.handle_dialog(accept, prompt_text, self._page_ids[page])
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Dialog handling failed: {exc}") from exc

    def get_downloads(self) -> List[Dict[str, Any]]:
        return self._events.get_downloads()

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._events.timeline(limit)

    async def act(self, action: str, selector: Optional[str] = None,
                  value: Optional[str] = None, frame: Optional[str] = None,
                  delay: int = 50) -> Dict[str, Any]:
        """Complete a browser primitive or return an explicit pending dialog.

        No wait-for-network heuristic claims that application work has completed.
        Downloads may remain pending and can be queried independently. Values
        entered into controls are deliberately excluded from receipts/events.
        """
        action = action.lower()
        supported = {"click", "fill", "type", "select", "press", "hover", "scroll", "upload"}
        if action not in supported:
            raise ValueError(f"Unsupported browser action: {action}")
        if action in {"click", "fill", "type", "select", "hover", "upload"} and not selector:
            raise ValueError(f"selector is required for {action}")
        if action in {"fill", "type", "select", "press", "upload"} and value is None:
            raise ValueError(f"value is required for {action}")
        async with self._action_lock:
            page = self._require_page()
            tab_id = self._page_ids[page]
            scope = page.frame_locator(frame) if frame else page
            target = scope.locator(selector) if selector else None
            action_id = "action_" + uuid.uuid4().hex[:12]
            timestamp = time.time()
            started = time.monotonic()
            sequence = self._events._sequence
            pending = self._events.pending_dialogs(tab_id)
            status = "dialog_pending" if pending else "completed"
            action_status = "not_started" if pending else "completed"

            async def perform():
                if action == "click":
                    await target.click(timeout=self.timeout)
                elif action == "fill":
                    await target.fill(value, timeout=self.timeout)
                elif action == "type":
                    await target.press_sequentially(value, delay=delay, timeout=self.timeout)
                elif action == "select":
                    await target.select_option(value, timeout=self.timeout)
                elif action == "hover":
                    await target.hover(timeout=self.timeout)
                elif action == "upload":
                    await target.set_input_files(value, timeout=self.timeout)
                elif action == "press":
                    if target:
                        await target.press(value, timeout=self.timeout)
                    else:
                        await page.keyboard.press(value)
                elif target:
                    await target.scroll_into_view_if_needed(timeout=self.timeout)
                else:
                    try:
                        delta = float(value or "600")
                    except ValueError as exc:
                        raise ValueError("scroll value must be a numeric vertical distance") from exc
                    await page.mouse.wheel(0, delta)

            if not pending:
                self._events.action_id = action_id
                self._events.record("action_started", action_id=action_id,
                                    context=self.active, action=action, target=selector, frame=frame)
                waiter = self._events.dialog_waiter(tab_id)
                task = asyncio.create_task(perform())
                self._action_tasks.add(task)
                context_name = self.active
                def on_done(completed):
                    self._action_tasks.discard(completed)
                    if completed.cancelled():
                        completion = "cancelled"
                    else:
                        completion = "failed" if completed.exception() else "completed"
                    # Do not include exception strings: Playwright call logs can
                    # echo values typed into a password or other private field.
                    self._events.record("action_finished", action_id=action_id,
                                        context=context_name, action=action, target=selector,
                                        status=completion)
                task.add_done_callback(on_done)
                try:
                    await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
                    if task.done():
                        try:
                            await task
                        except Exception as exc:
                            raise RuntimeError(f"Browser {action} failed ({type(exc).__name__})") from exc
                    else:
                        action_status = "pending"
                    pending = self._events.pending_dialogs(tab_id)
                    if pending:
                        status = "dialog_pending"
                    await asyncio.sleep(0)  # Let already emitted page/download callbacks register.
                except BaseException:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise
                finally:
                    waiter.cancel()
                    self._events.action_id = None
            observed = [dict(event) for event in self._events.events if event["sequence"] > sequence]
            return {"id": action_id, "action_id": action_id, "timestamp": timestamp,
                    "context": self.active, "action": action, "target": selector,
                    "status": status, "action_status": action_status,
                    "completion_scope": "browser_primitive", "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "page": self._tab_info(tab_id) if tab_id in self._tabs else {"tab_id": tab_id, "closed": True},
                    "dialogs": pending, "downloads": self.get_downloads(),
                    "events": observed, "correlation": "events_observed_during_action_only"}

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
            host_display = f"[{self.proxy_host}]" if ":" in self.proxy_host and not self.proxy_host.startswith("[") else self.proxy_host
            return {
                "running": True,
                "url": self._page.url,
                "title": await self._page.title(),
                "headless": self.headless,
                "proxy": f"http://{host_display}:{self.proxy_port}",
            }
        except Exception:
            return {"running": False, "url": "", "title": ""}
