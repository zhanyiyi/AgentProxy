"""Smoke tests for the browser-less / passive mitm-only mode.

Verifies:
- start_mitm_only fires the proxy and sets _session_active.
- The browser stays off — that's the whole point.
- session_status reports the right shape, including proxy_listening.
- Calling start_mitm_only twice is rejected (same guard as start_session).
- Port-conflict produces a structured error, leaves _session_active False.
- stop_session brings the proxy down without touching a non-existent browser.
"""
import asyncio
import json
import os
import socket
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_proxy.core.session_manager import SessionManager


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def _run():
    sm = SessionManager()
    port = _free_port()

    # ---- start ----
    raw = await sm.start_mitm_only(proxy_port=port)
    payload = json.loads(raw)
    assert payload["status"] == "session_started", payload
    assert payload["mode"] == "mitm_only", payload
    assert payload["proxy_port"] == port, payload
    assert "hint" in payload and "127.0.0.1" in payload["hint"], payload
    assert sm._session_active is True
    assert sm.mitm.running is True
    assert sm.browser.running is False, "browser must stay off in mitm-only mode"
    print("  [ok] start_mitm_only fires proxy, leaves browser off")

    # ---- status ----
    status = sm.get_status()
    assert status["session_active"] is True
    assert status["proxy_running"] is True
    assert status["proxy_listening"] is True, "TCP probe must confirm bind"
    assert status["browser_running"] is False
    assert status["proxy_port"] == port
    print(f"  [ok] status reports proxy_listening=True for port {port}")

    # ---- double-start rejected ----
    again = await sm.start_mitm_only(proxy_port=_free_port())
    assert "already active" in again.lower(), again
    print("  [ok] double-start rejected with helpful message")

    # ---- stop ----
    raw_stop = await sm.stop_session()
    stop_payload = json.loads(raw_stop)
    assert stop_payload["status"] == "session_stopped", stop_payload
    assert sm._session_active is False
    assert sm.mitm.running is False
    print("  [ok] stop_session brings proxy down cleanly")
    assert sm.get_status()["proxy_listening"] is False
    print("  [ok] post-stop status: proxy_listening=False")

    # ---- start again after stop is fine ----
    raw2 = await sm.start_mitm_only(proxy_port=_free_port())
    assert json.loads(raw2)["status"] == "session_started"
    await sm.stop_session()
    print("  [ok] re-startable after stop")


async def _run_port_conflict():
    """A second SessionManager trying to bind a port we already hold should
    fail with a structured error and leave its state untouched."""
    sm1 = SessionManager()
    port = _free_port()
    raw = await sm1.start_mitm_only(proxy_port=port)
    assert json.loads(raw)["status"] == "session_started"

    sm2 = SessionManager()
    raw_conflict = await sm2.start_mitm_only(proxy_port=port)
    payload = json.loads(raw_conflict)
    assert payload["status"] == "error", payload
    assert payload["mode"] == "mitm_only", payload
    assert "error" in payload and payload["error"], payload
    assert payload["proxy_port"] == port
    assert "ss -ltnp" in payload["hint"], payload
    assert sm2._session_active is False, "failed start must not flip session_active"
    assert sm2.mitm.running is False, "failed start must not leave mitm running"
    print(f"  [ok] port-conflict on {port}: structured error, state clean")

    await sm1.stop_session()


def main():
    async def all_tests():
        await _run()
        await _run_port_conflict()
    asyncio.run(all_tests())
    print("\n" + "=" * 50)
    print("ALL mitm-only smoke tests PASSED")
    print("=" * 50)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
    reason="binds a real mitm proxy port; set AGENTPROXY_RUN_INTEGRATION=1 to run",
)
def test_mitm_only_suite_runs():
    """pytest wrapper: non-raising run of the mitm-only suite == pass."""
    main()


if __name__ == "__main__":
    main()
