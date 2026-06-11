"""Tests for the ② cross-flow correlation layer + the Tencent/COS rule-pack
additions (the optimize/correctness-security-polish dataflow pass).

All pytest-collectable, no live browser/proxy:
  - TrafficAnalyzer.correlate_dataflow: value_passthrough edges, cross-identity
    secret reuse, frequency-cap noise control, causality (source before consumer)
  - passive body_rules fire on real Tencent STS / COS-signed-URL / AKID samples
  - semantic_params additions are tagged by the param extractor
"""
import json
import os
import tempfile

import pytest
from mitmproxy.test import tflow

from agent_proxy.core.traffic_db import TrafficDB
from agent_proxy.core.traffic_analysis import TrafficAnalyzer
from agent_proxy.core.passive_scan import PassiveScanner
from agent_proxy.config import load_rule_config


@pytest.fixture
def db_path():
    p = os.path.join(tempfile.mkdtemp(), "dataflow.db")
    yield p
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(p + suffix)
        except OSError:
            pass


def _seed(db, url, method="GET", status=200, req_body=None,
          resp_body=b"{}", label=None, ts=None):
    f = tflow.tflow(resp=True)
    f.request.url = url
    f.request.method = method
    if req_body is not None:
        f.request.content = req_body
    f.response.status_code = status
    f.response.headers["content-type"] = "application/json"
    f.response.content = resp_body
    db.save_flow(f, profile_label=label)
    if ts is not None:
        with db._get_conn() as c:
            c.execute("UPDATE flows SET timestamp=? WHERE id=?", (ts, f.id))
    return f.id


# ---------------- correlate_dataflow ----------------

_CODE = "071jWp000r6KjT1MrZ300a8RmS2jWp0GXYZ"  # 24+ char opaque oauth code


def test_correlate_links_response_value_into_later_request(db_path):
    db = TrafficDB(db_path)
    a = _seed(db, "https://m.x.com/authorize",
              resp_body=json.dumps({"code": _CODE}).encode(), ts=100)
    b = _seed(db, "https://w.x.com/callback?code=" + _CODE, ts=200)
    _seed(db, "https://x.com/unrelated", ts=150)

    out = json.loads(TrafficAnalyzer(db).correlate_dataflow())
    assert any(e["source"] == a and e["target"] == b for e in out["edges"])
    # edge persisted into the graph traffic_chain/evidence_bundle read
    chain = db.get_chain(a, depth=2)
    assert any(d["flow_id"] == b for d in chain["downstream"])
    # a dataflow signal was written on the consumer
    sigs = db.list_findings(flow_id=b, category="dataflow", kind="signal")
    assert sigs and sigs[0]["rule_id"] == "dataflow_passthrough"


def test_correlate_respects_causality(db_path):
    """A consumer that happened BEFORE the source must not be linked."""
    db = TrafficDB(db_path)
    a = _seed(db, "https://m.x.com/authorize",
              resp_body=json.dumps({"code": _CODE}).encode(), ts=300)
    early = _seed(db, "https://w.x.com/callback?code=" + _CODE, ts=100)
    out = json.loads(TrafficAnalyzer(db).correlate_dataflow())
    assert not any(e["target"] == early for e in out["edges"])


def test_correlate_cross_identity_secret_reuse(db_path):
    db = TrafficDB(db_path)
    sts = "AKIDEXAMPLEFAKESTSCREDDONOTUSE00"
    s1 = _seed(db, "https://up.x.com/sts",
               resp_body=json.dumps({"tmpSecretId": sts}).encode(),
               label="victim", ts=300)
    _seed(db, "https://cos.x.com/put?ak=" + sts, label="attacker", ts=400)
    out = json.loads(TrafficAnalyzer(db).correlate_dataflow())
    assert out["cross_identity_secret_reuse"]
    hi = db.list_findings(rule_id="cross_identity_secret_reuse", kind="finding")
    assert hi and hi[0]["severity"] == "high"


