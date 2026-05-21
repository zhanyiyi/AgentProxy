import argparse
import logging
import sys

from mcp.server.fastmcp import FastMCP

from .core.session_manager import SessionManager
from .models import SessionConfig
from .tools import register_all_tools

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stderr,
)
logger = logging.getLogger("agent_proxy")


def create_server(config: SessionConfig = None, user_config_path: str = None) -> FastMCP:
    cfg = config or SessionConfig()
    session = SessionManager(config=cfg, user_config_path=user_config_path)

    mcp = FastMCP(
        "AgentProxy",
        instructions="AI-Agent-Native Web Debug Proxy - Browser Automation + MITM Traffic Interception",
    )

    register_all_tools(mcp, session)
    return mcp


def main():
    parser = argparse.ArgumentParser(description="AgentProxy - AI Agent Web Debug Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Default MITM proxy port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MITM proxy host (default: 127.0.0.1)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser with UI")
    parser.add_argument("--timeout", type=int, default=30000, help="Browser timeout in ms (default: 30000)")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"], help="MCP transport (default: stdio)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to a YAML rule pack overriding the bundled defaults. "
                             "Falls back to AGENT_PROXY_CONFIG env var, then ./agent_proxy.yaml.")

    args = parser.parse_args()

    config = SessionConfig(
        proxy_port=args.port,
        proxy_host=args.host,
        headless=args.headless,
        browser_timeout=args.timeout,
    )

    mcp = create_server(config, user_config_path=args.config)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
