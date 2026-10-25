"""Delivered snapshot versions, native refs, and document invalidation."""
import pytest

from agent_proxy.core.browser_controller import BrowserController
from agent_proxy.core.browser_snapshot import SnapshotStore


def test_delta_reconstructs_current_refs_and_rejects_old_versions():
    store = SnapshotStore()
    unchanged = '\n'.join(f'- paragraph: Stable row {number}' for number in range(20))
    first = store.render("tab_1", None,
                         unchanged + '\n- button "Keep" [ref=e1]\n- button "Old" [ref=e2]', True, 40000)
    second = store.render("tab_1", None,
                          unchanged + '\n- button "Keep" [ref=e1]\n- button "New" [ref=e3]', True, 40000)
    assert first["kind"] == "full"
    assert second["kind"] == "delta" and second["base_snapshot_id"] == first["snapshot_id"]
    assert '- button "Old" [ref=e2]' in second["snapshot"]
    assert '+- button "New" [ref=e3]' in second["snapshot"]
    store.validate_ref("tab_1", None, second["snapshot_id"], "e1")
    with pytest.raises(ValueError, match="stale"):
        store.validate_ref("tab_1", None, first["snapshot_id"], "e1")
    with pytest.raises(ValueError, match="not delivered"):
        store.validate_ref("tab_1", None, second["snapshot_id"], "e2")


def test_truncation_only_authorizes_complete_delivered_nodes_and_resets_baseline():
    store = SnapshotStore()
    text = '- button "Shown" [ref=e1]\n- button "' + "Long name " * 12 + '" [ref=e2]'
    first = store.render("tab_1", None, text, True, 70)
    assert first["truncated"] and first["ref_count"] == 1
    store.validate_ref("tab_1", None, first["snapshot_id"], "e1")
    with pytest.raises(ValueError, match="not delivered"):
        store.validate_ref("tab_1", None, first["snapshot_id"], "e2")
    second = store.render("tab_1", None, '- button "Shown" [ref=e1]', True, 70)
    assert second["kind"] == "full" and second["base_snapshot_id"] is None


def test_scopes_are_independent_bounded_and_ref_text_in_names_is_not_metadata():
    store = SnapshotStore(max_scopes=2)
    text = '- button "Fake [ref=e99]" [ref=e1]\n- text: button "Fake" [ref=e98]'
    first = store.render("tab_1", None, text, True, 40000)
    assert first["ref_count"] == 1
    inner = store.render("tab_1", "#frame", '- button "Inner" [ref=f1e2]', True, 40000)
    assert inner["kind"] == "full"
    store.render("tab_2", None, '- button "Other" [ref=e1]', True, 40000)
    with pytest.raises(ValueError, match="stale"):
        store.validate_ref("tab_1", None, first["snapshot_id"], "e1")
    store.drop_tab("tab_1")
    with pytest.raises(ValueError, match="stale"):
        store.validate_ref("tab_1", "#frame", inner["snapshot_id"], "f1e2")


class Page:
    url = "https://example.test/workflow"

    def __init__(self):
        self.listeners = {}
        self.text = '- button "Next" [ref=f2e7]'
        self.selectors = []
        self.clicks = 0
        self.attached = True
        self.capture_options = None

    def on(self, name, callback):
        self.listeners.setdefault(name, []).append(callback)

    def emit(self, name, *args):
        for callback in self.listeners.get(name, []):
            callback(*args)

    def locator(self, selector):
        self.selectors.append(selector)
        return self

    def frame_locator(self, selector):
        return self

    async def aria_snapshot(self, **kwargs):
        self.capture_options = kwargs
        return self.text

    async def count(self):
        return int(self.attached)

    async def click(self, **kwargs):
        self.clicks += 1


def active_browser():
    browser, page = BrowserController(), Page()
    browser.pages["default"] = page
    browser._register_page("default", page)
    browser.running = True
    return browser, page


@pytest.mark.asyncio
async def test_ref_action_uses_native_frame_routing_and_same_url_navigation_invalidates():
    browser, page = active_browser()
    snapshot = await browser.snapshot(frame="#outer")
    assert page.capture_options["mode"] == "ai"
    receipt = await browser.act("click", ref="f2e7", snapshot_id=snapshot["snapshot_id"], frame="#outer")
    assert page.selectors[-1] == "aria-ref=f2e7" and page.clicks == 1
    assert receipt["target"] == "f2e7" and receipt["snapshot_id"] == snapshot["snapshot_id"]
    page.emit("framenavigated", object())  # The URL deliberately stays unchanged.
    with pytest.raises(ValueError, match="stale"):
        await browser.act("click", ref="f2e7", snapshot_id=snapshot["snapshot_id"], frame="#outer")
    fresh = await browser.snapshot(frame="#outer")
    assert fresh["kind"] == "full"
    page.attached = False
    with pytest.raises(ValueError, match="detached"):
        await browser.act("click", ref="f2e7", snapshot_id=fresh["snapshot_id"], frame="#outer")
    assert page.clicks == 1


@pytest.mark.asyncio
async def test_capture_interrupted_by_navigation_never_seeds_a_baseline():
    browser, page = active_browser()

    async def navigating_capture(**kwargs):
        page.emit("framenavigated", object())
        return page.text

    page.aria_snapshot = navigating_capture
    with pytest.raises(RuntimeError, match="navigated during capture"):
        await browser.snapshot()
    assert not browser._snapshots._latest


@pytest.mark.asyncio
async def test_ref_and_selector_validation_happens_before_any_action():
    browser, page = active_browser()
    with pytest.raises(ValueError, match="mutually exclusive"):
        await browser.act("click", selector="#next", ref="e1", snapshot_id="old")
    with pytest.raises(ValueError, match="snapshot_id is required"):
        await browser.act("click", ref="e1")
    assert page.clicks == 0
