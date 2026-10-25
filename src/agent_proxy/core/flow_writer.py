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

The same queue also accepts detached SSE/WebSocket message records, so live
streams are committed before their HTTP flow closes without adding a second
writer or writing synchronously for every transport chunk.

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
import time
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
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=_MAX_QUEUE)
        self._thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._running = False
        self.dropped = 0
        self.write_errors = 0
        self.scan_errors = 0
        self.persisted = 0
        self.persisted_messages = 0
        self.last_error: Optional[str] = None

    def start(self) -> None:
        with self._state_lock:
            if self._running:
                return
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Previous flow writer is still stopping")
            self._stop_requested.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._run, name="agentproxy-flow-writer", daemon=True
            )
            self._thread.start()

    def get_status(self) -> dict:
        with self._state_lock:
            return {
                "accepting": self._running,
                "thread_alive": bool(self._thread and self._thread.is_alive()),
                "queued": self._queue.qsize(),
                "pending": self._queue.unfinished_tasks,
                "persisted": self.persisted,
                "persisted_messages": self.persisted_messages,
                "dropped": self.dropped,
                "write_errors": self.write_errors,
                "scan_errors": self.scan_errors,
                "last_error": self.last_error,
            }

    def submit(self, flow: http.HTTPFlow, scan: bool) -> None:
        """Snapshot the flow on the hook thread and enqueue it. Never blocks."""
        try:
            snap = FlowSnapshot(flow)
        except Exception as e:  # snapshotting must never break the proxy path
            self.dropped += 1
            self.last_error = str(e)
            logger.error("flow_snapshot_failed", error=str(e))
            return
        self._enqueue(("flow", snap, scan))

    def submit_message(self, message: dict) -> None:
        """Enqueue a detached application message; transport bytes stay live."""
        self._enqueue(("message", dict(message, metadata=dict(message["metadata"])), False))

    def _enqueue(self, item: tuple) -> None:
        # Serialize acceptance with stop(): no snapshot can appear after the
        # worker has decided that its final queue is empty.
        with self._state_lock:
            if not self._running:
                self.dropped += 1
                return
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass  # The consumer made room between the two operations.
                else:
                    self._queue.task_done()
                    self.dropped += 1
                self._queue.put_nowait(item)

    def _run(self) -> None:
        try:
            while True:
                try:
                    kind, item, scan = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if self._stop_requested.is_set():
                        return
                    continue
                try:
                    if kind == "message":
                        self.db.save_stream_message(item)
                        self.persisted_messages += 1
                    else:
                        self.db.save_flow(item, profile_label=item.metadata.get("profile_label"))
                        self.persisted += 1
                except Exception as e:
                    self.write_errors += 1
                    self.last_error = str(e)
                    flow_id = item["flow_id"] if kind == "message" else item.id
                    logger.exception("capture_write_failed", flow_id=flow_id, kind=kind, error=str(e))
                else:
                    if scan and item.response is not None:
                        try:
                            self.scanner.scan(item, self.db)
                        except Exception as e:
                            self.scan_errors += 1
                            self.last_error = str(e)
                            logger.exception("flow_scan_failed", flow_id=item.id, error=str(e))
                finally:
                    self._queue.task_done()
        finally:
            with self._state_lock:
                self._running = False

    def drain(self, timeout: float = 5.0) -> bool:
        """Wait until every accepted snapshot finishes persistence and scanning.

        A processed write can still fail; callers inspect write_errors. Queue
        emptiness alone excludes the item currently being written.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._queue.all_tasks_done.wait(remaining)
            return True

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop accepting, finish the backlog, then join within one budget.

        A timeout retains the thread handle and prevents a second consumer from
        being started. Async callers must offload this blocking method.
        """
        with self._state_lock:
            self._running = False
            self._stop_requested.set()
            thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=max(0.0, timeout))
        if thread.is_alive():
            return False
        with self._state_lock:
            if self._thread is thread:
                self._thread = None
        return True
