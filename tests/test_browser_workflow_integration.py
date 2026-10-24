"""One local browser journey: iframe, confirmation, popup, download and history."""
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from agent_proxy.main import create_server
from agent_proxy.models import SessionConfig


PDF = b"%PDF-1.4\n% AgentProxy local workflow fixture\n%%EOF\n"
PAGES = {
    "/": b"""<title>Workflow</title><iframe id="report" src="/frame"></iframe>
        <button id="confirm" onclick="if(confirm('Open the sample report?'))location.href='/ready'">Continue</button>""",
    "/frame": b"""<h1>Report frame</h1><input id="filter"><button id="apply"
        onclick="document.querySelector('h1').textContent='Filter applied'">Apply</button>""",
    "/ready": b"""<title>Ready</title><a id="popup" target="_blank" href="/popup">Open report</a>""",
    "/popup": b"""<title>Sample report</title><a id="download" href="/sample.pdf" download>Download</a>""",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PDF if self.path == "/sample.pdf" else PAGES.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/pdf" if self.path.endswith(".pdf") else "text/html; charset=utf-8")
        if self.path == "/sample.pdf":
            self.send_header("Content-Disposition", 'attachment; filename="sample.pdf"')
        body = body or b"Not found"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


async def call(server, name, **arguments):
    result = await server.call_tool(name, arguments)
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
                    reason="launches local Chromium and MITM proxy")
async def test_local_multistep_browser_journey(tmp_path):
    site = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=site.serve_forever, daemon=True)
    thread.start()
    server = create_server(SessionConfig(db_path=str(tmp_path / "traffic.db")))
    try:
        async with server.settings.lifespan(server) as context:
            session = context["session"]
            # Avoid fixed test ports that may belong to another local process.
            import socket
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                proxy_port = probe.getsockname()[1]
            started = await call(server, "session_start", proxy_port=proxy_port)
            assert started["status"] == "session_started"
            base = f"http://127.0.0.1:{site.server_port}"
            await call(server, "browser_navigate", url=base + "/")
            snapshot = await call(server, "browser_snapshot", frame="iframe#report")
            assert "Report frame" in snapshot["snapshot"]
            await call(server, "browser_act", action="fill", selector="#filter", value="private-filter-value", frame="iframe#report")
            await call(server, "browser_act", action="click", selector="#apply", frame="iframe#report")
            assert "Filter applied" in (await call(server, "browser_snapshot", frame="iframe#report"))["snapshot"]

            receipt = await call(server, "browser_act", action="click", selector="#confirm")
            assert receipt["status"] == "dialog_pending"
            assert receipt["dialogs"][0]["message"] == "Open the sample report?"
            async with session.browser.page.expect_navigation(wait_until="domcontentloaded"):
                await call(server, "browser_dialog", accept=True)

            async with session.browser.page.context.expect_page() as popup_info:
                await call(server, "browser_act", action="click", selector="#popup")
            popup = await popup_info.value
            await popup.wait_for_load_state("domcontentloaded")
            tabs = (await call(server, "browser_tabs"))["tabs"]
            popup_tab = next(tab for tab in tabs if tab["url"].endswith("/popup"))
            await call(server, "browser_tabs", operation="select", tab_id=popup_tab["tab_id"])
            async with popup.expect_download():
                await call(server, "browser_act", action="click", selector="#download")

            async def completed_download():
                while True:
                    downloads = (await call(server, "browser_downloads"))["downloads"]
                    if downloads and downloads[-1]["status"] != "pending":
                        return downloads[-1]
                    await asyncio.sleep(0.02)

            download = await asyncio.wait_for(completed_download(), timeout=5)
            assert download["status"] == "completed", download
            assert Path(download["saved_path"]).read_bytes() == PDF
            assert download["sha256"] == hashlib.sha256(PDF).hexdigest()
            assert await asyncio.to_thread(session.mitm.flow_writer.drain, 3)
            flows = session.mitm.db.search(query="/sample.pdf")
            assert flows, "PDF paths must pass the default capture scope"
            detail = session.mitm.db.get_detail(flows[0]["id"])
            assert detail["response"]["artifact"]["sha256"] == download["sha256"]
            history = (await call(server, "session_timeline"))["actions"]
            assert len(history) >= 7
            assert "private-filter-value" not in json.dumps(history)
            image_result = await server.call_tool("browser_screenshot", {})
            content = image_result[0] if isinstance(image_result, tuple) else image_result
            assert content[0].type == "image"
        assert session.browser.running is False
        assert session.mitm.running is False
    finally:
        await asyncio.to_thread(site.shutdown)
        site.server_close()
        thread.join(timeout=1)
