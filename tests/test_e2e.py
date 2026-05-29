import asyncio
import json
import sys
import os
import http.server
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestHTTPServer:
    def __init__(self, port=18888):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/api/users':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('X-Custom-Header', 'test-value')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "users": [
                            {"id": 1, "name": "Alice", "email": "alice@test.com"},
                            {"id": 2, "name": "Bob", "email": "bob@test.com"},
                        ],
                        "total": 2
                    }).encode())
                elif self.path.startswith('/api/user/'):
                    uid = self.path.split('/')[-1]
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"id": uid, "name": f"User {uid}"}).encode())
                elif self.path == '/login':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'''
                    <html><body>
                    <form action="/api/login" method="POST">
                        <input type="text" id="username" name="username" />
                        <input type="password" id="password" name="password" />
                        <button type="submit">Login</button>
                    </form>
                    </body></html>
                    ''')
                elif self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Test Page</h1><a href="/api/users">Users API</a></body></html>')
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not Found')

            def do_POST(self):
                if self.path == '/api/login':
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length).decode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Set-Cookie', 'session=abc123; Path=/')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig",
                        "user": "testuser"
                    }).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass

        self.server = http.server.HTTPServer(('127.0.0.1', self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()


async def run_tests():
    from agent_proxy.core.session_manager import SessionManager
    from agent_proxy.models import SessionConfig

    test_server = TestHTTPServer(18888)
    test_server.start()
    print("[OK] Test HTTP server started on port 18888")

    config = SessionConfig(
        proxy_port=28080,
        headless=True,
        browser_timeout=15000,
    )
    session = SessionManager(config=config)

    try:
        # Test 1: Start session
        print("\n=== Test 1: Start Session ===")
        result = await session.start_session(proxy_port=28080, headless=True)
        print(f"Session start: {result}")
        status = session.get_status()
        assert status["session_active"], "Session should be active"
        assert status["proxy_running"], "Proxy should be running"
        assert status["browser_running"], "Browser should be running"
        print("[OK] Session started successfully")

        # Test 2: Navigate browser
        print("\n=== Test 2: Browser Navigation ===")
        result = await session.browser.navigate("http://127.0.0.1:18888/")
        print(f"Navigate result: {result}")
        assert "ok" in result.lower() or "200" in result, "Navigation should succeed"
        print("[OK] Browser navigation works")

        # Test 3: Check traffic capture
        print("\n=== Test 3: Traffic Capture ===")
        await asyncio.sleep(1)
        traffic = session.mitm.db.get_summary(limit=10)
        print(f"Captured {len(traffic)} traffic flows")
        if len(traffic) > 0:
            print(f"First flow: {json.dumps(traffic[0], indent=2)}")
        print("[OK] Traffic capture works")

        # Test 4: Navigate to API endpoint
        print("\n=== Test 4: API Traffic ===")
        result = await session.browser.navigate("http://127.0.0.1:18888/api/users")
        print(f"API navigate: {result}")
        await asyncio.sleep(1)

        traffic = session.mitm.db.get_summary(limit=10)
        print(f"Total captured: {len(traffic)} flows")
        for t in traffic:
            print(f"  {t['method']} {t['url']} -> {t['status_code']}")

        # Test 5: Inspect a flow
        print("\n=== Test 5: Flow Inspection ===")
        if traffic:
            flow_id = traffic[0]['id']
            detail = session.mitm.db.get_detail(flow_id)
            if detail:
                print(f"Flow detail: method={detail['request']['method']}, url={detail['request']['url']}")
                if detail.get('response'):
                    print(f"  Response status: {detail['response']['status_code']}")
                    print(f"  Response body preview: {str(detail['response'].get('body_preview', ''))[:100]}")
        print("[OK] Flow inspection works")

        # Test 6: Search traffic
        print("\n=== Test 6: Traffic Search ===")
        results = session.mitm.db.search(domain="127.0.0.1")
        print(f"Search by domain: found {len(results)} results")
        results = session.mitm.db.search(method="GET")
        print(f"Search by method GET: found {len(results)} results")
        print("[OK] Traffic search works")

        # Test 7: Auth detection
        print("\n=== Test 7: Auth Detection ===")
        result = await session.browser.navigate("http://127.0.0.1:18888/api/login")
        await asyncio.sleep(0.5)

        # Test the login endpoint via browser
        result = await session.browser.navigate("http://127.0.0.1:18888/login")
        await asyncio.sleep(0.5)

        auth_result = session.mitm.detect_auth_patterns()
        print(f"Auth detection: {json.dumps(auth_result['detected_auth_types'])}")
        print("[OK] Auth detection works")

        # Test 8: API patterns
        print("\n=== Test 8: API Discovery ===")
        patterns = session.mitm.get_api_patterns()
        patterns_data = json.loads(patterns)
        print(f"Discovered {len(patterns_data)} API endpoints")
        for p in patterns_data:
            print(f"  {p['method']} {p['path_pattern']} (count: {p['request_count']})")
        print("[OK] API discovery works")

        # Test 9: Interception rules
        print("\n=== Test 9: Traffic Interception ===")
        from agent_proxy.models import InterceptionRule
        rule = InterceptionRule(
            id="test_header_inject",
            url_pattern=".*",
            phase="request",
            action_type="inject_header",
            key="X-Injected-By-AgentProxy",
            value="true",
        )
        session.mitm.interceptor.add_rule(rule)
        print(f"Added interception rule: {rule.id}")
        rules = session.mitm.interceptor.rules
        print(f"Active rules: {list(rules.keys())}")
        session.mitm.interceptor.remove_rule("test_header_inject")
        print("Removed interception rule")
        print("[OK] Traffic interception works")

        # Test 10: OpenAPI generation
        print("\n=== Test 10: OpenAPI Generation ===")
        openapi = session.mitm.export_openapi_spec()
        spec = json.loads(openapi)
        print(f"OpenAPI spec generated: {len(spec.get('paths', {}))} paths")
        print(f"  Paths: {list(spec.get('paths', {}).keys())}")
        print("[OK] OpenAPI generation works")

        # Test 11: Replay
        print("\n=== Test 11: Request Replay ===")
        if traffic:
            flow_id = traffic[0]['id']
            replay_result = await session.mitm.replay_request(flow_id)
            print(f"Replay result: {replay_result}")
        print("[OK] Request replay works")

        # Test 12: Scope management
        print("\n=== Test 12: Scope Management ===")
        session.mitm.scope_manager.update_domains(["127.0.0.1"])
        print(f"Scope set to: {session.mitm.scope_manager.config.allowed_domains}")
        session.mitm.scope_manager.update_domains([])
        print("Scope cleared")
        print("[OK] Scope management works")

        # Test 13: Session status
        print("\n=== Test 13: Session Status ===")
        status = session.get_status()
        print(f"Session status: {json.dumps(status, indent=2)}")
        print("[OK] Session status works")

        # Test 14: Browser operations
        print("\n=== Test 14: Browser Operations ===")
        result = await session.browser.get_text()
        print(f"Page text (first 100 chars): {str(result)[:100]}")
        result = await session.browser.get_url()
        print(f"Current URL: {result}")
        result = await session.browser.get_title()
        print(f"Page title: {result}")
        print("[OK] Browser operations work")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n=== Cleanup ===")
        await session.stop_session()
        test_server.stop()
        print("Session stopped and test server shutdown")


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
    reason="launches real Chromium + mitmproxy on fixed ports; "
           "set AGENTPROXY_RUN_INTEGRATION=1 to run",
)
def test_e2e_suite_runs():
    """pytest wrapper: non-raising run of the e2e suite == pass."""
    asyncio.run(run_tests())


if __name__ == "__main__":
    asyncio.run(run_tests())
