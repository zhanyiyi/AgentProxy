"""Background flow writer — keeps SQLite writes + passive scans off the event loop.

mitmproxy's `request`/`response`/`error` hooks are synchronous and run on the
*same* asyncio loop that serves the MCP tools and drives Playwright. Doing the
SQLite write (twice per flow) and the up-to-256KB regex passive scan inline in
`response()` blocks that loop, so a burst of traffic or one large body stalls
MCP responses and browser automation.

This module moves that work to a dedicated daemon thread fed by a queue. The
recorder hook stays synchronous but only:
  1. does the cheap, must-be-inline work (strip our internal header), then
  2. snapshots the flow into a detached `FlowSnapshot` and enqueues it.

The snapshot is necessary because mitmproxy reuses/mutates the live `HTTPFlow`
object after the hook returns — we cannot hold a reference to it. The snapshot
re-exposes exactly the read interface that `TrafficDB.save_flow` and
`PassiveScanner.scan` consume (`.id`, `.request`, `.response`, `.metadata`,
`.headers` with `get`/`get_all`/`items`/`.fields`, `.content`, etc.), so neither
of those needs to change.
"""
from __future__ import annotations

import queue
import threading
from typing import Optional

import structlog
from mitmproxy import http
from mitmproxy.http import Headers

logger = structlog.get_logger()

# Bound the queue so a pathological traffic flood can't grow memory without
# limit. If the writer can't keep up we drop the *oldest* unwritten flow and
# count it, rather than blocking the capture hook (which would re-introduce the
# event-loop stall this module exists to avoid).
_MAX_QUEUE = 5000


class _MsgSnapshot:
    """Detached request/response view with the subset of the mitmproxy message
    API that save_flow / passive_scan read."""

    __slots__ = ("headers", "content", "url", "method", "status_code", "timestamp_start")

    def __init__(self, headers: Headers, content: Optional[bytes],
                 url: str = "", method: str = "", status_code: Optional[int] = None,
                 timestamp_start: Optional[float] = None):
        self.headers = headers
        self.content = content
        self.url = url
        self.method = method
        self.status_code = status_code
        self.timestamp_start = timestamp_start


class FlowSnapshot:
    """Immutable, thread-safe copy of an HTTPFlow taken inside the sync hook.

    Re-uses mitmproxy's own `Headers` so case-insensitive `get`, `get_all`,
    `items`, and `.fields` (used for ordered/duplicate header preservation in
    save_flow) all behave identically to a live flow.
    """

    __slots__ = ("id", "request", "response", "metadata")

    def __init__(self, flow: http.HTTPFlow):
        self.id = flow.id
        self.metadata = dict(flow.metadata)

        req = flow.request
        self.request = _MsgSnapshot(
            headers=Headers(list(req.headers.fields)),
            content=req.content,
            url=req.url,
            method=req.method,
            timestamp_start=req.timestamp_start,
        )

        if flow.response is not None:
            resp = flow.response
            self.response = _MsgSnapshot(
                headers=Headers(list(resp.headers.fields)),
                content=resp.content,
                status_code=resp.status_code,
            )
        else:
            self.response = None


class FlowWriter:
    """Single daemon-thread consumer that persists snapshots and runs the scan."""

    def __init__(self, db, scanner):
        self.db = db
        self.scanner = scanner
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=_MAX_QUEUE)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.dropped = 0
        self.write_errors = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="agentproxy-flow-writer", daemon=True
        )
        self._thread.start()

    def submit(self, flow: http.HTTPFlow, scan: bool) -> None:
        """Snapshot the flow on the hook thread and enqueue it. Never blocks."""
        try:
            snap = FlowSnapshot(flow)
        except Exception as e:  # snapshotting must never break the proxy path
            logger.error("flow_snapshot_failed", error=str(e))
            return
        label = snap.metadata.get("profile_label")
        try:
            self._queue.put_nowait((snap, label, scan))
        except queue.Full:
            # Drop the oldest pending item to make room, then retry once.
            try:
                self._queue.get_nowait()
                self.dropped += 1
                self._queue.put_nowait((snap, label, scan))
            except queue.Empty:
                self._queue.put_nowait((snap, label, scan))

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:  # shutdown sentinel
                self._queue.task_done()
                break
            snap, label, scan = item
            try:
                self.db.save_flow(snap, profile_label=label)
                if scan and snap.response is not None:
                    self.scanner.scan(snap, self.db)
            except Exception as e:
                self.write_errors += 1
                logger.error("flow_write_failed", flow_id=getattr(snap, "id", "?"), error=str(e))
            finally:
                self._queue.task_done()

    def drain(self, timeout: float = 5.0) -> bool:
        """Block until the queue is empty or timeout. Returns True if drained.

        Does NOT gate on self._running: stop() flips _running False before
        draining, and we still want the pending backlog flushed."""
        if self._thread is None:
            return True
        try:
            # queue.join() has no timeout; emulate one with a short poll loop.
            import time as _time
            deadline = _time.monotonic() + timeout
            while not self._queue.empty():
                if _time.monotonic() > deadline:
                    return False
                _time.sleep(0.02)
            return True
        except Exception:
            return False

    def stop(self, timeout: float = 5.0) -> None:
        if not self._running:
            return
        self._running = False
        self.drain(timeout=timeout)
        try:
            self._queue.put_nowait(None)  # sentinel
        except queue.Full:
            # Force room for the sentinel.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
