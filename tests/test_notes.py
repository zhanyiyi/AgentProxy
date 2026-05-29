"""Smoke tests for triage notes (flow_notes table + note tools + prompt)."""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def main():
    from agent_proxy.core.traffic_db import TrafficDB

    failed = 0

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "notes_test.db")
        db = TrafficDB(db_path)

        # 1. Insert a fresh note
        note = db.upsert_note(
            flow_id="abc-123",
            verdict="not_vulnerable",
            scenario="POST /api/order/cancel; orderId in JSON",
            sensitive_fields="orderId (object_id_param), userId (identity_param)",
            test_steps="Replayed via victim ctx -> 403; mutated orderId -> identical baseline",
            conclusion="Server enforces ownership check before action. Did not test cross-tenant.",
        )
        if note["verdict"] != "not_vulnerable":
            print(f"  [FAIL] verdict not stored: {note}"); failed += 1
        else:
            print("  [ok] insert note + verdict roundtrip")

        # 2. Same flow_id overwrites instead of stacking
        note2 = db.upsert_note(
            flow_id="abc-123",
            verdict="inconclusive",
            scenario="re-investigated",
            test_steps="tried admin token, still 403",
            conclusion="needs cross-tenant followup",
        )
        all_for_flow = db.list_notes(flow_id="abc-123")
        if len(all_for_flow) != 1:
            print(f"  [FAIL] expected 1 note, got {len(all_for_flow)}"); failed += 1
        elif all_for_flow[0]["verdict"] != "inconclusive":
            print(f"  [FAIL] overwrite didn't apply: {all_for_flow[0]['verdict']}"); failed += 1
        else:
            print("  [ok] same flow_id overwrites note (verdict updated)")

        if note2["created_at"] != note["created_at"]:
            print("  [FAIL] created_at must be preserved on update"); failed += 1
        else:
            print("  [ok] created_at preserved on overwrite")
        if note2["updated_at"] < note2["created_at"]:
            print("  [FAIL] updated_at < created_at"); failed += 1

        # 3. Verdict enum is enforced
        try:
            db.upsert_note(flow_id="bad", verdict="exploitable")
            print("  [FAIL] bad verdict was accepted"); failed += 1
        except ValueError:
            print("  [ok] verdict enum enforced")

        # 4. Field length cap
        big = "x" * 5000
        n = db.upsert_note(flow_id="big-001", verdict="vulnerable", scenario=big)
        if len(n["scenario"]) > 1500:
            print(f"  [FAIL] scenario not capped: {len(n['scenario'])} chars"); failed += 1
        else:
            print(f"  [ok] scenario capped at {len(n['scenario'])} chars")

        # 5. Multiple flows + verdict filter
        db.upsert_note(flow_id="vuln-1", verdict="vulnerable",
                       conclusion="reflected XSS, see flow xyz-789")
        db.upsert_note(flow_id="incon-1", verdict="inconclusive",
                       conclusion="needs OOB to verify SSRF")
        vuln = db.list_notes(verdict="vulnerable")
        ids = {n["flow_id"] for n in vuln}
        if "vuln-1" not in ids or "big-001" not in ids:
            print(f"  [FAIL] verdict filter wrong: {ids}"); failed += 1
        else:
            print(f"  [ok] verdict='vulnerable' filter returned {len(vuln)}")

        # 6. notes_stats
        stats = db.notes_stats()
        if stats["total"] != 4:  # abc-123 + big-001 + vuln-1 + incon-1
            print(f"  [FAIL] expected 4 total, got {stats}"); failed += 1
        else:
            print(f"  [ok] notes_stats total={stats['total']} by_verdict={stats['by_verdict']}")

        # 7. Removal
        ok = db.remove_note("abc-123")
        if not ok or db.get_note("abc-123") is not None:
            print("  [FAIL] remove failed"); failed += 1
        else:
            print("  [ok] remove_note works")

        # 8. clear() wipes notes too
        db.clear()
        if db.notes_stats()["total"] != 0:
            print("  [FAIL] clear didn't wipe notes"); failed += 1
        else:
            print("  [ok] clear() wipes flow_notes")

    # 9. evidence_bundle includes note section
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "evidence.db")
        from agent_proxy.core.mitm_controller import MitmController
        m = MitmController(db_path=db_path)

        # synthesize a flow row directly so we don't need a live mitm session
        with m.db._get_conn() as conn:
            import time
            conn.execute(
                "INSERT INTO flows (id, url, method, status_code, request_headers, "
                "response_headers, timestamp, size) VALUES (?,?,?,?,?,?,?,?)",
                ("flow-x", "https://target/api/me", "GET", 200,
                 '[["host","target"]]', '[["content-type","application/json"]]',
                 time.time(), 12),
            )
        m.db.upsert_note(
            flow_id="flow-x", verdict="vulnerable",
            scenario="auth-required JSON endpoint",
            sensitive_fields="userId in cookie",
            test_steps="replayed via victim ctx, got victim's data",
            conclusion="BOLA — see flow flow-y for proof",
        )
        bundle = m.evidence_bundle("flow-x", depth=1)
        for needle in ("Triage note", "vulnerable", "BOLA", "Sensitive fields"):
            if needle not in bundle:
                print(f"  [FAIL] evidence_bundle missing '{needle}'"); failed += 1
                break
        else:
            print("  [ok] evidence_bundle embeds the triage note")

    if failed == 0:
        print("\n" + "=" * 50)
        print("ALL note smoke tests PASSED")
        print("=" * 50)
    else:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)


def test_notes_suite_runs():
    """pytest wrapper: a non-raising run of the smoke suite == pass."""
    main()


if __name__ == "__main__":
    main()
