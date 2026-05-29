"""Regression tests for the correctness + security + AI-native optimization pass.

Covers, as pytest-collectable cases (no live browser / proxy needed):
  A2  SQLite connection lifecycle (contextmanager commits + closes)
  A1  FlowWriter background snapshot/persist + detachment
  B   count_flows, 0600 DB perms, bounded analysis loads
  C   findings UNIQUE(+kind) migration, replay-nonce correlation, param tagging
  D   RuleConfig live mutation helpers (config_* tools' engine)
"""
import os
import stat
import tempfile

import pytest
from mitmproxy.test import tflow

from agent_proxy.core.traffic_db import TrafficDB
from agent_proxy.core.passive_scan import PassiveScanner
from agent_proxy.core.flow_writer import FlowWriter, FlowSnapshot
from agent_proxy.config import load_rule_config


@pytest.fixture
def db_path():
    p = os.path.join(tempfile.mkdtemp(), "regress.db")
    yield p
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(p + suffix)
        except OSError:
            pass


# ----------------------------- A2 -----------------------------

def test_conn_is_closed_after_use(db_path):
    db = TrafficDB(db_path)
    with db._get_conn() as conn:
        conn.execute("SELECT 1")
    # Using a closed connection raises ProgrammingError.
    import sqlite3
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_conn_rolls_back_on_error(db_path):
    db = TrafficDB(db_path)
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        with db._get_conn() as conn:
            conn.execute("INSERT INTO flows (id) VALUES ('x')")
            conn.execute("SELECT * FROM nonexistent_table")
    # The insert in the aborted transaction must not have committed.
    assert db.count_flows() == 0


# ----------------------------- A1 -----------------------------

def test_snapshot_preserves_id_and_detaches(db_path):
    f = tflow.tflow(resp=True)
    f.request.url = "https://t.test/a"
    snap = FlowSnapshot(f)
    assert snap.id == f.id
    original_url = snap.request.url
    f.request.url = "https://mutated/"  # mutate live flow after snapshot
    assert snap.request.url == original_url


def test_flow_writer_persists_and_scans(db_path):
    db = TrafficDB(db_path)
    w = FlowWriter(db, PassiveScanner())
    w.start()
    f = tflow.tflow(resp=True)
    f.response.headers["content-type"] = "application/json"
    f.response.content = b'{"x":1}'
    w.submit(f, scan=True)
    assert w.drain(timeout=3.0)
    w.stop()
    assert db.get_detail(f.id) is not None
    assert db.count_flows() == 1


# ----------------------------- B -----------------------------

def test_db_file_is_owner_only(db_path):
    TrafficDB(db_path)
    mode = stat.S_IMODE(os.stat(db_path).st_mode)
    assert mode == 0o600


def test_count_flows_matches_inserts(db_path):
    db = TrafficDB(db_path)
    assert db.count_flows() == 0
    for i in range(3):
        f = tflow.tflow(resp=True)
        db.save_flow(f)
    assert db.count_flows() == 3


# ----------------------------- C -----------------------------

def test_finding_and_signal_coexist_same_evidence(db_path):
    db = TrafficDB(db_path)
    assert db.add_finding("f1", "ruleA", "low", "cat", "same-ev", kind="signal")
    assert db.add_finding("f1", "ruleA", "high", "cat", "same-ev", kind="finding")
    rows = db.list_findings(flow_id="f1", kind="all")
    kinds = sorted(r["kind"] for r in rows)
    assert kinds == ["finding", "signal"]


def test_replay_nonce_disambiguates_same_endpoint(db_path):
    db = TrafficDB(db_path)
    f1 = tflow.tflow(resp=True)
    f1.request.url = "https://x.test/api"
    f1.request.method = "GET"
    f1.metadata["replay_nonce"] = "NONCE_A"
    f2 = tflow.tflow(resp=True)
    f2.request.url = "https://x.test/api"
    f2.request.method = "GET"
    f2.metadata["replay_nonce"] = "NONCE_B"
    db.save_flow(f1)
    db.save_flow(f2)
    assert db.find_replay_match_by_nonce("NONCE_A") == f1.id
    assert db.find_replay_match_by_nonce("NONCE_B") == f2.id
    assert db.find_replay_match_by_nonce("NONCE_A") != db.find_replay_match_by_nonce("NONCE_B")


@pytest.mark.parametrize("name,cat,should", [
    ("userId", "identity_param", True),
    ("uid", "identity_param", True),
    ("redirect_uri", "ssrf_candidate", True),
    ("csrftoken", "state_token", True),
    ("idea", "object_id_param", False),
    ("photos", "object_storage", False),
    ("description", "expression_candidate", False),
    ("coffee", "money_param", False),
])
def test_param_tagging_precision(name, cat, should):
    from agent_proxy.core.param_extractor import _tags_for
    sp = load_rule_config().semantic_params
    tags = _tags_for(name, sp)
    assert (cat in tags) is should, (name, cat, tags)


# ----------------------------- D -----------------------------

def test_rule_config_live_mutation():
    cfg = load_rule_config()
    n0 = len(cfg.body_rules)
    cfg.add_body_rule("aklt", r"AKLT[0-9A-Za-z]{16,}", "high", "secret_leak")
    assert len(cfg.body_rules) == n0 + 1
    cfg.add_body_rule("aklt", r"AKLT[0-9A-Za-z]{20,}", "high", "secret_leak")
    assert len(cfg.body_rules) == n0 + 1  # replace, not append

    cfg.add_fuzz_payloads("ssti", ["{{7*7}}", "{{7*7}}"])
    assert cfg.fuzz_payloads["ssti"] == ["{{7*7}}"]  # dedup

    cfg.add_semantic_params("identity_param", ["LarkAccountId"])
    assert "larkaccountid" in cfg.semantic_params["identity_param"]


def test_rule_config_bad_regex_raises():
    import re
    cfg = load_rule_config()
    with pytest.raises(re.error):
        cfg.add_body_rule("bad", r"(", "low")
