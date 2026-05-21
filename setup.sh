#!/bin/bash
set -e

echo "=== AgentProxy Setup ==="

echo "[1/4] Installing Python dependencies..."
pip install -e ".[dev]" 2>&1 | tail -3

echo "[2/4] Installing Playwright browsers..."
python -m playwright install chromium 2>&1 | tail -3

echo "[3/4] Installing mitmproxy certificates..."
python -c "
import subprocess, os, sys
cert_dir = os.path.expanduser('~/.mitmproxy')
if not os.path.exists(os.path.join(cert_dir, 'mitmproxy-ca-cert.pem')):
    print('Generating mitmproxy CA certificate...')
    subprocess.run([sys.executable, '-m', 'mitmproxy', '--help'], capture_output=True)
else:
    print('mitmproxy CA certificate already exists.')
"

echo "[4/4] Verifying installation..."
python -c "
from agent_proxy.core.session_manager import SessionManager
from agent_proxy.core.mitm_controller import MitmController
from agent_proxy.core.browser_controller import BrowserController
print('All core modules imported successfully!')
"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Usage with Claude Code / Codex:"
echo "  Add to .mcp.json:"
echo '  {"mcpServers":{"agent-proxy":{"command":"python","args":["-m","agent_proxy.main"]}}}'
echo ""
echo "Or run standalone:"
echo "  python -m agent_proxy.main"
echo ""
echo "For headful browser (with UI):"
echo '  {"mcpServers":{"agent-proxy":{"command":"python","args":["-m","agent_proxy.main","--no-headless"]}}}'
