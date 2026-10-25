"""Recovery cursors retain uncertainty and never contain action input values."""
import json

from agent_proxy.core.traffic_db import TrafficDB
from agent_proxy.core.workflow_state import CheckpointStore


def test_checkpoint_persists_per_context_and_omits_inputs(tmp_path):
    db = TrafficDB(str(tmp_path / "traffic.db"))
    store = CheckpointStore(db)
    page = {"tab_id": "tab_1", "url": "https://example.test/form", "title": "Form"}
    store.observe(page)
    store.begin({"action": "fill", "selector": "#password", "value": "private-input",
                 "cookies": {"session": "private-cookie"}})
    saved = store.finish({"context": "default", "action_id": "action_1", "action": "fill",
                          "target": "#password", "status": "completed",
                          "action_status": "completed", "page": page})
    store.observe({**page, "tab_id": "tab_2"}, context="other")
    restarted = CheckpointStore(db)
    assert restarted.latest("default") == saved
    assert saved["step"] == 1 and saved["last_action_id"] == "action_1"
    assert restarted.latest()["context"] == "other"
    with db._get_conn() as conn:
        raw = " ".join(row[0] for row in conn.execute("SELECT entry FROM workflow_checkpoints"))
    assert "private-input" not in raw and "private-cookie" not in raw


def test_restart_and_snapshot_do_not_turn_unknown_action_into_success(tmp_path):
    db = TrafficDB(str(tmp_path / "traffic.db"))
    store = CheckpointStore(db)
    store.observe({"tab_id": "tab_3", "url": "https://example.test/submit"})
    store.begin({"action": "click", "target": "button[type=submit]"})
    restarted = CheckpointStore(db)
    checkpoint = restarted.latest("default")
    assert checkpoint["status"] == "needs_review"
    assert checkpoint["action_status"] == "unknown"
    assert checkpoint["error_type"] == "ProcessInterrupted"
    assert checkpoint["step"] == 1 and checkpoint["last_action_id"] is None
    assert restarted.observe({"title": "Submitted"})["status"] == "needs_review"
    acknowledged = restarted.observe({"title": "Submitted"}, status="ready")
    assert acknowledged["action_status"] == "unknown"
    assert acknowledged["action"]["action"] == "click"


def test_dialog_checkpoint_needs_explicit_resolution(tmp_path):
    store = CheckpointStore(TrafficDB(str(tmp_path / "traffic.db")))
    store.begin({"action": "click", "target": "#confirm"})
    checkpoint = store.finish({"action_id": "action_2", "action": "click", "status": "dialog_pending",
                               "action_status": "pending", "dialogs": [{"message": "private-prompt"}]})
    assert checkpoint["status"] == "requires_dialog"
    assert checkpoint["action_status"] == "pending"
    assert "private-prompt" not in json.dumps(checkpoint)
    assert store.observe({"title": "Confirm"})["status"] == "requires_dialog"
    restarted = CheckpointStore(store.db).latest()
    assert restarted["status"] == "needs_review"
    assert restarted["action_status"] == "unknown"


def test_interruption_and_reset_are_context_local(tmp_path):
    store = CheckpointStore(TrafficDB(str(tmp_path / "traffic.db")))
    store.begin({"action": "click", "target": "#next"})
    checkpoint = store.interrupted("CancelledError")
    assert checkpoint["status"] == "needs_review" and checkpoint["action_status"] == "unknown"
    store.observe({"tab_id": "tab_2"}, context="other")
    assert store.reset("default") == 1
    assert store.latest("default") is None
    assert store.latest()["context"] == "other"
    assert store.reset() == 1
    assert store.latest() is None
