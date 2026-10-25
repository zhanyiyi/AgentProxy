"""Message boundaries, byte budgets and persistence while connections stay open."""
import base64
from types import SimpleNamespace

from mitmproxy.test import tflow
from mitmproxy.websocket import WebSocketData, WebSocketMessage

from agent_proxy.core.flow_writer import FlowWriter
from agent_proxy.core.mitm_controller import ScopeManager, TrafficRecorder
from agent_proxy.core.stream_capture import (
    MAX_MESSAGE_BYTES, MAX_MESSAGES_PER_FLOW, SSEParser, StreamCapture,
)
from agent_proxy.core.traffic_db import TrafficDB
from agent_proxy.models import ScopeConfig


def test_sse_chunk_boundaries_and_incomplete_tail():
    messages = []
    parser = SSEParser(lambda payload, metadata: messages.append((payload, metadata)))
    for chunk in [b"\xef", b"\xbb\xbfid: order-1\r", b"\nevent: update\r\ndata: \xe4",
                  b"\xbd\xa0\r", b"\ndata: second\nretry: 1500\n\n", b"data: tail", b""]:
        parser.feed(chunk)
    assert [payload for payload, _ in messages] == ["你\nsecond", "tail"]
    first, tail = (metadata for _, metadata in messages)
    assert first["event"] == "update" and first["id"] == "order-1"
    assert first["retry"] == 1500 and first["incomplete"] is False
    assert tail["event"] == "message" and tail["id"] == "order-1"
    assert tail["retry"] == 1500 and tail["incomplete"] is True


def test_sse_large_line_is_bounded_and_marked_without_losing_next_event():
    messages = []
    parser = SSEParser(lambda payload, metadata: messages.append((payload, metadata)))
    parser.feed(b"data: " + b"x" * MAX_MESSAGE_BYTES + b"tail\n\n")
    parser.feed(b":" + b"c" * (2 * MAX_MESSAGE_BYTES))
    assert len(parser._line) <= MAX_MESSAGE_BYTES + len(b"data: ")
    parser.feed(b"\n\ndata: next\n\n")
    assert len(messages[0][0].encode()) == MAX_MESSAGE_BYTES
    assert messages[0][1]["truncated"] is True
    assert messages[0][1]["original_bytes"] == MAX_MESSAGE_BYTES + 4
    assert messages[1][0] == "next" and messages[1][1]["truncated"] is False


def test_websocket_binary_budget_and_shared_connection_limit():
    messages = []
    state = {}
    capture = StreamCapture("ws", "websocket", messages.append, state)
    binary = bytes(range(256)) * (MAX_MESSAGE_BYTES // 256 + 1)
    capture.websocket_message(WebSocketMessage(2, True, binary, timestamp=123))
    entry = messages[0]
    assert base64.b64decode(entry["payload"]) == binary[:MAX_MESSAGE_BYTES]
    assert entry["direction"] == "client_to_server" and entry["timestamp"] == 123
    assert entry["metadata"]["opcode"] == 2
    assert entry["metadata"]["truncated"] is True
    state["stream_message_count"] = MAX_MESSAGES_PER_FLOW - 1
    for text in (b"last", b"omitted", b"also omitted"):
        capture.websocket_message(WebSocketMessage(1, False, text))
    assert [message["payload"] for message in messages[1:]] == ["last", ""]
    assert messages[-1]["metadata"] == {
        "kind": "limit", "omitted": "message_limit", "limit": MAX_MESSAGES_PER_FLOW,
    }


def test_sse_headers_and_messages_persist_before_close(tmp_path):
    db = TrafficDB(tmp_path / "traffic.db")
    scanner = SimpleNamespace(scan=lambda *args: None)
    writer = FlowWriter(db, scanner)
    recorder = TrafficRecorder(ScopeManager(ScopeConfig()), db, scanner, writer)
    flow = tflow.tflow(resp=True)
    flow.response.headers["content-type"] = "text/event-stream; charset=utf-8"
    flow.response.raw_content = None
    writer.start()
    try:
        recorder.request(flow)
        recorder.responseheaders(flow)
        chunk = b"id: item-1\ndata: available while open\n\n"
        assert flow.response.stream(chunk) is chunk
        assert writer.drain(timeout=2)
        assert db.get_detail(flow.id)["response"]["status_code"] == 200
        messages = db.list_stream_messages(flow_id=flow.id)
        assert [message["payload"] for message in messages] == ["available while open"]
        assert writer.get_status()["persisted_messages"] == 1
        assert flow.response.stream(b"") == b""
        recorder.response(flow)
        assert writer.drain(timeout=2)
        response = db.get_detail(flow.id)["response"]
        assert response["body_omitted"] == "stream_messages"
        assert response["headers"]["content-type"] == "text/event-stream; charset=utf-8"
    finally:
        assert writer.stop(timeout=2)


def test_unsupported_sse_encoding_is_explicit_and_keeps_transport_headers(tmp_path):
    db = TrafficDB(tmp_path / "traffic.db")
    recorder = TrafficRecorder(ScopeManager(ScopeConfig()), db)
    flow = tflow.tflow(resp=True)
    flow.response.raw_content = None
    flow.response.headers["content-type"] = "text/event-stream"
    flow.response.headers["content-encoding"] = "gzip"
    recorder.responseheaders(flow)
    assert flow.response.stream is True
    assert flow.response.headers["content-encoding"] == "gzip"
    message = db.list_stream_messages()[0]
    assert message["metadata"]["kind"] == "unsupported"
    assert message["metadata"]["content_encoding"] == "gzip"
    assert db.get_detail(flow.id)["response"]["body_omitted"] == "stream_content_encoding_unsupported"


def test_sse_uses_utf8_despite_charset_and_flushes_error_tail_once(tmp_path):
    db = TrafficDB(tmp_path / "traffic.db")
    recorder = TrafficRecorder(ScopeManager(ScopeConfig()), db)
    flow = tflow.tflow(resp=True)
    flow.response.raw_content = None
    flow.response.headers["content-type"] = "text/event-stream; charset=latin-1"
    recorder.responseheaders(flow)
    flow.response.stream("data: 你好".encode("utf-8"))
    recorder.error(flow)
    flow.response.stream(b"")
    messages = db.list_stream_messages()
    assert len(messages) == 1 and messages[0]["payload"] == "你好"
    assert messages[0]["metadata"]["incomplete"] is True
    assert db.get_detail(flow.id)["response"]["body_charset"] == "utf-8"


def test_websocket_recorder_cursor_filter_and_clear(tmp_path):
    db = TrafficDB(tmp_path / "traffic.db")
    recorder = TrafficRecorder(ScopeManager(ScopeConfig()), db)
    flow = tflow.tflow(resp=True)
    flow.response.status_code = 101
    flow.websocket = WebSocketData()
    recorder.responseheaders(flow)
    for message in [WebSocketMessage(1, False, b"server event"), WebSocketMessage(1, True, b"reply")]:
        flow.websocket.messages.append(message)
        recorder.websocket_message(flow)
    first, second = db.list_stream_messages(protocol="websocket")
    assert first["direction"] == "server_to_client"
    assert second["direction"] == "client_to_server"
    assert db.list_stream_messages(flow.id, after_id=first["id"], limit=1) == [second]
    assert db.list_stream_messages(protocol="sse") == []
    assert db.get_detail(flow.id)["response"]["status_code"] == 101
    db.clear()
    assert db.list_stream_messages() == []
    next_id = db.save_stream_message(second)
    assert next_id > second["id"]
