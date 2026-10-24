import argparse
import asyncio
from contextlib import asynccontextmanager
import faulthandler
from importlib.metadata import version
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

import anyio
from mcp.server.fastmcp import FastMCP

from .core.session_manager import SessionManager
from .models import SessionConfig
from .prompt_loader import load_prompts
from .tools import register_all_tools

logger = logging.getLogger("agent_proxy")


def configure_logging(log_dir: str = None) -> None:
    """Configure process logging once, without writing tool arguments or bodies."""
    directory = Path(log_dir).expanduser() if log_dir else Path.home() / ".agentproxy" / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    import os
    file_handler = RotatingFileHandler(
        directory / f"agent_proxy_{os.getpid()}.log",
        maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [pid=%(process)d] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr), file_handler], force=True,
    )
    faulthandler.enable(file=sys.stderr)


def create_server(config: SessionConfig = None, user_config_path: str = None) -> FastMCP:
    cfg = config or SessionConfig()
    session = SessionManager(config=cfg, user_config_path=user_config_path)

    @asynccontextmanager
    async def lifespan(server):
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()

        def log_task_error(loop, context):
            exception = context.get("exception")
            logger.error(
                "Background task failed: %s", context.get("message", "unknown failure"),
                exc_info=(type(exception), exception, exception.__traceback__) if exception else None,
            )

        loop.set_exception_handler(log_task_error)
        try:
            yield {"session": session}
        finally:
            # MCP uses AnyIO cancellation scopes. The transport may already be
            # cancelled while owned browser/proxy resources still need closing.
            try:
                with anyio.CancelScope(shield=True):
                    await session.stop_session()
            finally:
                loop.set_exception_handler(previous_handler)

    mcp = FastMCP(
        "AgentProxy",
        lifespan=lifespan,
        instructions=(
            "AI-Agent-Native Web Debug Proxy — Browser Automation + MITM "
            "Traffic Interception. If a `pentest_workflow` prompt is "
            "registered, call it once at the start of an engagement to get "
            "the playbook keyed to the current session state."
        ),
    )
    # FastMCP 1.x exposes version on its underlying protocol server rather
    # than its constructor. Report our package version in the MCP handshake.
    mcp._mcp_server.version = version("agent-proxy")

    register_all_tools(mcp, session)
    load_prompts(mcp, session)
    return mcp


def main():
    parser = argparse.ArgumentParser(description="AgentProxy - AI Agent Web Debug Proxy")
    parser.add_argument("--port", type=int, default=8080, help="Default MITM proxy port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="MITM proxy host (default: 127.0.0.1)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser with UI")
    parser.add_argument("--timeout", type=int, default=30000, help="Browser timeout in ms (default: 30000)")
    parser.add_argument("--startup-timeout", type=float, default=60, help="Total startup budget in seconds")
    parser.add_argument("--shutdown-timeout", type=float, default=15, help="Resource cleanup budget in seconds")
    parser.add_argument("--log-dir", default=None, help="Rotating logs directory (default: ~/.agentproxy/logs)")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse", "streamable-http"], help="MCP transport (default: stdio)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to a YAML rule pack overriding the bundled defaults. "
                             "Falls back to AGENT_PROXY_CONFIG env var, then ./agent_proxy.yaml.")
    parser.add_argument("--db-path", type=str, default=None,
                        help="Reopen this capture database; defaults to a new isolated instance directory")

    args = parser.parse_args()
    configure_logging(args.log_dir)

    # The proxy has no authentication. Binding off-loopback turns it into an
    # open MITM relay for anyone on the network — warn loudly.
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "MITM proxy binding to non-loopback host %s with NO authentication. "
            "Anyone who can reach this port (and trusts the CA) can route traffic "
            "through it. Use 127.0.0.1 unless you specifically intend this.",
            args.host,
        )

    config = SessionConfig(
        proxy_port=args.port,
        proxy_host=args.host,
        headless=args.headless,
        browser_timeout=args.timeout,
        startup_timeout=args.startup_timeout,
        shutdown_timeout=args.shutdown_timeout,
        db_path=args.db_path,
    )

    mcp = create_server(config, user_config_path=args.config)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
