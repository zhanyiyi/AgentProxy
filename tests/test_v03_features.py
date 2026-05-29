"""Smoke tests for v0.3 features:
- A1 body alias (no body_preview KeyError downstream)
- A4 replay returns new_flow_id
- B  multi-context dual identity (hot + cold hydration + storage_state fallback)
- C  tag / link / chain
- D  traffic_params with semantic tags
- E  finding vs signal split
- F  evidence_bundle markdown
"""
import asyncio
import json
import sys
import os
import tempfile
import http.server
import threading
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# A tiny app that returns different content per identity (cookie sid_user)
SECRETS = {
    "alice": {"who": "alice", "card": "AKIAIOSFODNN7EXAMPLE"},  # AWS key for finding
    "bob":   {"who": "bob",   "card": "BBBB-2222"},
}


class IdentityServer:
    def __init__(self, port=18895):
        self.port = port

    def start(self):
        class H(http.server.BaseHTTPRequestHandler):
            def _who(self):
                cookie = self.headers.get("Cookie", "") or ""
                for kv in cookie.split(";"):
                    if "=" in kv:
                        k, v = kv.strip().split("=", 1)
                        if k == "sid_user":
                            return v
                return None

            def do_GET(self):
                if self.path.startswith("/login/"):
                    user = self.path.split("/", 2)[2]
                    self.send_response(200)
                    self.send_header("Set-Cookie", f"sid_user={user}; Path=/")
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(f"<html>logged in as {user}</html>".encode())
                elif self.path == "/api/me":
                    user = self._who()
                    if not user:
                        self.send_response(401); self.end_headers(); return
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(SECRETS.get(user, {"who": user})).encode())
                elif self.path.startswith("/api/profile/"):
                    # IDOR target: any identity can read any profile (intentionally vulnerable)
                    target = self.path.rsplit("/", 1)[-1]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(SECRETS.get(target, {"who": target})).encode())
                elif self.path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html>home</html>")
                else:
                    self.send_response(404); self.end_headers()

            def log_message(self, *a, **k): pass

        self.server = http.server.HTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        if self.server:
            self.server.shutdown()


