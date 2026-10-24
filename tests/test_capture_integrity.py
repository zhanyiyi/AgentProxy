"""Capture storage regressions using detached snapshots; no browser or network."""
import hashlib
import json
import sqlite3
from pathlib import Path

from mitmproxy.test import tflow

from agent_proxy.core.flow_writer import FlowSnapshot
from agent_proxy.core.traffic_analysis import TrafficAnalyzer
from agent_proxy.core.traffic_db import MAX_BODY_BYTES, TrafficDB


def captured(db, url="https://example.com/report", content=b"ok", content_type="text/plain"):
    flow = tflow.tflow(resp=True)
    flow.request.url = url
    flow.response.headers["content-type"] = content_type
    flow.response.content = content
    db.save_flow(FlowSnapshot(flow))
    return flow.id


def test_snapshot_charset_and_duplicate_headers(tmp_path):
    db = TrafficDB(str(tmp_path / "capture.db"))
    flow = tflow.tflow(resp=True)
    flow.response.headers["content-type"] = 'text/plain; charset="gb18030"'
    flow.response.headers.add("Set-Cookie", "first=1")
    flow.response.headers.add("Set-Cookie", "second=2")
    flow.response.content = "导出完成".encode("gb18030")
    db.save_flow(FlowSnapshot(flow))
    detail = db.get_detail(flow.id, level="full")
    assert detail["response"]["body"] == "导出完成"
    assert detail["response"]["body_charset"] == "gb18030"
    assert [v for k, v in detail["response"]["headers_raw"] if k.lower() == "set-cookie"] == ["first=1", "second=2"]
    assert isinstance(detail["response"]["headers"], dict)


def test_preview_reports_storage_truncation_too(tmp_path):
    db = TrafficDB(str(tmp_path / "capture.db"))
    fid = captured(db, content=b"x" * (MAX_BODY_BYTES + 20))
    response = db.get_detail(fid, level="preview", body_preview_length=10)["response"]
    assert response["body"] == "x" * 10
    assert response["body_truncated"] is True
    assert response["body_notes"] == ["preview_truncated", "stored_truncated_256kb"]
    assert db.get_detail(fid, level="meta")["response"]["body_truncated"] is True


def test_artifact_capture_limits_and_path_safety(tmp_path, monkeypatch):
    from agent_proxy.core import artifact_store

    db = TrafficDB(str(tmp_path / "capture.db"))
    payload = b"%PDF-test\x00binary"
    flow = tflow.tflow(resp=True)
    flow.id = "../../escape"
    flow.response.headers["content-type"] = "application/pdf"
    flow.response.headers["content-disposition"] = 'attachment; filename="../../bad.pdf"'
    flow.response.content = payload
    db.save_flow(FlowSnapshot(flow))
    response = db.get_detail(flow.id, level="meta")["response"]
    info = response["artifact"]
    path = Path(info["path"])
    assert path.parent == tmp_path / "capture.db.artifacts"
    assert path.read_bytes() == payload
    assert info["sha256"] == hashlib.sha256(payload).hexdigest()
    assert info["size"] == len(payload)
    assert info["omitted"] is None

    monkeypatch.setattr(artifact_store, "MAX_ARTIFACT_BYTES", 4)
    fid = captured(db, content=b"12345", content_type="application/zip")
    info = db.get_detail(fid)["response"]["artifact"]
    assert info["omitted"] == "size_limit_exceeded"
    assert info["path"] is None
    assert info["size"] == 5


def test_literal_search_and_hostname_filters_before_limit(tmp_path):
    db = TrafficDB(str(tmp_path / "capture.db"))
    first = captured(db, "https://example.com/real?value=100%_done")
    child = captured(db, "https://api.example.com/child")
    captured(db, "https://unrelated.test/path/example.com?value=100xxdone")
    captured(db, "https://example.com.unrelated.test/decoy")
    assert [r["id"] for r in db.search(query="%_done")] == [first]
    assert {r["id"] for r in db.search(domain="EXAMPLE.com")} == {first, child}
    assert len(db.search(domain="example.com", limit=1)) == 1
    analyzer = TrafficAnalyzer(db)
    assert {h["host"] for h in json.loads(analyzer.site_map("example.com"))} == {"example.com", "api.example.com"}
    patterns = json.loads(analyzer.get_api_patterns("example.com"))
    assert sum(p["request_count"] for p in patterns) == 2


def test_legacy_database_migration_and_action_journal(tmp_path):
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE flows (id TEXT PRIMARY KEY, url TEXT, method TEXT, status_code INTEGER, request_headers TEXT, request_body TEXT, response_headers TEXT, response_body TEXT, timestamp REAL, size INTEGER)")
        conn.execute("INSERT INTO flows VALUES ('old','https://example.com','GET',200,'{}',NULL,'{}','old',1,3)")
    db = TrafficDB(path)
    assert db.get_detail("old")["response"]["body"] == "old"
    assert db.get_detail("old")["response"]["artifact"] is None
    entry = {"action_id": "action-1", "action": "click", "context": "default", "page": {"url": "https://example.com"}, "events": [], "status": "completed"}
    saved = db.save_action(entry)
    assert saved["action_id"] == "action-1"
    assert saved["id"] == "action-1"
    assert db.list_actions(1) == [saved]
    saved["status"] = "pending_dialog"
    assert db.save_action(saved)["status"] == "pending_dialog"
    assert len(db.list_actions()) == 1
    db.clear()
    assert db.list_actions() == []
