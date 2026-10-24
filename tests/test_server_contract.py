"""Protocol contracts that do not need a browser or a listening proxy."""
import json
from importlib.metadata import version

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from agent_proxy.main import create_server
from agent_proxy.models import SessionConfig
from agent_proxy.prompt_loader import _build_prompt_callable


async def test_workflow_tools_and_errors(tmp_path):
    server = create_server(SessionConfig(db_path=str(tmp_path / "capture.db")))
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert tools["browser_snapshot"].annotations.readOnlyHint is True
    assert tools["browser_act"].annotations.readOnlyHint is False
    assert tools["browser_tabs"].annotations.destructiveHint is True
    with pytest.raises(ToolError, match="Flow not found"):
        await server.call_tool("traffic_inspect", {"flow_id": "missing"})
    result = await server.call_tool("session_timeline", {})
    content = result[0] if isinstance(result, tuple) else result
    assert json.loads(content[0].text) == {"actions": []}
    assert server._mcp_server.create_initialization_options().server_version == version("agent-proxy")


@pytest.mark.parametrize("names", [["not-an-identifier"], ["class"], ["same", "same"]])
def test_prompt_names_are_data_not_source(names):
    with pytest.raises(ValueError):
        _build_prompt_callable("test", "", "", [{"name": name} for name in names], None, None)