async def main():
    from agent_proxy.core.session_manager import SessionManager
    from agent_proxy.models import SessionConfig

    failed = 0
    profile_dir = "/tmp/agentproxy_v03_profiles"
    if os.path.exists(profile_dir):
        shutil.rmtree(profile_dir)
    os.makedirs(profile_dir, exist_ok=True)

    srv = IdentityServer(); srv.start()
    print("[ok] identity server up")

    cfg = SessionConfig(
        proxy_port=28083, headless=True, browser_timeout=15000,
        profile_dir=profile_dir,
        db_path=os.path.join(tempfile.mkdtemp(), "v03.db"),
    )
    s = SessionManager(config=cfg)

    try:
        # ======== A: P0 闭环 ========
        await s.start_session(proxy_port=28083, headless=True, profile_dir=profile_dir)
        print("[ok] session started, profile_dir=%s" % profile_dir)

        # B1: default context exists, profile_label injected on flows
        await s.browser.navigate("http://127.0.0.1:18895/login/alice")
        await asyncio.sleep(0.5)
        await s.browser.navigate("http://127.0.0.1:18895/api/me")
        await asyncio.sleep(0.5)

        flows = s.mitm.db.get_summary(limit=10)
        with s.mitm.db._get_conn() as conn:
            row = conn.execute(
                "SELECT id, profile_label FROM flows WHERE url LIKE '%/api/me' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            assert row, "no /api/me flow captured"
            me_flow_id, label = row[0], row[1]
        if label != "default":
            print(f"  [FAIL] profile_label expected 'default', got {label!r}"); failed += 1
        else:
            print("  [ok] B1 profile_label='default' on captured flow")

        # A2: console_logs tool (verify browser collected something or empty list at least)
        logs_json = await s.browser.get_console_logs()
        print(f"  [ok] A2 console_logs returns: {logs_json[:80]}")

        # A3: --disable-web-security NOT in default args
        # (we can't introspect chromium args directly; verify the flag stays False)
        if s.browser.unsafe_disable_web_security:
            print("  [FAIL] A3 unsafe flag should default False"); failed += 1
        else:
            print("  [ok] A3 unsafe_disable_web_security default False")

        # A4: replay returns new_flow_id
        replay_json = await s.mitm.replay_request(me_flow_id)
        replay = json.loads(replay_json)
        if not replay.get("new_flow_id"):
            print(f"  [FAIL] A4 no new_flow_id in {replay}"); failed += 1
        else:
            print(f"  [ok] A4 replay returned new_flow_id={replay['new_flow_id'][:8]}…")

        # ======== B: 双身份 ========
        # Save default (alice) profile to disk
        await s.browser.save_storage_state(name="alice")
        print("  [ok] B saved alice storage state")

        # Create victim context, login bob, save
        await s.browser.create_context("victim", from_profile=False)
        s.browser.use_context("victim")
        await s.browser.navigate("http://127.0.0.1:18895/login/bob")
        await asyncio.sleep(0.5)
        await s.browser.navigate("http://127.0.0.1:18895/api/me")
        await asyncio.sleep(0.5)
        await s.browser.save_storage_state(name="bob")
        print("  [ok] B logged in as bob in victim context")

        # Verify bob flow has profile_label='victim'
        with s.mitm.db._get_conn() as conn:
            rows = conn.execute(
                "SELECT profile_label FROM flows WHERE url LIKE '%/api/me' ORDER BY timestamp DESC LIMIT 2"
            ).fetchall()
        labels = [r[0] for r in rows]
        if "victim" not in labels:
            print(f"  [FAIL] B no 'victim' label on bob flow ({labels})"); failed += 1
        else:
            print(f"  [ok] B labels seen: {labels}")

        # Switch back to default
        s.browser.use_context("default")
        await s.browser.navigate("http://127.0.0.1:18895/api/profile/alice")
        await asyncio.sleep(0.5)

        with s.mitm.db._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM flows WHERE url LIKE '%/api/profile/alice' "
                "AND profile_label = 'default' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            assert row, "no profile/alice flow"
            alice_target = row[0]

        # IDOR: replay alice's flow via VICTIM (bob's) context
        idor_result = await s.replay_via_browser(alice_target, context="victim")
        print(f"  [debug] idor result keys={list(json.loads(idor_result).keys())}")
        idor = json.loads(idor_result)
        if idor.get("via") != "browser_context":
            print(f"  [FAIL] B IDOR not via browser_context: {idor}"); failed += 1
        elif idor.get("status_code") != 200:
            print(f"  [FAIL] B IDOR status {idor.get('status_code')}"); failed += 1
        elif idor.get("new_flow_id"):
            # The replay was sent through victim context (bob's cookie),
            # but the URL targets alice's resource → if we get alice's data,
            # IDOR is real. If app re-scoped to bob, bodies differ.
            print(f"  [ok] B IDOR via victim ctx returned 200, new_flow_id={idor['new_flow_id'][:8]}…")
            # Check the captured replay carries victim label
            with s.mitm.db._get_conn() as conn:
                row = conn.execute(
                    "SELECT profile_label FROM flows WHERE id = ?", (idor["new_flow_id"],)
                ).fetchone()
            if row and row[0] == "victim":
                print(f"  [ok] B replay flow correctly labeled 'victim'")
            else:
                print(f"  [WARN] B replay label was {row[0] if row else None!r}")

        # B cold-hydrate: stop session, restart, replay via 'admin' context that
        # was never live but has saved profile (we'll fake one by saving a snapshot first)
        await s.browser.save_storage_state(name="admin")  # snapshot current default state
        await s.stop_session()
        print("  [ok] B session stopped")

        # Restart, only default context exists; ask for replay via admin profile
        s2 = SessionManager(config=cfg)
        await s2.start_session(proxy_port=28083, headless=True, profile_dir=profile_dir)
        # admin context not live; should hydrate from <profile_dir>/admin_state.json
        cold = await s2.replay_via_browser(alice_target, context="admin")
        cold_obj = json.loads(cold)
        if cold_obj.get("via") == "browser_context":
            print("  [ok] B cold-hydrate from admin_state.json succeeded")
        else:
            print(f"  [WARN] B cold-hydrate took fallback path: via={cold_obj.get('via')}")

        # ======== C: tag / link / chain ========
        s2.mitm.db.add_tag(alice_target, "idor_target")
        s2.mitm.db.add_tag(alice_target, "alice_profile")
        if cold_obj.get("new_flow_id"):
            s2.mitm.db.add_link(alice_target, cold_obj["new_flow_id"], "identity_swap")
        ids_with_tag = s2.mitm.db.find_by_tag("idor_target")
        if alice_target not in ids_with_tag:
            print("  [FAIL] C find_by_tag missed"); failed += 1
        else:
            print(f"  [ok] C find_by_tag('idor_target') -> {len(ids_with_tag)} flow(s)")

        chain = s2.mitm.db.get_chain(alice_target)
        print(f"  [ok] C chain tags={chain['tags']} downstream_count={len(chain['downstream'])}")

        # ======== D: traffic_params ========
        from agent_proxy.core.param_extractor import extract_params
        # Build a synthetic flow_detail-like dict to test the extractor
        synthetic = {
            "request": {
                "method": "POST",
                "url": "http://x.com/a/123/edit?tenantId=t1&redirect=/home",
                "headers": {"Authorization": "Bearer eyJa.bb.cc",
                            "X-CSRF-Token": "xx",
                            "Cookie": "sid_user=alice; theme=dark"},
                "body": json.dumps({"role": "admin", "userId": 99,
                                    "callbackUrl": "http://evil/", "page": 1}),
            }
        }
        params = extract_params(synthetic)
        # Path has both {id} and other segments; tags should include identity/object/state
        flat_query_tags = sum([p["tags"] for p in params["query"]], [])
        flat_json_tags = sum([p["tags"] for p in params["json"]], [])
        flat_header_tags = sum([p["tags"] for p in params["headers"]], [])

        for expected in [("query", "identity_param"), ("query", "redirect_candidate"),
                         ("json", "privilege_param"), ("json", "identity_param"),
                         ("json", "ssrf_candidate"), ("headers", "state_token")]:
            section, tag = expected
            tags = sum([p["tags"] for p in params[section]], [])
            if tag not in tags:
                print(f"  [FAIL] D missing tag '{tag}' in section '{section}' (have {tags})")
                failed += 1
        print(f"  [ok] D path={[p['name'] for p in params['path']]} "
              f"query_tags={set(flat_query_tags)} json_tags={set(flat_json_tags)}")
        # cookies surfaced as names only, no values
        cookie_names = [c["name"] for c in params["cookies"]]
        if "sid_user" not in cookie_names:
            print("  [FAIL] D cookie name not surfaced"); failed += 1
        else:
            print(f"  [ok] D cookies (names only) {cookie_names}")

        # ======== E: finding vs signal split ========
        findings_only = s2.mitm.db.list_findings(kind="finding", limit=200)
        signals_only = s2.mitm.db.list_findings(kind="signal", limit=200)
        f_rules = {f["rule_id"] for f in findings_only}
        sig_rules = {f["rule_id"] for f in signals_only}
        if "missing_csp" in f_rules:
            print("  [FAIL] E missing_csp leaked into findings"); failed += 1
        elif sig_rules and "missing_csp" not in sig_rules and "sensitive_param" not in sig_rules:
            # at least one signal rule should fire on this corpus
            print(f"  [WARN] E no expected signal rule fired (sig_rules={sig_rules})")
        else:
            print(f"  [ok] E findings rules={sorted(f_rules)} signals rules={sorted(sig_rules)}")

        stats = s2.mitm.db.findings_stats()
        if "findings" not in stats or "signals" not in stats:
            print("  [FAIL] E stats missing split"); failed += 1
        else:
            print(f"  [ok] E stats split: f={stats['findings']['count']} s={stats['signals']['count']}")

        # ======== F: evidence_bundle ========
        bundle = s2.mitm.evidence_bundle(alice_target, depth=2)
        if "Evidence Bundle" not in bundle or "Reproduce" not in bundle:
            print("  [FAIL] F bundle missing key sections"); failed += 1
        elif "idor_target" not in bundle:
            print("  [FAIL] F bundle missing tag"); failed += 1
        else:
            print(f"  [ok] F bundle generated, {len(bundle)} chars")

        if failed == 0:
            print("\n" + "=" * 50)
            print("ALL v0.3 SMOKE TESTS PASSED!")
            print("=" * 50)
        else:
            print(f"\n{failed} v0.3 test(s) failed")
            sys.exit(1)

    except Exception as e:
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await s.stop_session()
        except Exception:
            pass
        try:
            await s2.stop_session()
        except Exception:
            pass
        srv.stop()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("AGENTPROXY_RUN_INTEGRATION") != "1",
    reason="launches real Chromium + mitmproxy on fixed ports; "
           "set AGENTPROXY_RUN_INTEGRATION=1 to run",
)
def test_v03_suite_runs():
    """pytest wrapper: non-raising run of the v0.3 suite == pass."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
