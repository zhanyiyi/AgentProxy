# AgentProxy

AgentProxy is an AI-agent-native web debugging proxy. It exposes browser automation, MITM traffic capture, request replay, API discovery, and basic security testing as MCP tools so Codex, Claude Code, Cursor, and other MCP clients can operate a browser and analyze traffic in one workflow.

The core idea is simple:

```text
AI Agent -> MCP stdio -> AgentProxy -> Playwright browser + mitmproxy -> target website
```

AgentProxy can either launch its own Playwright Chromium browser or connect to an already-running Chrome/Chromium instance over CDP. The CDP mode is the recommended mode for manual login, MFA, captcha, password-manager, and real-browser-profile workflows.

## Features

- Start and stop a complete browser + MITM session from MCP.
- Capture HTTP and HTTPS traffic into a local SQLite database.
- Navigate, click, fill, type, run JavaScript, inspect HTML/text, manage cookies, and take screenshots.
- List, search, inspect, replay, and fuzz captured traffic.
- Extract values with JSONPath or CSS selectors.
- Detect common auth signals such as session cookies, bearer tokens, JWTs, API keys, CSRF tokens, and basic auth.
- Reconstruct API endpoint patterns and generate OpenAPI output.
- Connect to an external Chrome/Chromium browser via CDP for manual login and captcha workflows.

## Repository Layout

```text
.
├── config/
│   └── mcp.json              # JSON-style MCP example
├── docs/
│   ├── architecture.md       # Architecture notes
│   ├── design.md             # Tool and module design
│   └── prd.md                # Product requirements
├── src/agent_proxy/
│   ├── main.py               # MCP server entrypoint
│   ├── models.py             # Pydantic models
│   ├── core/                 # Browser, MITM, session, and DB controllers
│   └── tools/                # MCP tool registration
├── tests/
├── pyproject.toml
└── setup.sh
```

## Requirements

Use a Linux machine with Python 3.10 or newer. The project has been tested on Kali/Debian-like systems.

Required system tools:

```bash
python3 --version
python3 -m pip --version
git --version
```

Recommended packages on Debian/Kali/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git wget curl ca-certificates
```

For manual browser windows, the machine must have a working graphical desktop, X11/Wayland session, or a remote desktop/VNC environment. Headless mode does not need a visible desktop.

## Install From Source

Clone or copy this repository to the target machine, then install it in a virtual environment:

```bash
cd /path/to/dpx-flow
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Install Playwright's Chromium browser:

```bash
.venv/bin/python -m playwright install chromium
```

On a fresh Linux machine, Playwright may also ask for additional OS libraries. If so, run:

```bash
.venv/bin/python -m playwright install --with-deps chromium
```

Verify the Python package:

```bash
.venv/bin/python -c "from agent_proxy.main import create_server; print(type(create_server()).__name__)"
```

Expected output:

```text
FastMCP
```

## Optional: Install Google Chrome

External CDP mode works with Google Chrome or Chromium. Chromium from the distribution package is usually enough:

```bash
sudo apt-get install -y chromium
```

If you want Google Chrome Stable:

```bash
cd /tmp
wget -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
google-chrome --version
```

If you do not have sudo access, you can unpack the `.deb` locally:

```bash
mkdir -p ~/.local/opt/google-chrome-stable ~/.local/bin
dpkg-deb -x /tmp/google-chrome-stable_current_amd64.deb ~/.local/opt/google-chrome-stable
cat > ~/.local/bin/google-chrome <<'EOF'
#!/bin/sh
exec "$HOME/.local/opt/google-chrome-stable/opt/google/chrome/google-chrome" "$@"
EOF
chmod +x ~/.local/bin/google-chrome
~/.local/bin/google-chrome --version
```

## Configure Codex MCP

Codex reads MCP servers from `~/.codex/config.toml`. Add this block, replacing the path with your local project path:

