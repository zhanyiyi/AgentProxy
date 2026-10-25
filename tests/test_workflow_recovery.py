"""Recovery binds observations and preserves uncertainty without replaying UI steps."""
import asyncio
import json

import pytest

from agent_proxy.core.session_manager import SessionManager
from agent_proxy.models import SessionConfig


class Browser:
    def __init__(self):
        self.active = "default"
        self.selected = "tab_1"
        self.tabs = [{"tab_id": "tab_1", "context": "default", "url": "http://local.test/form"}]
        self.calls = 0
        self.failure = None
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    def list_tabs(self):
        return [{**tab, "active": tab["tab_id"] == self.selected and tab["context"] == self.active}
                for tab in self.tabs]

    async def select_tab(self, tab_id):
        page = next(tab for tab in self.tabs if tab["tab_id"] == tab_id)
        self.selected, self.active = tab_id, page["context"]
        return {**page, "active": True}

    async def snapshot(self, **kwargs):
        return {"status": "ok", "page": next(tab for tab in self.list_tabs() if tab["active"]),
                "snapshot": "- heading Form"}

    async def navigate(self, url, **kwargs):
        next(tab for tab in self.tabs if tab["tab_id"] == self.selected)["url"] = url
        return json.dumps({"status": "ok", "url": url, "title": "Inspection"})

    async def act(self, action, **kwargs):
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        if self.failure:
            raise self.failure
        return {"id": f"action_{self.calls}", "context": self.active, "action": action,
                "page": next(tab for tab in self.list_tabs() if tab["active"]),
                "status": "completed", "action_status": "completed"}


def manager(tmp_path):
    session = SessionManager(SessionConfig(db_path=str(tmp_path / "traffic.db")))
    session.browser = Browser()
    return session


async def test_missing_binding_selects_unique_live_page_without_actions(tmp_path):
    session = manager(tmp_path)
    await session.remember_browser_page()
    session.browser.tabs = [{"tab_id": "tab_2", "context": "default", "url": "http://local.test/form"}]
    session.browser.selected = None
    snapshot = await session.observe_browser()
    assert snapshot["recovery"]["status"] == "restored"
    assert snapshot["checkpoint"]["tab_id"] == "tab_2"
    assert session.browser.calls == 0
    session.browser.tabs = []
    assert (await session.observe_browser())["status"] == "resume_required"


async def test_unknown_step_survives_observation_and_explicit_navigation(tmp_path):
    original = manager(tmp_path)
    await original.remember_browser_page()
    original.checkpoints.begin({"action": "click", "selector": "#submit", "value": "private"})
    session = manager(tmp_path)
    snapshot = await session.observe_browser()
    assert snapshot["checkpoint"]["status"] == "needs_review"
    await session.navigate_browser("http://local.test/inspect")
    assert session.checkpoints.latest()["action_status"] == "unknown"
    assert session.checkpoints.latest()["status"] == "needs_review"
    blocked = await session.act_browser("click", selector="#continue")
    assert blocked["action_status"] == "not_started" and session.browser.calls == 0
    acknowledged = await session.checkpoint_browser("acknowledge")
    assert acknowledged["checkpoint"]["action_status"] == "unknown"
    await session.act_browser("click", selector="#continue")
    assert session.browser.calls == 1


async def test_failed_operation_is_not_automatically_retried(tmp_path):
    session = manager(tmp_path)
    session.browser.failure = RuntimeError("Page connection closed")
    with pytest.raises(RuntimeError):
        await session.act_browser("fill", selector="#name", value="private-input")
    assert session.checkpoints.latest()["status"] == "needs_review"
    assert "private-input" not in json.dumps(session.checkpoints.latest())
    await session.act_browser("fill", selector="#name", value="private-input")
    assert session.browser.calls == 1
    await session.clear_capture()
    assert session.checkpoints.latest() is None


async def test_rejected_ref_is_known_not_started_and_does_not_require_acknowledgement(tmp_path):
    session = manager(tmp_path)
    perform = session.browser.act

    async def reject(*args, **kwargs):
        raise ValueError("snapshot_id is stale")

    session.browser.act = reject
    with pytest.raises(ValueError, match="stale"):
        await session.act_browser("click", ref="e1", snapshot_id="old")
    checkpoint = session.checkpoints.latest()
    assert checkpoint["status"] == "ready" and checkpoint["action_status"] == "not_started"
    assert session.browser.calls == 0
    session.browser.act = perform
    await session.act_browser("click", selector="#new-target")
    assert session.browser.calls == 1


async def test_tab_switch_waits_for_action_checkpoint(tmp_path):
    session = manager(tmp_path)
    session.browser.tabs.append({"tab_id": "tab_2", "context": "other", "url": "http://local.test/other"})
    session.browser.release.clear()
    operation = asyncio.create_task(session.act_browser("click", selector="#next"))
    await session.browser.entered.wait()
    switch = asyncio.create_task(session.change_browser_tab("select", "tab_2"))
    await asyncio.sleep(0)
    assert not switch.done()
    session.browser.release.set()
    receipt = await operation
    await switch
    assert receipt["context"] == "default"
    assert session.checkpoints.latest("default")["last_action_id"] == "action_1"
    assert session.checkpoints.latest("other")["tab_id"] == "tab_2"


async def test_batched_workflow_stops_at_pending_step(tmp_path):
    session = manager(tmp_path)
    session._session_active = True

    async def pending(*args, **kwargs):
        session.browser.calls += 1
        return {"id": "pending_1", "context": "default", "status": "dialog_pending",
                "action_status": "pending", "dialogs": [{"type": "confirm"}]}

    session.browser.act = pending
    result = json.loads(await session.browse_and_capture(
        "http://local.test/form", actions=[{"type": "click", "selector": "#confirm"},
                                          {"type": "click", "selector": "#submit"}]))
    assert result["status"] == "dialog_pending"
    assert len(result["actions"]) == 1 and session.browser.calls == 1
    assert session.checkpoints.latest()["status"] == "requires_dialog"
