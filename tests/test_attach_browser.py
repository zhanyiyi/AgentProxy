"""Smoke tests for SessionManager.attach_browser — the hot-path that
upgrades a mitm-only session into mitm+browser without restarting the
proxy or losing already-captured flows.

We don't launch real Playwright here — that would couple the test to
chromium binaries and slow it to seconds. Instead we replace
session.browser with a minimal stub that mirrors the BrowserController
surface attach_browser actually touches."""
import asyncio
import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_proxy.core.session_manager import SessionManager


class _StubBrowser:
    """Minimal BrowserController stand-in. Only methods/attributes
    SessionManager.attach_browser / hydrate_browser_from_traffic touch."""
    def __init__(self):
        self.running = False
        self.headless = True
        self.proxy_port = 0
        self.profile_dir = None
        self.unsafe_disable_web_security = False
        self.contexts = {"default": _StubContext()}
        self.pages = {"default": _StubPage()}
        self.active = "default"
        self.fail_on_start = False

    async def start(self):
        if self.fail_on_start:
            raise RuntimeError("simulated browser launch failure")
        self.running = True
        return f"stub browser up (proxy={self.proxy_port}, headless={self.headless})"

    async def stop(self):
        self.running = False
        return "stub browser stopped"

    def list_contexts(self):
        return list(self.contexts.keys())

    async def add_scoped_auth_headers(self, context, host, headers):
        """Mirror BrowserController.add_scoped_auth_headers (host-scoped header
        injection). Records onto the page so the suite's existing assertions
        about page.extra_headers still hold. Returns the count, like the real
        method."""
        page = self.pages.get(context)
        if page is not None and headers:
            page.extra_headers.update(headers)
        return len(headers or {})


class _StubContext:
    def __init__(self):
        self.added_cookies = []

    async def add_cookies(self, cookies):
        self.added_cookies.extend(cookies)


class _StubPage:
    def __init__(self):
        self.extra_headers = {}

    async def set_extra_http_headers(self, headers):
        self.extra_headers = dict(headers)


def _free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


async def _all_tests():
    # ---- attach without an active mitm rejected ----
    sm = SessionManager()
    sm.browser = _StubBrowser()  # type: ignore[assignment]
    raw = await sm.attach_browser()
    payload = json.loads(raw)
    assert payload["status"] == "error"
    assert "No active mitm" in payload["error"]
    print("  [ok] attach without mitm-only → error, no state changes")

    # ---- happy path: mitm-only → attach ----
    sm = SessionManager()
    sm.browser = _StubBrowser()  # type: ignore[assignment]
    port = _free_port()
    raw = await sm.start_mitm_only(proxy_port=port)
    assert json.loads(raw)["status"] == "session_started"
    flows_before = len(sm.mitm.db.get_summary(limit=9999))

    raw_attach = await sm.attach_browser(headless=False)
    payload = json.loads(raw_attach)
    assert payload["status"] == "browser_attached", payload
    assert payload["proxy_port"] == port
    assert payload["headless"] is False
    assert sm.browser.running is True
    assert sm.browser.proxy_port == port, "browser must reuse the live mitm port"
    assert sm.mitm.running is True, "mitm must remain running"
    assert sm._session_active is True
    assert len(sm.mitm.db.get_summary(limit=9999)) == flows_before, \
        "captured flows must not be cleared by attach"
    print("  [ok] attach reuses port, leaves mitm + flows untouched")

    # ---- attach when browser already running rejected ----
    raw = await sm.attach_browser()
    assert json.loads(raw)["status"] == "error"
    print("  [ok] attach refused when browser already running")

    await sm.stop_session()

    # ---- hydrate_host shortcut ----
    sm = SessionManager()
    sm.browser = _StubBrowser()  # type: ignore[assignment]
    # seed db with a flow carrying a cookie before attaching
    import sqlite3
    with sqlite3.connect(sm.mitm.db.db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO flows
               (id, url, method, status_code, request_headers, response_headers, timestamp, size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("seed", "https://target.example.com/x", "GET", 200,
             json.dumps([["Cookie", "session=ABC"], ["Authorization", "Bearer X"]]),
             json.dumps([]), time.time(), 0),
        )
    await sm.start_mitm_only(proxy_port=_free_port())
    raw_attach = await sm.attach_browser(hydrate_host="target.example.com")
    payload = json.loads(raw_attach)
    assert payload["status"] == "browser_attached"
    assert payload["hydrate"]["status"] == "ok"
    assert payload["hydrate"]["cookies_injected"] == 1
    assert "Authorization" in payload["hydrate"]["headers_injected"]
    # verify the stub actually saw the calls
    ctx = sm.browser.contexts["default"]
    page = sm.browser.pages["default"]
    assert any(c["name"] == "session" for c in ctx.added_cookies)
    assert page.extra_headers.get("Authorization") == "Bearer X"
    print("  [ok] hydrate_host shortcut: cookies + headers reach the context/page")

    await sm.stop_session()

    # ---- browser launch fails — mitm survives ----
    sm = SessionManager()
    sm.browser = _StubBrowser()  # type: ignore[assignment]
    sm.browser.fail_on_start = True  # type: ignore[attr-defined]
    await sm.start_mitm_only(proxy_port=_free_port())
    raw = await sm.attach_browser()
    payload = json.loads(raw)
    assert payload["status"] == "error"
    assert payload.get("mitm_still_running") is True
    assert sm.mitm.running is True
    assert sm.browser.running is False
    print("  [ok] browser-start failure preserves the live mitm")

    await sm.stop_session()

    # ---- hydrate without a running browser ----
    sm = SessionManager()
    sm.browser = _StubBrowser()  # type: ignore[assignment]
    raw = await sm.hydrate_browser_from_traffic(host="x")
    payload = json.loads(raw)
    assert payload["status"] == "error"
    assert "Browser is not running" in payload["error"]
    print("  [ok] hydrate without browser running → clear error")


def main():
    asyncio.run(_all_tests())
    print("\n" + "=" * 50)
    print("ALL attach-browser smoke tests PASSED")
    print("=" * 50)


def test_attach_browser_suite_runs():
    """pytest wrapper: non-raising run of the stub-browser suite == pass."""
    main()


if __name__ == "__main__":
    main()