```toml
[mcp_servers.agent-proxy]
command = "/path/to/dpx-flow/.venv/bin/python"
args = ["-m", "agent_proxy.main"]
cwd = "/path/to/dpx-flow"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Example for this machine:

```toml
[mcp_servers.agent-proxy]
command = "/home/kali/Desktop/dpx-flow/.venv/bin/python"
args = ["-m", "agent_proxy.main"]
cwd = "/home/kali/Desktop/dpx-flow"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Restart Codex after editing `config.toml`. Use `/mcp` in Codex to confirm that `agent-proxy` is loaded.

The JSON equivalent, useful for other MCP clients, is:

```json
{
  "mcpServers": {
    "agent-proxy": {
      "command": "/path/to/dpx-flow/.venv/bin/python",
      "args": ["-m", "agent_proxy.main"],
      "cwd": "/path/to/dpx-flow"
    }
  }
}
```

## Quick Smoke Test

After Codex loads the MCP server, call:

```text
session_start(proxy_port=8081, headless=true)
browser_navigate(url="https://www.baidu.com", wait_until="domcontentloaded")
session_status()
traffic_list(limit=10)
session_stop()
```

Expected behavior:

- `session_start` starts mitmproxy on `127.0.0.1:8081` and launches a Playwright browser.
- `browser_navigate` returns HTTP 200 and the page title.
- `traffic_list` shows captured traffic from Baidu and related static/resource domains.
- `session_stop` closes the browser and proxy.

## Manual Login / Captcha Mode With External Chrome

Use external Chrome/Chromium mode when you need a visible browser for manual login, password entry, MFA, captcha, or an existing browser profile.

Start Chrome first. The browser must be launched with both a CDP port and a proxy pointing to the AgentProxy MITM port:

```bash
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/agent-proxy-user-profile \
  --proxy-server=http://127.0.0.1:8081 \
  --ignore-certificate-errors \
  --no-sandbox \
  about:blank
```

If you use Chromium:

```bash
chromium \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/agent-proxy-user-profile \
  --proxy-server=http://127.0.0.1:8081 \
  --ignore-certificate-errors \
  --no-sandbox \
  about:blank
```

Then connect AgentProxy to that browser from Codex:

```text
session_connect_cdp(endpoint_url="http://127.0.0.1:9222", proxy_port=8081)
browser_navigate(url="https://www.baidu.com", wait_until="domcontentloaded")
```

Now use the Chrome window manually. Click login, enter credentials, pass captcha/MFA, or perform any other manual workflow. The browser traffic continues to flow through `127.0.0.1:8081`, and AgentProxy stores it in SQLite.

After manual actions, inspect traffic:

```text
session_status()
traffic_search(domain="passport.baidu.com", limit=50)
traffic_auth_detect()
traffic_inspect(flow_id="<flow-id>", full_body=false)
```

Stop the session when finished:

```text
session_stop()
```

If Chrome remains open after `session_stop`, close it manually or kill the process that owns port `9222`:

```bash
ss -ltnp 'sport = :9222'
kill <pid>
```

## Running The MCP Server Manually

You can run the MCP server directly:

```bash
cd /path/to/dpx-flow
.venv/bin/python -m agent_proxy.main
```

The default transport is stdio. For SSE:

```bash
.venv/bin/python -m agent_proxy.main --transport sse
```

Useful flags:

```text
--port 8080          Default MITM proxy port
--host 127.0.0.1     MITM proxy bind host
--headless           Run Playwright browser headless
--no-headless        Run Playwright browser with UI
--timeout 30000      Browser operation timeout in milliseconds
```

## Main MCP Tools

Session:

```text
session_start(proxy_port=8080, headless=true)
session_connect_cdp(endpoint_url="http://127.0.0.1:9222", proxy_port=8080)
session_status()
session_stop()
```

Browser:

```text
browser_navigate(url, wait_until)
browser_click(selector)
browser_fill(selector, value)
browser_type(selector, value, delay)
browser_press_key(key)
browser_screenshot()
browser_get_text(selector?)
browser_get_html(selector?)
browser_execute_js(script)
browser_get_cookies()
browser_set_cookies(cookies_json)
browser_set_headers(headers_json)
browser_set_offline(offline)
browser_accessibility_tree()
```

Traffic:

