"""Smoke tests for TrafficDB.collect_session_state.

Builds a synthetic flow set directly via SQL (so the test doesn't need
mitmproxy HTTPFlow plumbing), then verifies the aggregator picks the
right cookies + auth headers and respects host scoping."""
import json
import os
import sqlite3
import contextlib
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_proxy.core.traffic_db import TrafficDB


def _insert(db_path: str, fid: str, url: str, ts: float,
            req_headers: list[tuple[str, str]],
            resp_headers: list[tuple[str, str]] | None = None,
            method: str = "GET", status: int = 200) -> None:
    """Insert a flow row using the real schema (matches save_flow's writes)."""
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(
            """INSERT OR REPLACE INTO flows
               (id, url, method, status_code, request_headers, response_headers, timestamp, size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fid, url, method, status,
                json.dumps([list(t) for t in req_headers]),
                json.dumps([list(t) for t in (resp_headers or [])]),
                ts, 0,
            ),
        )


def _fresh_db() -> TrafficDB:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    tmp.close()
    db = TrafficDB(tmp.name)
    return db


def test_empty_db_returns_empty_state():
    db = _fresh_db()
    s = db.collect_session_state(host="example.com")
    assert s["host"] == "example.com"
    assert s["cookies"] == []
    assert s["headers"] == {}
    assert s["stats"]["flows_scanned"] == 0
    print("  [ok] empty db → empty state, no errors")


def test_blank_host_handled():
    db = _fresh_db()
    s = db.collect_session_state(host="")
    assert s["host"] == ""
    assert s["cookies"] == [] and s["headers"] == {}
    print("  [ok] blank host short-circuits")


def test_cookie_collected_from_request_header():
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "f1",
        "https://app.example.com/api/me", now,
        req_headers=[
            ("Cookie", "session=abc123; theme=dark"),
            ("Authorization", "Bearer eyJleHAi..."),
        ],
    )
    s = db.collect_session_state(host="app.example.com")
    cookie_names = {c["name"] for c in s["cookies"]}
    assert cookie_names == {"session", "theme"}, s["cookies"]
    sess = next(c for c in s["cookies"] if c["name"] == "session")
    assert sess["value"] == "abc123"
    assert sess["domain"] == "app.example.com"
    assert sess["path"] == "/"
    assert s["headers"].get("Authorization") == "Bearer eyJleHAi..."
    assert s["stats"]["cookie_sources"] == ["request_cookie"]
    print("  [ok] cookie pulled from request header, header preserves case")


def test_set_cookie_used_as_fallback():
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "f1",
        "https://api.example.com/login", now,
        req_headers=[("User-Agent", "test")],
        resp_headers=[
            ("Set-Cookie", "fresh_token=xyz; Domain=example.com; Path=/api; HttpOnly"),
        ],
    )
    s = db.collect_session_state(host="api.example.com")
    assert len(s["cookies"]) == 1
    c = s["cookies"][0]
    assert c["name"] == "fresh_token" and c["value"] == "xyz"
    assert c["domain"] == "example.com"   # honoured from Domain= attribute
    assert c["path"] == "/api"
    assert "response_set_cookie" in s["stats"]["cookie_sources"]
    print("  [ok] Set-Cookie parsed with Domain= and Path= attributes")


def test_last_writer_wins():
    db = _fresh_db()
    base = time.time()
    _insert(
        db.db_path, "f1", "https://app.example.com/a", base,
        req_headers=[("Cookie", "session=OLD")],
    )
    _insert(
        db.db_path, "f2", "https://app.example.com/b", base + 10,
        req_headers=[("Cookie", "session=NEW")],
    )
    s = db.collect_session_state(host="app.example.com")
    sess = next(c for c in s["cookies"] if c["name"] == "session")
    assert sess["value"] == "NEW", sess
    print("  [ok] later flows overwrite earlier values")


def test_host_scoping_excludes_unrelated_subdomains():
    """url LIKE %example.com% would match evil.example.com.attacker.io —
    the parser-level hostname check must exclude it."""
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "leak", "https://example.com.attacker.io/x", now,
        req_headers=[("Cookie", "leaked=oops")],
    )
    _insert(
        db.db_path, "real", "https://example.com/x", now,
        req_headers=[("Cookie", "real=yes")],
    )
    s = db.collect_session_state(host="example.com")
    names = {c["name"] for c in s["cookies"]}
    assert names == {"real"}, names
    print("  [ok] hostname scoping rejects 'example.com.attacker.io'")


def test_subdomain_match_allowed():
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "sub", "https://api.example.com/x", now,
        req_headers=[("Cookie", "k=v")],
    )
    s = db.collect_session_state(host="example.com")
    assert {c["name"] for c in s["cookies"]} == {"k"}
    print("  [ok] subdomain (api.example.com) matches host=example.com")


def test_only_whitelisted_auth_headers():
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "f1", "https://app.example.com/x", now,
        req_headers=[
            ("Authorization", "Bearer A"),
            ("X-CSRF-Token", "B"),
            ("X-Tracking-Id", "C"),  # NOT whitelisted
            ("User-Agent", "x"),
        ],
    )
    s = db.collect_session_state(host="app.example.com")
    assert "Authorization" in s["headers"]
    assert "X-CSRF-Token" in s["headers"]
    assert "X-Tracking-Id" not in s["headers"]
    assert "User-Agent" not in s["headers"]
    print("  [ok] only whitelisted auth headers surfaced")


def test_pathological_inputs_are_safe():
    db = _fresh_db()
    now = time.time()
    _insert(
        db.db_path, "f1", "https://app.example.com/x", now,
        req_headers=[
            ("Cookie", "  =  ; valid=1; "),       # malformed pairs ignored
            ("Authorization", ""),                 # empty value ignored
        ],
    )
    s = db.collect_session_state(host="app.example.com")
    assert {c["name"] for c in s["cookies"]} == {"valid"}
    assert "Authorization" not in s["headers"]
    print("  [ok] malformed cookie pairs and empty headers skipped")


def main():
    test_empty_db_returns_empty_state()
    test_blank_host_handled()
    test_cookie_collected_from_request_header()
    test_set_cookie_used_as_fallback()
    test_last_writer_wins()
    test_host_scoping_excludes_unrelated_subdomains()
    test_subdomain_match_allowed()
    test_only_whitelisted_auth_headers()
    test_pathological_inputs_are_safe()
    print("\n" + "=" * 50)
    print("ALL hydrate (collect_session_state) tests PASSED")
    print("=" * 50)


if __name__ == "__main__":
    main()
