"""Lifecycle fault regressions; no browser, listener or external service."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from agent_proxy.core import session_manager as session_module
from agent_proxy.core.mitm_controller import MitmController
from agent_proxy.models import SessionConfig


class StubProxy:
    def __init__(self, **kwargs):
        self.port = 8080
        self.running = False
        self.last_error = None
        self.starts = 0
        self.stops = 0
        self.flow_writer = SimpleNamespace(get_status=lambda: {"pending": 0})
        self.db = SimpleNamespace(count_flows=lambda: 0)
        self.interceptor = SimpleNamespace(rules={})

    async def start(self, port, host):
        self.port = port
        self.starts += 1
        self.running = True
        return "proxy started"

    async def stop(self, **kwargs):
        self.stops += 1
        self.running = False
        return "proxy stopped"


class StubBrowser:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.running = False
        self.active = "default"
        self.acquired = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.starts = 0
        self.stops = 0
        self.stop_delay = 0
        self.stop_error = None

    def list_contexts(self):
        return ["default"] if self.running else []

    async def start(self):
        self.starts += 1
        self.acquired = True
        self.entered.set()
        await self.release.wait()
        self.running = True
        return "browser started"

    async def stop(self):
        self.stops += 1
        if self.stop_delay:
            await asyncio.sleep(self.stop_delay)
        if self.stop_error:
            raise self.stop_error
        self.running = self.acquired = False
        return "browser stopped"


@pytest.fixture
def session(monkeypatch, tmp_path):
    monkeypatch.setattr(session_module, "MitmController", StubProxy)
    monkeypatch.setattr(session_module, "BrowserController", StubBrowser)
    return session_module.SessionManager(SessionConfig(
        db_path=str(tmp_path / "traffic.db"), startup_timeout=1, shutdown_timeout=.5))


@pytest.mark.asyncio
async def test_cancelled_start_releases_partial_resources_and_can_restart(session):
    task = asyncio.create_task(session.start_session())
    await session.browser.entered.wait()
    session.browser.stop_delay = .01
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.browser.stops == session.mitm.stops == 1
    assert not session.browser.acquired and not session.mitm.running
    assert session.state == "idle"
    session.browser.release.set()
    assert json.loads(await session.start_session())["status"] == "session_started"
    await session.stop_session()


@pytest.mark.asyncio
async def test_concurrent_starts_share_one_resource_set(session):
    first = asyncio.create_task(session.start_session())
    await session.browser.entered.wait()
    second = asyncio.create_task(session.start_session())
    session.browser.release.set()
    results = await asyncio.gather(first, second)
    assert json.loads(results[0])["status"] == "session_started"
    assert "already active" in results[1]
    assert session.browser.starts == session.mitm.starts == 1
    await session.stop_session()


@pytest.mark.asyncio
async def test_startup_timeout_has_separate_cleanup_budget(session):
    session.config.startup_timeout = .01
    session.browser.stop_delay = .03
    with pytest.raises(TimeoutError):
        await session.start_session()
    assert not session.browser.acquired and not session.mitm.running
    assert session.state == "idle"


@pytest.mark.asyncio
async def test_browser_cleanup_failure_does_not_skip_proxy_cleanup(session):
    session.browser.release.set()
    await session.start_session()
    session.browser.stop_error = RuntimeError("close failed")
    with pytest.raises(RuntimeError, match="close failed"):
        await session.stop_session()
    assert not session.mitm.running
    assert session.state == "failed" and session._cleanup_error
    session.browser.stop_error = None
    await session.stop_session()
    assert session.state == "idle" and session._cleanup_error is None


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_cleanup_before_unlocking(session):
    session.browser.release.set()
    await session.start_session()
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_stop():
        entered.set()
        await release.wait()
        session.browser.running = session.browser.acquired = False
        return "browser stopped"

    session.browser.stop = slow_stop
    task = asyncio.create_task(session.stop_session())
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert session._lifecycle_lock.locked()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.state == "idle" and not session.browser.acquired
    assert not session._lifecycle_lock.locked()


@pytest.mark.asyncio
async def test_late_cancellation_preserves_startup_error_and_final_state(session):
    entered, release = asyncio.Event(), asyncio.Event()

    async def fail_start():
        session.browser.acquired = True
        raise ValueError("invalid browser state")

    async def slow_stop():
        entered.set()
        await release.wait()
        session.browser.acquired = False
        return "browser stopped"

    session.browser.start = fail_start
    session.browser.stop = slow_stop
    task = asyncio.create_task(session.start_session())
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert session._lifecycle_lock.locked()
    release.set()
    with pytest.raises(ValueError, match="invalid browser state"):
        await task
    assert session.state == "idle" and not session._session_active
    assert not session.browser.acquired and not session.mitm.running
    assert not session._lifecycle_lock.locked()


def test_default_databases_are_isolated_and_explicit_paths_reused(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = SessionConfig()
    first = session_module.SessionManager(config)
    second = session_module.SessionManager(config)
    assert config.db_path is None  # Constructing one instance does not mutate the shared config.
    assert first.session_id != second.session_id
    assert first.config.db_path != second.config.db_path
    assert first.session_id in first.config.db_path
    explicit = SessionConfig(db_path=str(tmp_path / "history.db"))
    a, b = session_module.SessionManager(explicit), session_module.SessionManager(explicit)
    assert a.config.db_path == b.config.db_path == str(tmp_path / "history.db")
    status = first.get_status()
    assert status["session_id"] == first.session_id
    assert status["db_path"] == first.config.db_path and status["writer"]["pending"] == 0


@pytest.mark.asyncio
async def test_proxy_background_failure_updates_health(tmp_path):
    proxy = MitmController(db_path=str(tmp_path / "traffic.db"))

    async def fail():
        raise RuntimeError("listener crashed")

    proxy.running = True
    proxy.proxy_task = asyncio.create_task(fail())
    proxy.proxy_task.add_done_callback(proxy._proxy_exited)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not proxy.running and proxy.last_error == "listener crashed"
    await proxy.stop()
