"""Completion and stop semantics of the bounded background writer."""
import queue
from threading import Event
from types import SimpleNamespace

import pytest
from mitmproxy.test import tflow

from agent_proxy.core.flow_writer import FlowWriter


class SlowDB:
    def __init__(self):
        self.entered = Event()
        self.release = Event()
        self.saved = []

    def save_flow(self, flow, **kwargs):
        self.entered.set()
        if not self.release.wait(2):
            raise RuntimeError("test write was never released")
        self.saved.append(flow.id)


def test_drain_waits_for_in_flight_commit_and_stop_retains_live_thread():
    db = SlowDB()
    writer = FlowWriter(db, SimpleNamespace())
    writer.start()
    try:
        writer.submit(tflow.tflow(resp=True), scan=False)
        assert db.entered.wait(1)
        assert writer.get_status()["queued"] == 0
        assert writer.get_status()["pending"] == 1
        assert writer.drain(timeout=.01) is False
        assert writer.stop(timeout=.01) is False
        assert writer.get_status()["thread_alive"] is True
        with pytest.raises(RuntimeError, match="still stopping"):
            writer.start()
    finally:
        db.release.set()
        assert writer.stop(timeout=1)
    assert writer.get_status()["persisted"] == 1
    assert writer.get_status()["pending"] == 0


def test_overflow_accounts_for_discarded_work_and_drain_completes():
    db = SlowDB()
    writer = FlowWriter(db, SimpleNamespace())
    writer._queue = queue.Queue(maxsize=1)
    writer.start()
    try:
        first, discarded, last = (tflow.tflow(resp=True) for _ in range(3))
        writer.submit(first, scan=False)
        assert db.entered.wait(1)
        writer.submit(discarded, scan=False)
        writer.submit(last, scan=False)
        assert writer.get_status()["dropped"] == 1
        db.release.set()
        assert writer.drain(timeout=1)
    finally:
        db.release.set()
        assert writer.stop(timeout=1)
    assert db.saved == [first.id, last.id]
    assert writer.get_status()["pending"] == 0


def test_write_failure_is_visible_after_drain():
    def fail(*args, **kwargs):
        raise RuntimeError("disk full")
    writer = FlowWriter(SimpleNamespace(save_flow=fail), SimpleNamespace())
    writer.start()
    try:
        writer.submit(tflow.tflow(resp=True), scan=False)
        assert writer.drain(timeout=1)
    finally:
        assert writer.stop(timeout=1)
    status = writer.get_status()
    assert status["pending"] == status["persisted"] == 0
    assert status["write_errors"] == 1 and status["last_error"] == "disk full"
