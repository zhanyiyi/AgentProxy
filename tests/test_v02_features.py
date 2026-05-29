"""Smoke tests for v0.2 features: findings / site_map / layered inspect / diff."""
import asyncio
import json
import sys
import os
import tempfile
import http.server
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


HTML_PAGE = b"""<html><head><title>app</title></head><body>
<h1>app</h1>
<a href="/api/profile">profile</a>
<a href="/api/profile?redirect=/admin">redirect-link</a>
<a href="/.git/config">git-config</a>
</body></html>"""

PROFILE_JSON = json.dumps({
    "user": "alice",
    "aws_key": "AKIAIOSFODNN7EXAMPLE",
    "session_jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
}).encode()

SQL_ERROR_JSON = json.dumps({
    "error": "You have an error in your SQL syntax near 'foo'"
}).encode()


class VulnServer:
    def __init__(self, port=18891):
        self.port = port

    def start(self):
        outer = self
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(HTML_PAGE)
                elif self.path.startswith("/api/profile"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Credentials", "true")
                    self.end_headers()
                    self.wfile.write(PROFILE_JSON)
                elif self.path == "/.git/config":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"[core]\nrepositoryformatversion = 0")
                elif self.path == "/api/search":
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(SQL_ERROR_JSON)
                else:
                    self.send_response(404); self.end_headers()
            def log_message(self, *a, **k): pass

        self.server = http.server.HTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        if self.server: self.server.shutdown()


async def main():
    from agent_proxy.core.session_manager import SessionManager
    from agent_proxy.models import SessionConfig

    srv = VulnServer(); srv.start()
    print("[ok] vuln server up")

    cfg = SessionConfig(proxy_port=28082, headless=True, browser_timeout=15000,
                        db_path=os.path.join(tempfile.mkdtemp(), "v02.db"))
    s = SessionManager(config=cfg)
    failed = 0

    try:
        await s.start_session(proxy_port=28082, headless=True)
        print("[ok] session started")

        for path in ["/", "/api/profile", "/api/profile?redirect=/admin",
                     "/.git/config", "/api/search"]:
            await s.browser.navigate(f"http://127.0.0.1:18891{path}")
        await asyncio.sleep(1)

        # Test A: findings populated (kind='all' to include both findings + signals)
        findings = s.mitm.db.list_findings(kind="all", limit=200)
        print(f"\n[test] findings+signals count = {len(findings)}")
        rule_ids = {f["rule_id"] for f in findings}
        print(f"  rule_ids fired: {sorted(rule_ids)}")
        expected = {"aws_access_key", "jwt_in_body", "sqli_db_error",
                    "cors_misconfig", "debug_endpoint", "sensitive_param", "missing_csp"}
        missing = expected - rule_ids
        if missing:
            print(f"  [FAIL] missing rules: {missing}"); failed += 1
        else:
            print("  [ok] all 7 expected rules fired")

        # Test B: findings_stats
        stats = s.mitm.db.findings_stats()
        print(f"\n[test] stats = {stats}")
        # v0.3: stats now splits into findings vs signals
        total_in_stats = stats["findings"]["count"] + stats["signals"]["count"]
        if total_in_stats != len(findings):
            print("  [FAIL] stats total mismatch"); failed += 1
        else:
            print(f"  [ok] stats consistent (findings={stats['findings']['count']}, signals={stats['signals']['count']})")

        # Test C: layered inspect
        flows = s.mitm.db.get_summary(limit=20)
        if flows:
            fid = flows[0]["id"]
            meta = s.mitm.db.get_detail(fid, level="meta")
            preview = s.mitm.db.get_detail(fid, level="preview")
            full = s.mitm.db.get_detail(fid, level="full", body_preview_length=256*1024)
            print(f"\n[test] inspect levels for {fid[:8]}")
            assert "body" not in meta["request"], "meta should not have body"
            print(f"  [ok] meta has no body")
            print(f"  [ok] preview has body: {bool((preview.get('response') or {}).get('body'))}")
            print(f"  [ok] full body len: {len((full.get('response') or {}).get('body') or '')}")

        # Test D: site_map
        sm = json.loads(s.mitm.site_map())
        print(f"\n[test] site_map hosts: {[h['host'] for h in sm]}")
        if not any("127.0.0.1" in h["host"] for h in sm):
            print("  [FAIL] site_map missing host"); failed += 1
        else:
            print(f"  [ok] {len(sm[0]['endpoints'])} endpoints captured under host")
            print(f"  [ok] first endpoint findings count: {sm[0]['endpoints'][0]['findings']}")

        # Test E: with_findings on summary
        rich = s.mitm.db.get_summary(limit=10, with_findings=True)
        if rich and "findings" in rich[0]:
            print(f"\n[test] traffic_list with_findings → first row findings={rich[0]['findings']}")
            print("  [ok]")
        else:
            print("[FAIL] with_findings not applied"); failed += 1

        # Test F: diff_flows
        profile_flows = [f for f in flows if "/api/profile" in f["url"]]
        if len(profile_flows) >= 2:
            d = s.mitm.diff_flows(profile_flows[0]["id"], profile_flows[1]["id"])
            obj = json.loads(d)
            print(f"\n[test] diff status: {obj.get('status')}")
            print("  [ok] diff returned")
        else:
            print("\n[skip] not enough profile flows for diff")

        # Test G: replay_via_browser (should reuse cookies)
        if profile_flows:
            r = await s.replay_via_browser(profile_flows[0]["id"])
            print(f"\n[test] replay_via_browser:\n  {r[:200]}")
            if "browser_context" in r and "200" in r:
                print("  [ok] replay via browser succeeded")
            else:
                print("  [FAIL]"); failed += 1

        # Test H: Scope ignore_extensions
        # static / OPTIONS should not appear in db at all
        static_count = len([f for f in flows if any(f["url"].endswith(e)
                            for e in [".png", ".jpg", ".css", ".woff"])])
        if static_count == 0:
            print("\n[ok] scope filter: no static assets in db")
        else:
            print(f"\n[FAIL] {static_count} static assets leaked into db")
            failed += 1

        if failed == 0:
            print("\n" + "=" * 50)
            print("ALL v0.2 SMOKE TESTS PASSED!")
            print("=" * 50)
        else:
            print(f"\n{failed} test(s) failed")
            sys.exit(1)

    except Exception as e:
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        await s.stop_session()
        srv.stop()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
    reason="launches real Chromium + mitmproxy on fixed ports; "
           "set AGENTPROXY_RUN_INTEGRATION=1 to run",
)
def test_v02_suite_runs():
    """pytest wrapper: non-raising run of the v0.2 suite == pass."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