def test_correlate_frequency_cap_skips_global_value(db_path):
    """A value minted by many flows (e.g. a session token on every response)
    is global noise and must not generate edges."""
    db = TrafficDB(db_path)
    glob = "abcdef0123456789abcdef0123456789abcd"  # long opaque, minted widely
    for i in range(10):
        _seed(db, f"https://x.com/page{i}",
              resp_body=json.dumps({"t": glob}).encode(), ts=i)
    consumer = _seed(db, "https://x.com/use?t=" + glob, ts=100)
    out = json.loads(TrafficAnalyzer(db).correlate_dataflow(freq_cap=8))
    assert not any(e["target"] == consumer for e in out["edges"])


# ---------------- passive body_rules (Tencent/COS) ----------------

@pytest.mark.parametrize("name,blob,expect_rule", [
    ("akid", "q-ak=AKIDEXAMPLEFAKEKEYDONOTUSE00", "tencent_access_key"),
    ("sts_json", '{"credentials":{"tmpSecretId":"x","tmpSecretKey":"y"}}', "tencent_sts_credential"),
    ("cos_url",
     "https://p.x.com/a.png?q-sign-algorithm=sha1&q-ak=AKIDEXAMPLEFAKEKEYDONOTUSE00"
     "&q-sign-time=1;2&q-signature=" + "0" * 40,
     "cos_presigned_url"),
])
def test_tencent_body_rule_fires(db_path, name, blob, expect_rule):
    db = TrafficDB(db_path)
    f = tflow.tflow(resp=True)
    f.response.headers["content-type"] = "application/json"
    f.response.content = blob.encode()
    PassiveScanner(rules=load_rule_config()).scan(f, db)
    ids = {r["rule_id"] for r in db.list_findings(flow_id=f.id, kind="all")}
    assert expect_rule in ids


def test_aws_key_does_not_trip_tencent_rule(db_path):
    db = TrafficDB(db_path)
    f = tflow.tflow(resp=True)
    f.response.headers["content-type"] = "text/plain"
    f.response.content = b"AKIAIOSFODNN7EXAMPLE"
    PassiveScanner(rules=load_rule_config()).scan(f, db)
    ids = {r["rule_id"] for r in db.list_findings(flow_id=f.id, kind="all")}
    assert "aws_access_key" in ids
    assert "tencent_access_key" not in ids


# ---------------- semantic_params additions ----------------

@pytest.mark.parametrize("param,cat", [
    ("fileurl", "ssrf_candidate"),
    ("link", "redirect_candidate"),
    ("tmpsecretid", "object_storage"),
])
def test_new_semantic_words_tagged(param, cat):
    from agent_proxy.core.param_extractor import _tags_for
    cfg = load_rule_config()
    assert cat in _tags_for(param, cfg.semantic_params)


def test_dataflow_suite_runs():
    """pytest wrapper marker so the module is obviously a suite."""
    assert True


# ---------------- review-driven hardening ----------------

def test_max_edges_cap_is_reported_not_silent(db_path):
    """When max_edges is hit, the result must say so rather than silently
    dropping (review should-fix)."""
    db = TrafficDB(db_path)
    # one minted value consumed by several later flows
    val = "071jWp000r6KjT1MrZ300a8RmS2jWp0Gabc"
    src = _seed(db, "https://x.com/mint",
                resp_body=json.dumps({"code": val}).encode(), ts=1)
    for i in range(5):
        _seed(db, f"https://x.com/use{i}?code=" + val, ts=10 + i)
    out = json.loads(TrafficAnalyzer(db).correlate_dataflow(max_edges=2))
    assert out["edges_created"] == 2
    assert out["edges_capped"] is True
    assert out["edges_suppressed"] >= 1


def test_generic_token_not_sliced_from_long_blob(db_path):
    """A long base64/opaque blob in a response must not be sliced into a 28-char
    substring that then 'matches' an unrelated request (review false-positive)."""
    db = TrafficDB(db_path)
    blob = "A" * 90  # 90-char opaque run, bounded by quotes in JSON
    _seed(db, "https://x.com/mint",
          resp_body=json.dumps({"data": blob}).encode(), ts=1)
    # a later request carries a DIFFERENT 40-char run — must not link
    other = "B" * 40
    consumer = _seed(db, "https://x.com/use?x=" + other, ts=2)
    out = json.loads(TrafficAnalyzer(db).correlate_dataflow())
    assert not any(e["target"] == consumer for e in out["edges"])
