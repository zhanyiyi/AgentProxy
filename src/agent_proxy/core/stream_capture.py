"""Bounded, passive capture of application messages carried by live streams.

The SSE parser observes decoded UTF-8 text but never owns or changes transport
bytes. Each connection keeps at most one bounded event under construction;
completed messages go through the existing background writer.
"""
from __future__ import annotations

import base64
import codecs
import re
import time
from typing import Callable


MAX_MESSAGE_BYTES = 64 * 1024
MAX_MESSAGES_PER_FLOW = 1000
_MAX_FIELD_BYTES = 1024
_LINE_END = re.compile(r"\r\n|\r|\n")


class StreamCapture:
    """Apply one per-flow message budget shared by both WebSocket directions."""

    def __init__(self, flow_id: str, protocol: str, emit: Callable, state: dict):
        self.flow_id = flow_id
        self.protocol = protocol
        self.emit = emit
        self.state = state

    def message(self, payload: str, metadata: dict, direction: str = "server_to_client",
                timestamp: float | None = None) -> None:
        count = self.state.get("stream_message_count", 0)
        if count >= MAX_MESSAGES_PER_FLOW:
            if not self.state.get("stream_message_limit_reached"):
                self.state["stream_message_limit_reached"] = True
                self._emit("", {"kind": "limit", "omitted": "message_limit",
                                "limit": MAX_MESSAGES_PER_FLOW}, direction, timestamp)
            return
        self.state["stream_message_count"] = count + 1
        self._emit(payload, metadata, direction, timestamp)

    def _emit(self, payload: str, metadata: dict, direction: str,
              timestamp: float | None) -> None:
        self.emit({"flow_id": self.flow_id, "protocol": self.protocol,
                   "direction": direction, "timestamp": timestamp if timestamp is not None else time.time(),
                   "payload": payload, "metadata": dict(metadata)})

    def websocket_message(self, message) -> None:
        content = message.content
        captured = content[:MAX_MESSAGE_BYTES]
        metadata = {
            "opcode": int(message.type), "encoding": "utf-8" if message.is_text else "base64",
            "original_bytes": len(content), "captured_bytes": len(captured),
            "truncated": len(content) > len(captured),
            "dropped": message.dropped, "injected": message.injected,
        }
        if message.is_text:
            # A byte limit may split a valid code point; that tail is omitted,
            # whereas malformed bytes from the peer remain visible as U+FFFD.
            payload = codecs.getincrementaldecoder("utf-8")("replace").decode(
                captured, final=not metadata["truncated"]
            )
            encoded_payload = payload.encode("utf-8")
            if len(encoded_payload) > MAX_MESSAGE_BYTES:
                payload = encoded_payload[:MAX_MESSAGE_BYTES].decode("utf-8", errors="ignore")
                metadata["truncated"] = True
            metadata["captured_bytes"] = len(payload.encode("utf-8"))
        else:
            payload = base64.b64encode(captured).decode("ascii")
        self.message(payload, metadata,
                     "client_to_server" if message.from_client else "server_to_client",
                     message.timestamp)


class SSEParser:
    """Incrementally retain SSE event facts across arbitrary chunk boundaries.

    A blank line completes an event. An EOF tail is retained with
    ``incomplete=True`` so received data is not confused with a dispatched
    event. Comments and unknown fields consume no persistent message budget.
    The line, data and event/id fields are bounded independently.
    """

    def __init__(self, emit: Callable):
        self.emit = emit
        self._decoder = codecs.getincrementaldecoder("utf-8-sig")("replace")
        self._line = bytearray()
        self._line_bytes = 0
        self._skip_lf = False
        self._data = bytearray()
        self._data_bytes = 0
        self._has_data = False
        self._event = ""
        self._id = ""
        self._retry = None
        self._truncated_fields: set[str] = set()

    def feed(self, chunk: bytes) -> None:
        final = not chunk
        text = self._decoder.decode(chunk, final=final)
        if self._skip_lf and text:
            if text.startswith("\n"):
                text = text[1:]
            self._skip_lf = False
        start = 0
        for ending in _LINE_END.finditer(text):
            self._append_line(text[start:ending.start()])
            self._finish_line()
            start = ending.end()
            self._skip_lf = ending.group() == "\r" and start == len(text)
        self._append_line(text[start:])
        if final:
            if self._line_bytes:
                self._finish_line()
            self._dispatch(incomplete=True)

    def _append_line(self, text: str) -> None:
        encoded = text.encode("utf-8")
        self._line_bytes += len(encoded)
        remaining = MAX_MESSAGE_BYTES + len(b"data: ") - len(self._line)
        if remaining > 0:
            self._line.extend(encoded[:remaining])

    def _finish_line(self) -> None:
        raw = bytes(self._line)
        size = self._line_bytes
        self._line.clear()
        self._line_bytes = 0
        if not size:
            self._dispatch()
            return
        if raw.startswith(b":"):
            return
        field, separator, value = raw.partition(b":")
        prefix_size = len(field) + len(separator)
        if value.startswith(b" "):
            value = value[1:]
            prefix_size += 1
        if field == b"data":
            if self._has_data:
                self._append_data(b"\n", 1)
            self._has_data = True
            self._append_data(value, max(0, size - prefix_size))
        elif field in {b"event", b"id"}:
            name = field.decode("ascii")
            if field == b"id" and b"\0" in value:
                return
            if size - prefix_size > _MAX_FIELD_BYTES:
                self._truncated_fields.add(name)
            else:
                self._truncated_fields.discard(name)
            text = value[:_MAX_FIELD_BYTES].decode("utf-8", errors="ignore")
            if field == b"event":
                self._event = text
            else:
                self._id = text
        elif field == b"retry" and value.isdigit():
            # An enormous decimal cannot be a usable reconnect interval and
            # must not create an unbounded integer conversion on the proxy.
            if size - prefix_size <= 32:
                self._retry = int(value)
                self._truncated_fields.discard("retry")
            else:
                self._truncated_fields.add("retry")

    def _append_data(self, prefix: bytes, original_size: int) -> None:
        self._data_bytes += original_size
        remaining = MAX_MESSAGE_BYTES - len(self._data)
        if remaining > 0:
            self._data.extend(prefix[:remaining])

    def _dispatch(self, incomplete: bool = False) -> None:
        if self._has_data:
            truncated = self._data_bytes > len(self._data)
            payload = codecs.getincrementaldecoder("utf-8")("replace").decode(
                bytes(self._data), final=not truncated
            )
            metadata = {"event": self._event or "message", "id": self._id,
                        "retry": self._retry, "encoding": "utf-8",
                        "original_bytes": self._data_bytes,
                        "captured_bytes": len(payload.encode("utf-8")),
                        "truncated": truncated, "incomplete": incomplete}
            if self._truncated_fields:
                metadata["truncated_fields"] = sorted(self._truncated_fields)
            self.emit(payload, metadata)
        self._data.clear()
        self._data_bytes = 0
        self._has_data = False
        self._event = ""
        self._truncated_fields.discard("event")
