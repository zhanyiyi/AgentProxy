"""Browser ownership and completion contracts without a real Chromium process."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent_proxy.core import browser_controller as module
from agent_proxy.core.browser_controller import BrowserController


class Emitter:
    def __init__(self):
        self.listeners = {}

    def on(self, name, callback):
        self.listeners.setdefault(name, []).append(callback)

    def remove_listener(self, name, callback):
        self.listeners[name].remove(callback)

    def emit(self, name, *args):
        for callback in tuple(self.listeners.get(name, [])):
            callback(*args)


class FakePage(Emitter):
    def __init__(self):
        super().__init__()
        self.url = "https://example.test/page"
        self.closed = False
        self.frame_selector = None
        self.on_click = None
        self.values = []

    def locator(self, selector):
        return self

    def frame_locator(self, selector):
        self.frame_selector = selector
        return self

    async def aria_snapshot(self, **kwargs):
        return '- button "Export"'

    async def click(self, **kwargs):
        if self.on_click:
            await self.on_click()

    async def fill(self, value, **kwargs):
        self.values.append(value)

    async def press_sequentially(self, value, **kwargs):
        self.values.append(value)

    async def close(self):
        self.closed = True
        self.emit("close")


class FakeContext(Emitter):
    def __init__(self, pages=None):
        super().__init__()
        self.pages = pages or []
        self.closed = False
        self.set_extra_http_headers = AsyncMock()

    def set_default_timeout(self, value):
        pass

    async def new_page(self):
        page = FakePage()
        self.pages.append(page)
        self.emit("page", page)
        return page

    async def close(self):
        self.closed = True
        for page in self.pages:
            await page.close()


def active_browser(owned=True):
    browser = BrowserController()
    page = FakePage()
    ctx = FakeContext([page])
    browser.contexts["default"] = ctx
    browser.pages["default"] = page
    if owned:
        browser._owned_contexts.add(ctx)
    browser._track_context("default", ctx)
    browser._register_page("default", page, owned=owned)
    browser.running = True
    return browser, ctx, page


def install_playwright(monkeypatch, remote):
    if not hasattr(remote, "on"):
        events = Emitter()
        remote.on = events.on
        remote.emit = events.emit
    driver = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(return_value=remote),
                                 connect_over_cdp=AsyncMock(return_value=remote)),
        stop=AsyncMock(),
    )
    monkeypatch.setattr(module, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=driver)))
    monkeypatch.setattr(module, "_mitmproxy_ca_spki_b64", lambda: "test")
    return driver


@pytest.mark.asyncio
async def test_failed_start_cleans_resources_before_running_true(monkeypatch):
    remote = SimpleNamespace(close=AsyncMock())
    driver = install_playwright(monkeypatch, remote)
    browser = BrowserController(proxy_host="::1")
    browser._create_named_context = AsyncMock(side_effect=ValueError("invalid state"))
    with pytest.raises(ValueError, match="invalid state"):
        await browser.start()
    remote.close.assert_awaited_once()
    assert driver.chromium.launch.call_args.kwargs["proxy"]["server"] == "http://[::1]:8080"
    driver.stop.assert_awaited_once()
    assert not browser.running and browser._playwright is None
    await browser.stop()  # Cleanup is idempotent.
    driver.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_start_cleans_and_propagates_cancellation(monkeypatch):
    remote = SimpleNamespace(close=AsyncMock())
    driver = install_playwright(monkeypatch, remote)
    browser = BrowserController()
    entered = asyncio.Event()
    async def blocked_context(*args):
        entered.set()
        await asyncio.Future()
    browser._create_named_context = blocked_context
    task = asyncio.create_task(browser.start())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    remote.close.assert_awaited_once()
    driver.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_is_owned_before_page_initialization_can_fail(monkeypatch):
    context = FakeContext()
    context.set_extra_http_headers.side_effect = RuntimeError("setup failed")
    remote = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    driver = install_playwright(monkeypatch, remote)
    browser = BrowserController()
    with pytest.raises(RuntimeError, match="setup failed"):
        await browser.start()
    assert context.closed
    remote.close.assert_awaited_once()
    driver.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_cdp_disconnect_does_not_close_borrowed_browser_or_tabs(monkeypatch):
    page = FakePage()
    context = FakeContext([page])
    remote = SimpleNamespace(contexts=[context], close=AsyncMock())
    driver = install_playwright(monkeypatch, remote)
    browser = BrowserController()
    await browser.connect_cdp()
    with pytest.raises(ValueError, match="borrowed"):
        await browser.close_tab(browser.list_tabs()[0]["tab_id"])
    await browser.stop()
    assert not page.closed and not context.closed
    remote.close.assert_not_awaited()
    driver.stop.assert_awaited_once()
    context.set_extra_http_headers.assert_not_awaited()


@pytest.mark.asyncio
async def test_cdp_created_page_is_owned_but_context_is_borrowed(monkeypatch):
    context = FakeContext()
    remote = SimpleNamespace(contexts=[context], close=AsyncMock())
    install_playwright(monkeypatch, remote)
    browser = BrowserController()
    await browser.connect_cdp()
    assert browser.list_tabs()[0]["owned"]
    await browser.stop()
    assert context.pages[0].closed and not context.closed
    remote.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_driver_stop_reuses_shielded_task_after_timeout():
    browser = BrowserController()
    ready = asyncio.Event()
    async def stop_driver():
        await ready.wait()
    driver = SimpleNamespace(stop=AsyncMock(side_effect=stop_driver))
    browser._playwright = driver
    browser.shutdown_timeout = 0.05
    browser.cleanup_timeout = 0.02
    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        await browser.stop()
    original_task = browser._driver_stop_task
    assert not original_task.done() and not original_task.cancelled()
    ready.set()
    await browser.stop()
    driver.stop.assert_awaited_once()
    assert original_task.done() and browser._playwright is None


@pytest.mark.asyncio
async def test_browser_disconnected_updates_state_without_reconnecting(monkeypatch):
    remote = SimpleNamespace(contexts=[FakeContext([FakePage()])], close=AsyncMock())
    driver = install_playwright(monkeypatch, remote)
    browser = BrowserController()
    await browser.connect_cdp()
    remote.emit("disconnected")
    assert not browser.running
    assert browser.get_timeline(1)[0]["kind"] == "browser_disconnected"
    driver.chromium.connect_over_cdp.assert_awaited_once()
    await browser.stop()


@pytest.mark.asyncio
async def test_snapshot_frame_and_popup_selection_are_explicit():
    browser, context, page = active_browser()
    result = await browser.snapshot(frame="#report-frame")
    assert page.frame_selector == "#report-frame"
    assert result["snapshot"] == '- button "Export"'
    assert "snapshot" in json.loads(await browser.get_accessibility_tree())
    popup = await context.new_page()
    tabs = browser.list_tabs()
    assert len(tabs) == 2 and browser.page is page
    popup_id = next(tab["tab_id"] for tab in tabs if not tab["active"])
    await browser.select_tab(popup_id)
    assert browser.page is popup
    await browser.close_tab(popup_id)
    assert browser.page is page
    await browser.stop()


class FakeDialog:
    type = "confirm"
    message = "Continue?"
    default_value = ""

    def __init__(self):
        self.resolved = asyncio.Event()
        self.accepted = None

    async def accept(self, prompt_text=None):
        self.accepted = True
        self.resolved.set()

    async def dismiss(self):
        self.accepted = False
        self.resolved.set()


@pytest.mark.asyncio
async def test_click_returns_pending_dialog_without_accepting_or_deadlocking():
    browser, _, page = active_browser()
    dialog = FakeDialog()
    async def show_confirm():
        page.emit("dialog", dialog)
        await dialog.resolved.wait()
    page.on_click = show_confirm
    receipt = await asyncio.wait_for(browser.act("click", selector="#confirm"), 1)
    assert receipt["status"] == "dialog_pending"
    assert receipt["action_status"] == "pending" and dialog.accepted is None
    assert (await browser.snapshot())["status"] == "dialog_pending"
    blocked = await browser.act("click", selector="#another")
    assert blocked["action_status"] == "not_started"
    result = await browser.handle_dialog(accept=False)
    assert result["status"] == "dismissed" and dialog.accepted is False
    await asyncio.sleep(0)
    await browser.stop()


@pytest.mark.asyncio
async def test_snapshot_returns_pending_dialog_that_arrives_during_capture():
    browser, _, page = active_browser()
    dialog = FakeDialog()
    async def blocked_snapshot(**kwargs):
        page.emit("dialog", dialog)
        await dialog.resolved.wait()
        return "unreachable while pending"
    page.aria_snapshot = blocked_snapshot
    result = await asyncio.wait_for(browser.snapshot(), 1)
    assert result["status"] == "dialog_pending" and dialog.accepted is None
    await browser.handle_dialog(accept=False)
    await browser.stop()


@pytest.mark.asyncio
async def test_fill_values_do_not_enter_receipts_or_timeline():
    browser, _, page = active_browser()
    secret = "private-form-value-4242"
    receipt = await browser.act("fill", selector="#password", value=secret)
    assert page.values == [secret]
    assert secret not in json.dumps(receipt)
    assert secret not in json.dumps(browser.get_timeline())
    assert receipt["completion_scope"] == "browser_primitive"
    await browser.stop()


@pytest.mark.asyncio
async def test_download_has_pending_and_durable_completed_states(tmp_path):
    browser, _, page = active_browser()
    browser.download_dir = str(tmp_path)
    ready = asyncio.Event()
    class Download:
        url = "https://example.test/export"
        suggested_filename = "../../report.pdf"
        async def save_as(self, destination):
            await ready.wait()
            Path(destination).write_bytes(b"test report")
        async def failure(self):
            return None
    page.emit("download", Download())
    assert browser.get_downloads()[0]["status"] == "pending"
    ready.set()
    await asyncio.gather(*browser._events.download_tasks)
    download = browser.get_downloads()[0]
    assert download["status"] == "completed"
    assert download["size"] == 11 and len(download["sha256"]) == 64
    assert Path(download["saved_path"]).parent == tmp_path
    await browser.stop()


@pytest.mark.asyncio
async def test_download_failure_is_observable(tmp_path):
    browser, _, page = active_browser()
    browser.download_dir = str(tmp_path)
    class Download:
        url = "https://example.test/export"
        suggested_filename = "report.pdf"
        async def save_as(self, destination):
            raise RuntimeError("download interrupted")
    page.emit("download", Download())
    await asyncio.gather(*browser._events.download_tasks)
    assert browser.get_downloads()[0]["status"] == "failed"
    assert "interrupted" in browser.get_downloads()[0]["error"]
    await browser.stop()


@pytest.mark.asyncio
async def test_event_history_is_bounded_and_returned_as_copies():
    browser, _, _ = active_browser()
    for number in range(250):
        browser._events.record("observation", number=number)
    assert len(browser.get_timeline(200)) == 200
    copy = browser.get_timeline(1)
    copy[0]["number"] = -1
    assert browser.get_timeline(1)[0]["number"] == 249
    with pytest.raises(ValueError):
        browser.get_timeline(201)
    await browser.stop()
