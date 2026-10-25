"""One local journey through live streams, native refs and persisted recovery state."""
import asyncio
import json
import os
import re

import pytest
from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets
from tornado.web import Application, RequestHandler
from tornado.websocket import WebSocketHandler

from agent_proxy.main import create_server
from agent_proxy.models import SessionConfig


class Page(RequestHandler):
    def get(self):
        items = "".join(f"<li>Unchanged navigation item {index}</li>" for index in range(50))
        self.write("""<title>Stream workflow</title><h1 id="status">Waiting</h1>
            <button onclick="document.querySelector('#status').textContent='Updated'">Update</button>
            <iframe id="frame" src="/frame"></iframe><ul>""" + items + """</ul>
            <script>
            window.events = []; window.messages = [];
            window.source = new EventSource('/events');
            source.onmessage = event => events.push(event.data);
            window.socket = new WebSocket(location.origin.replace('http:', 'ws:') + '/socket');
            socket.onopen = () => socket.send('client-hello');
            socket.onmessage = event => messages.push(event.data);
            </script>""")


class Frame(RequestHandler):
    def get(self):
        self.write("""<h2 id="state">Frame waiting</h2><button
            onclick="document.querySelector('#state').textContent='Frame applied'">Apply frame</button>""")


class Events(RequestHandler):
    async def get(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.write("id: first\ndata: available while connected\n\n")
        await self.flush()
        await self.settings["release_streams"].wait()


class Socket(WebSocketHandler):
    def open(self):
        self.write_message("server-hello")

    def on_message(self, message):
        self.write_message("echo:" + message)


async def call(server, name, **arguments):
    result = await server.call_tool(name, arguments)
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


def button_ref(snapshot, name):
    match = re.search(r'button "' + re.escape(name) + r'"[^\n]*\[ref=([^\]]+)\]', snapshot)
    assert match, snapshot
    return match[1]


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
                    reason="launches local Chromium and MITM proxy")
async def test_live_stream_refs_and_checkpoint_recovery(tmp_path):
    release = asyncio.Event()
    app = Application([(r"/", Page), (r"/frame", Frame), (r"/events", Events), (r"/socket", Socket)],
                      release_streams=release)
    sockets = bind_sockets(0, address="127.0.0.1")
    port = sockets[0].getsockname()[1]
    site = HTTPServer(app)
    site.add_sockets(sockets)
    path = str(tmp_path / "traffic.db")
    server = create_server(SessionConfig(db_path=path))
    try:
        async with server.settings.lifespan(server) as context:
            session = context["session"]
            import socket
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                proxy_port = probe.getsockname()[1]
            await call(server, "session_start", proxy_port=proxy_port)
            url = f"http://127.0.0.1:{port}/"
            await call(server, "browser_navigate", url=url)
            page = session.browser.page
            await page.wait_for_function("events.length === 1 && messages.includes('echo:client-hello')")
            assert not release.is_set(), "Messages must be queryable while SSE is still connected"
            assert await asyncio.to_thread(session.mitm.flow_writer.drain, 3)
            sse = await call(server, "traffic_messages", protocol="sse")
            assert sse["messages"][0]["payload"] == "available while connected"
            assert sse["messages"][0]["metadata"]["id"] == "first"
            ws = await call(server, "traffic_messages", protocol="websocket")
            assert {message["direction"] for message in ws["messages"]} == {"client_to_server", "server_to_client"}
            assert not (await call(server, "traffic_messages", protocol="websocket", after_id=ws["next_after_id"]))["messages"]

            initial = await call(server, "browser_snapshot", incremental=False)
            update_ref = button_ref(initial["snapshot"], "Update")
            frame_ref = button_ref(initial["snapshot"], "Apply frame")
            assert frame_ref.startswith("f"), "The root snapshot must include an iframe reference"
            await call(server, "browser_act", action="click", ref=update_ref, snapshot_id=initial["snapshot_id"])
            delta = await call(server, "browser_snapshot")
            assert delta["kind"] == "delta" and delta["base_snapshot_id"] == initial["snapshot_id"]
            assert "Updated" in delta["snapshot"]
            await call(server, "browser_act", action="click", ref=frame_ref, snapshot_id=delta["snapshot_id"])
            assert await page.frame_locator("#frame").locator("#state").inner_text() == "Frame applied"

            duplicate = await page.context.new_page()
            await duplicate.goto(url, wait_until="domcontentloaded")
            await page.close()
            restored = await call(server, "browser_snapshot")
            assert restored["recovery"]["status"] == "restored"
            assert restored["recovery"]["actions_replayed"] == 0
            assert session.browser.page is duplicate
            # Model a lost acknowledgement after the intent was persisted. The
            # next process must preserve uncertainty, never reissue the click.
            await asyncio.to_thread(session.checkpoints.begin, {"action": "click", "selector": "#submit"})

        restarted = create_server(SessionConfig(db_path=path))
        async with restarted.settings.lifespan(restarted) as context:
            checkpoint = (await call(restarted, "browser_checkpoint"))["checkpoint"]
            assert checkpoint["status"] == "needs_review" and checkpoint["action_status"] == "unknown"
            plan = await call(restarted, "browser_checkpoint", operation="restore")
            assert plan["status"] == "resume_required" and plan["actions_replayed"] == 0
            assert context["session"].browser.running is False
    finally:
        release.set()
        site.stop()
        await site.close_all_connections()