```text
traffic_list(limit)
traffic_inspect(flow_id, full_body)
traffic_search(query?, domain?, method?, limit)
traffic_clear()
traffic_extract(flow_id, json_path?, css_selector?)
traffic_replay(flow_id, method?, headers_json?, body?, timeout)
traffic_fuzz(flow_id, target_param, param_type, payload_category)
traffic_auth_detect(flow_ids?)
traffic_api_patterns(domain?, limit?)
traffic_openapi(domain?, limit?)
traffic_generate_code(flow_ids, framework)
```

Intercept and scope:

```text
intercept_add_rule(...)
intercept_list_rules()
intercept_remove_rule(rule_id?)
intercept_set_global_header(key, value)
intercept_remove_global_header(key)
scope_set(allowed_domains)
scope_clear()
```

Workflow:

```text
browse_and_capture(url, wait_until, actions)
api_discover(domain?)
security_scan(flow_id, target_param, param_type, payload_categories)
export_session(format, domain?)
```

## Traffic Database

Captured traffic is stored in a local SQLite database:

```text
agent_proxy_traffic.db
```

This database is generated at runtime and is intentionally ignored by Git. It may contain complete request headers, cookies, request bodies, response bodies, login flows, tokens, and other sensitive data from your browser session. Keep it local, delete it when no longer needed, and do not commit it.

Clear captured traffic from MCP:

```text
traffic_clear()
```

Or delete the database when AgentProxy is stopped:

```bash
rm -f agent_proxy_traffic.db
```

## Troubleshooting

### Codex does not show AgentProxy tools

Check `~/.codex/config.toml`:

```toml
[mcp_servers.agent-proxy]
command = "/absolute/path/to/dpx-flow/.venv/bin/python"
args = ["-m", "agent_proxy.main"]
cwd = "/absolute/path/to/dpx-flow"
```

Then restart Codex and run `/mcp`.

### `ModuleNotFoundError: No module named 'agent_proxy'`

Install the project into the virtual environment:

```bash
cd /path/to/dpx-flow
.venv/bin/python -m pip install -e ".[dev]"
```

Make sure Codex's MCP `command` points to that same `.venv/bin/python`.

### Headed browser fails with XServer or DISPLAY error

Headed browser mode requires a working GUI session. Verify:

```bash
echo "$DISPLAY"
xdpyinfo >/dev/null && echo ok
```

If no desktop is available, use headless mode:

```text
session_start(proxy_port=8081, headless=true)
```

Or run inside VNC/Xvfb and connect to that desktop.

### External Chrome CDP connection fails

Check that Chrome is listening:

```bash
ss -ltnp 'sport = :9222'
curl http://127.0.0.1:9222/json/version
```

If nothing is listening, start Chrome again with:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/agent-proxy-user-profile --proxy-server=http://127.0.0.1:8081 --ignore-certificate-errors --no-sandbox about:blank
```

### Port 8081 or 9222 is already in use

Find and stop the owning process:

```bash
ss -ltnp 'sport = :8081'
ss -ltnp 'sport = :9222'
kill <pid>
```

Or use a different proxy port:

```text
session_start(proxy_port=8090, headless=true)
session_connect_cdp(endpoint_url="http://127.0.0.1:9222", proxy_port=8090)
```

If using external Chrome, its `--proxy-server` port must match the `proxy_port` passed to `session_connect_cdp`.

### HTTPS pages load but some resources fail

For the built-in Playwright browser, AgentProxy launches with `ignore_https_errors` and Chrome certificate-error flags.

For external Chrome, include:

```bash
--ignore-certificate-errors
```

Some sites may still enforce extra TLS, certificate pinning, bot checks, or browser integrity checks. Use a real Chrome profile and manual mode when possible.

## Development

Run tests:

```bash
cd /path/to/dpx-flow
.venv/bin/python -m pytest
```

Run a local import check:

```bash
.venv/bin/python -c "from agent_proxy.core.session_manager import SessionManager; print('ok')"
```

Run the MCP server:

```bash
.venv/bin/python -m agent_proxy.main
```

## Notes

AgentProxy is designed for local, authorized debugging and security testing. It captures browser traffic very completely. Treat captured traffic and generated replay commands as sensitive local artifacts.
