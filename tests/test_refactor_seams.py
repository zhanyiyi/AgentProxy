"""Unit tests for the Phase-2 refactor seams and merged-tool semantics.

All pytest-collectable, no live browser/proxy:
  - MitmController fuzz helpers (_classify_fuzz_response, _build_fuzz_request,
    _strip_hop_headers) extracted from the old 125-line fuzz_endpoint
  - TrafficAnalyzer.diff_flows / _json_field_diff (was integration-only)
  - TrafficAnalyzer.evidence_bundle DAG ordering (was integration-only)
"""
import json
import os
import tempfile

import pytest
from mitmproxy.test import tflow

from agent_proxy.core.traffic_db import TrafficDB
from agent_proxy.core.mitm_controller import MitmController
from agent_proxy.core.traffic_analysis import TrafficAnalyzer


@pytest.fixture
def db_path():
    p = os.path.join(tempfile.mkdtemp(), "refactor.db")
    yield p
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(p + suffix)
        except OSError:
            pass


# ---------------- fuzz response classifier ----------------

def test_classify_5xx_is_server_error():
    a = MitmController._classify_fuzz_response("PWNXYZ", 500, b"internal error", 200, 100)
    assert a["anomaly"] == "Server Error (5xx)"
    assert a["reflected"] is False


def test_classify_status_deviation():
    a = MitmController._classify_fuzz_response("p", 403, b"x" * 100, 200, 100)
    assert "Status Code Deviation (200 -> 403)" == a["anomaly"]


def test_classify_length_deviation():
    a = MitmController._classify_fuzz_response("p", 200, b"x" * 200, 200, 100)
    assert a["anomaly"] == "Content Length Deviation (>20%)"


def test_classify_reflection_wins_when_status_matches():
    a = MitmController._classify_fuzz_response("PWN", 200, b"got PWN here" + b"z" * 90, 200, 100)
    assert a["anomaly"] == "Payload Reflected in Response"
    assert a["reflected"] is True


def test_classify_baseline_match_returns_none():
    assert MitmController._classify_fuzz_response("p", 200, b"z" * 100, 200, 100) is None


# ---------------- header stripping ----------------

def test_strip_hop_headers_drops_transport_headers():
    h = MitmController._strip_hop_headers(
        {"Host": "x", "Content-Length": "5", "Content-Encoding": "gzip", "Authorization": "Bearer t"})
    assert "Authorization" in h
    assert "Host" not in h and "Content-Length" not in h and "Content-Encoding" not in h


def test_strip_hop_headers_drops_cookie_only_when_asked():
    base = {"Cookie": "a=b", "X-Keep": "1"}
    assert "Cookie" in MitmController._strip_hop_headers(dict(base))
    assert "Cookie" not in MitmController._strip_hop_headers(dict(base), drop_cookie=True)


# ---------------- json field diff ----------------

def test_json_field_diff_added_removed_changed():
    d = TrafficAnalyzer._json_field_diff(
        {"keep": 1, "gone": 2, "n": {"x": 1}},
        {"keep": 1, "new": 3, "n": {"x": 2}},
    )
    assert "new" in d["added"]
    assert "gone" in d["removed"]
    assert "n.x" in d["changed"]


def test_json_field_diff_list_length():
    d = TrafficAnalyzer._json_field_diff({"a": [1, 2]}, {"a": [1, 2, 3]})
    assert any("len 2->3" in c for c in d["changed"])


# ---------------- diff_flows on real rows ----------------

def _seed(db, url="https://x.test/api", method="GET", status=200, body=b"{}"):
    f = tflow.tflow(resp=True)
    f.request.url = url
    f.request.method = method
    f.response.status_code = status
    f.response.headers["content-type"] = "application/json"
    f.response.content = body
    db.save_flow(f)
    return f.id


def test_diff_flows_reports_status_and_json_diff(db_path):
    db = TrafficDB(db_path)
    a = _seed(db, body=b'{"role": "user"}')
    b = _seed(db, status=200, body=b'{"role": "admin"}')
    out = json.loads(TrafficAnalyzer(db).diff_flows(a, b))
    assert out["status"] == [200, 200]
    assert "role" in out["json_diff"]["changed"]


def test_diff_flows_missing_flow(db_path):
    db = TrafficDB(db_path)
    out = json.loads(TrafficAnalyzer(db).diff_flows("nope", "nope2"))
    assert "error" in out


# ---------------- evidence_bundle DAG ordering ----------------

def test_evidence_bundle_orders_upstream_root_downstream(db_path):
    db = TrafficDB(db_path)
    up = _seed(db, url="https://x.test/login")
    root = _seed(db, url="https://x.test/action")
    down = _seed(db, url="https://x.test/effect")
    db.add_link(up, root, "auth")
    db.add_link(root, down, "trigger")
    db.add_tag(root, "idor_target")
    md = TrafficAnalyzer(db).evidence_bundle(root, depth=2)
    assert "Evidence Bundle" in md
    assert "(root)" in md
    # all three flows present, root carries its tag
    for fid in (up, root, down):
        assert fid[:8] in md
    assert "`idor_target`" in md
