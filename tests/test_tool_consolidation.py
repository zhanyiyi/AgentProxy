"""Tests for the Phase-1 tool-surface consolidation (77 -> 64).

Guards the consolidated surface (so a removed tool can't silently reappear and
re-bloat the agent's per-turn schema budget) and exercises the merged-tool
dispatch (config_add kinds, traffic_extract regex+save_as) through the real
FastMCP call_tool path. No live proxy/browser needed — these tools touch only
the rule pack and the DB.
"""
import json

import pytest

from agent_proxy.main import create_server

REMOVED = {
    "traffic_replay_via_browser", "traffic_findings_stats",
    "config_add_passive_rule", "config_add_fuzz_payloads", "config_add_semantic_params",
    "traffic_extract_session_variable", "intercept_set_global_header",
    "intercept_remove_global_header", "scope_clear", "traffic_api_patterns",
    "traffic_openapi", "security_scan", "api_discover",
    "cert_install_firefox", "cert_install_chrome",
}
MERGED = {
    "traffic_replay", "traffic_findings", "config_add", "traffic_extract",
    "scope_set", "export_session", "cert_install", "traffic_fuzz",
}


async def _tool_names(mcp):
    return {t.name for t in await mcp.list_tools()}


async def _call(mcp, name, **args):
    """Return the text payload of a call_tool result across FastMCP versions."""
    res = await mcp.call_tool(name, args)
    content = res[0] if isinstance(res, tuple) else res
    block = content[0]
    return getattr(block, "text", block)


@pytest.mark.asyncio
async def test_consolidated_surface_has_no_removed_tools():
    mcp = create_server()
    names = await _tool_names(mcp)
    assert REMOVED & names == set(), f"removed tools reappeared: {REMOVED & names}"
    assert MERGED <= names
    # Budget guard: keep the surface lean. 64 today; alert if it creeps back up.
    assert len(names) <= 66, f"tool surface grew to {len(names)}"


@pytest.mark.asyncio
async def test_config_add_semantic_then_tags_param():
    mcp = create_server()
    out = json.loads(await _call(mcp, "config_add", kind="semantic",
                                 category="identity_param", words=["larkAccountId"]))
    assert out["status"] == "ok"
    assert "larkaccountid" in out["words_in_category"]


@pytest.mark.asyncio
async def test_config_add_fuzz_appends_payloads():
    mcp = create_server()
    out = json.loads(await _call(mcp, "config_add", kind="fuzz",
                                 category="ssti", payloads=["{{7*7}}", "${7*7}"]))
    assert out["status"] == "ok"
    assert "{{7*7}}" in out["payloads_in_category"] and "${7*7}" in out["payloads_in_category"]


@pytest.mark.asyncio
async def test_config_add_bad_regex_is_json_error():
    mcp = create_server()
    out = json.loads(await _call(mcp, "config_add", kind="passive_rule",
                                 rule_id="bad", regex="(unclosed", rescan=False))
    assert out["status"] == "error"
    assert "invalid regex" in out["error"]


@pytest.mark.asyncio
async def test_config_add_unknown_kind():
    mcp = create_server()
    out = json.loads(await _call(mcp, "config_add", kind="bogus"))
    assert out["status"] == "error"


@pytest.mark.asyncio
async def test_traffic_extract_regex_save_as_sets_session_var():
    server = create_server()
    sm = _session_of(server)
    from mitmproxy.test import tflow
    f = tflow.tflow(resp=True)
    f.response.content = b'{"ticket": "T-4242"}'
    sm.mitm.db.save_flow(f)

    out = await _call(server, "traffic_extract", flow_id=f.id,
                      regex=r'"ticket":\s*"([^"]+)"', save_as="ticket")
    assert "T-4242" in out
    assert sm.mitm.session_variables.get("ticket") == "T-4242"


def _session_of(mcp):
    """Pull the SessionManager captured in the tool closures (test-only)."""
    for t in mcp._tool_manager._tools.values():
        fn = getattr(t, "fn", None)
        if fn and fn.__closure__:
            for cell in fn.__closure__:
                obj = cell.cell_contents
                if obj.__class__.__name__ == "SessionManager":
                    return obj
    raise AssertionError("SessionManager not found in tool closures")
