# AgentProxy

AgentProxy is an AI-agent-native web debugging proxy. It exposes browser automation, MITM traffic capture, request replay, API discovery, **passive vulnerability scanning**, and basic security testing as MCP tools so Codex, Claude Code, Cursor, and other MCP clients can operate a browser and analyze traffic in one workflow.

The core idea is simple:

```text
AI Agent -> MCP stdio -> AgentProxy -> Playwright browser + mitmproxy -> target website
                                          │
                                          └─→ SQLite (flows + findings tables)
```

AgentProxy can either launch its own Playwright Chromium browser or connect to an already-running Chrome/Chromium instance over CDP. The CDP mode is the recommended mode for manual login, MFA, captcha, password-manager, and real-browser-profile workflows.

## Features

- Start and stop a complete browser + MITM session from MCP.
- Capture HTTP and HTTPS traffic into a local SQLite database.
- **Passive scanner with finding/signal split** — every captured response is auto-checked against 10 rules; high-confidence findings are surfaced separately from low-confidence signals so the agent's context isn't drowned by noise.
- **Layered traffic abstraction** — `traffic_list` returns compact summaries, `traffic_inspect` exposes `meta`/`preview`/`full` levels so the agent only loads what it needs.
- **Site map** — one call gives a host-grouped attack-surface map with endpoint params, status distribution, auth requirements, and finding counts.
- **Semantic parameter map** — `traffic_params` lists every mutable parameter (path/query/json/form/headers/cookies) tagged with categories like `identity_param`, `ssrf_candidate`, `sql_candidate`, `state_token`. The agent sees attack surface without reading the body.
- **Dual-identity testing (cold/hot fusion)** — multiple named browser contexts (default + victim + admin + …) inside one Browser process. `session_create_context`/`session_use_context` for live use; saved `<name>_state.json` profiles auto-hydrate on demand. `traffic_replay_via_browser(context="victim")` reuses victim cookies for IDOR/privilege-escalation testing.
- **Closed-loop replay** — every replay returns `new_flow_id` so the agent chains directly into `traffic_diff` and `evidence_bundle`. Browser-context replay reuses live cookies/tokens to avoid 401/403 noise.
- **Multi-step trace (tag + link)** — name flows with `traffic_tag`, declare data-flow with `traffic_link`, walk the DAG with `traffic_chain`. Built for stored SSRF, OAuth flows, two-stage IDOR.
- **Triage notes** — after researching a flow, the agent records a structured 4-section note (scenario / sensitive fields / test steps / conclusion) via `note_add`. Notes are embedded into evidence bundles automatically; the `triage_note` MCP prompt gives the agent the checklist on demand.
- **Evidence bundle** — `evidence_bundle(flow_id)` walks the link DAG and emits a Markdown report with method/url/status/profile/tags/findings/notes/curl-reproducer. Drop straight into a SRC report.
- **Profile persistence** — login state survives across sessions via per-context `storage_state` dump/restore.
- Navigate, click, fill, type, run JavaScript, inspect HTML/text, manage cookies, take screenshots, read console logs.
- List, search, inspect, replay, and fuzz captured traffic (fuzz now flags reflected payloads).
- Extract values with JSONPath or CSS selectors.
- Detect common auth signals such as session cookies, bearer tokens, JWTs, API keys, CSRF tokens, and basic auth.
- Reconstruct API endpoint patterns and generate OpenAPI output.
- Connect to an external Chrome/Chromium browser via CDP for manual login and captcha workflows.

## Repository Layout

```text
.
├── config/
│   └── mcp.json              # JSON-style MCP example
├── src/agent_proxy/
│   ├── main.py               # MCP server entrypoint
│   ├── models.py             # Pydantic models
│   ├── core/                 # Browser, MITM, session, and DB controllers
│   └── tools/                # MCP tool registration
├── pyproject.toml
└── setup.sh
```

## Requirements

Use a Linux machine with Python 3.10 or newer.

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
cd /path/to/AgentProxy
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
command = "/path/to/AgentProxy/.venv/bin/python"
args = ["-m", "agent_proxy.main"]
cwd = "/path/to/AgentProxy"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Restart Codex after editing `config.toml`. Use `/mcp` in Codex to confirm that `agent-proxy` is loaded.

The JSON equivalent, useful for other MCP clients, is:

```json
{
  "mcpServers": {
    "agent-proxy": {
      "command": "/path/to/AgentProxy/.venv/bin/python",
      "args": ["-m", "agent_proxy.main"],
      "cwd": "/path/to/AgentProxy"
    }
  }
}
```

### Loading a Custom Rule Pack From an MCP Client

You don't run `agent-proxy --config foo.yaml` by hand — the MCP client launches the server for you. There are three ways to point that launched process at your YAML:

**1. Pass `--config` through the MCP client's `args`** (most explicit)

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.agent-proxy]
command = "/path/to/AgentProxy/.venv/bin/python"
args    = ["-m", "agent_proxy.main", "--config", "/home/me/work/my_rules.yaml"]
cwd     = "/path/to/AgentProxy"
```

Claude Code / Cursor / generic JSON:

```json
{
  "mcpServers": {
    "agent-proxy": {
      "command": "/path/to/AgentProxy/.venv/bin/python",
      "args": ["-m", "agent_proxy.main", "--config", "/home/me/work/my_rules.yaml"],
      "cwd": "/path/to/AgentProxy"
    }
  }
}
```

**2. Pass `AGENT_PROXY_CONFIG` as an environment variable** (cleaner when juggling multiple clients)

Codex:

```toml
[mcp_servers.agent-proxy]
command = "/path/to/AgentProxy/.venv/bin/python"
args    = ["-m", "agent_proxy.main"]
cwd     = "/path/to/AgentProxy"
env     = { AGENT_PROXY_CONFIG = "/home/me/work/my_rules.yaml" }
```

JSON:

```json
{
  "mcpServers": {
    "agent-proxy": {
      "command": "/path/to/AgentProxy/.venv/bin/python",
      "args": ["-m", "agent_proxy.main"],
      "cwd": "/path/to/AgentProxy",
      "env": { "AGENT_PROXY_CONFIG": "/home/me/work/my_rules.yaml" }
    }
  }
}
```

**3. Drop a file named `agent_proxy.yaml` next to the project** (zero-config style)

If `<cwd>/agent_proxy.yaml` exists, the server picks it up automatically — no flag, no env var. Useful when you want different rule packs per project: `cd` into the target's working dir and the right pack loads. The `cwd` field in your MCP client config controls where the server looks.

**Priority** when multiple are present: explicit `--config` flag &gt; `AGENT_PROXY_CONFIG` env &gt; `<cwd>/agent_proxy.yaml` &gt; bundled defaults.

After restarting the MCP client, ask the agent to call `config_show(section="source_paths")` to verify which file actually loaded.


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

## Customising Rules with YAML

All semantic parameter dictionaries, passive-scan rules, and fuzz payloads live in a single YAML file. The bundled rule pack ships at `src/agent_proxy/config/defaults.yaml` — copy it, edit the sections you care about, then point your MCP client at the new file (see "Loading a Custom Rule Pack From an MCP Client" above for the three ways to do this).

```bash
cp src/agent_proxy/config/defaults.yaml ~/work/my_rules.yaml
# edit ~/work/my_rules.yaml
# then either:
#   - add `--config /home/me/work/my_rules.yaml` to your MCP client's args
#   - or set env AGENT_PROXY_CONFIG=/home/me/work/my_rules.yaml in the client config
#   - or save it as <cwd>/agent_proxy.yaml so it auto-loads
# restart the MCP client (Codex / Claude Code / Cursor) so the server reloads
```

You only need to write the sections that differ. Dictionaries deep-merge with the bundled defaults; lists at the leaf level replace wholesale.

Examples of common edits:

```yaml
# Add new semantic categories without touching the existing 11
semantic_params:
  internal_id_param:
    - lark_account_id
    - cas_employee_id

# Add new secret regexes (you must list the full body_rules array because
# lists replace wholesale — the easiest fix is to copy the whole list and
# append your additions)
passive_scan:
  body_rules:
    # ... copy bundled entries here ...
    - id: github_token
      severity: high
      category: secret_leak
      kind: finding
      regex: 'gh[pousr]_[A-Za-z0-9]{36,}'

# Add a brand-new fuzz category — traffic_fuzz(payload_category="ssti") will
# pick it up immediately, no code change needed
fuzz_payloads:
  ssti:
    - "{{7*7}}"
    - "${7*7}"
    - "<%= 7*7 %>"
```

Inspect the active rule pack at runtime through the `config_show` MCP tool:

```text
config_show()                          # full dump
config_show(section="source_paths")    # which yaml files actually loaded?
config_show(section="fuzz_payloads")
config_show(section="semantic_params")
```

Invalid regex entries are skipped with a warning so a single typo never breaks the rest of the pack.

## Recommended Triage Workflow

The agent-friendly path is to look at signals before bodies:

```text
session_start(proxy_port=8081, profile_dir="/tmp/agentproxy/target1")
browser_navigate(url="https://target.example.com")
# ... drive the browser through the app ...

traffic_findings_stats()                    # how dense is the attack surface?
site_map()                                  # host-grouped endpoint map
traffic_findings(severity="high")           # what should I look at first?
traffic_params(flow_id="<id>")              # which params are mutable + semantic tags
traffic_inspect(flow_id="<id>", level="meta")     # confirm context cheaply
traffic_inspect(flow_id="<id>", level="full")     # only when needed
traffic_replay_via_browser(flow_id="<id>")        # retry with live cookies (auto returns new_flow_id)
traffic_diff(flow_a="<id1>", flow_b="<id2>")      # IDOR / privilege check
note_add(flow_id="<id>", verdict="...", scenario="...", ...)   # ALWAYS record the verdict
session_stop()
```

`session_start(profile_dir=...)` saves storage state on stop and restores it next time so login state survives sessions.

## Dual-Identity (BOLA / IDOR / Privilege Escalation)

```text
# 1. Start with a profile dir so identities persist across runs
session_start(profile_dir="/tmp/agentproxy/acme")

# 2. Login as the VICTIM in a dedicated context
session_create_context(name="victim", from_profile=false)
session_use_context(name="victim")
browser_navigate(url="https://acme.example.com/login")
# (login as victim user — humans can take over here, or use browser_fill/click)
session_save_profile(name="victim")          # snapshot victim cookies/localStorage

# 3. Switch back to default and login as ATTACKER
session_use_context(name="default")
browser_navigate(url="https://acme.example.com/login")
# (login as attacker user)
session_save_profile(name="default")

# 4. Drive the attacker session, find a target flow
browser_navigate(url="https://acme.example.com/api/order/12345")
traffic_list(limit=20, with_findings=true)
# pick the flow id of the sensitive request, e.g. flow_a
traffic_params(flow_id=flow_a)               # confirm it has identity_param tags

# 5. Replay flow_a through the VICTIM context (the IDOR test)
result = traffic_replay_via_browser(flow_id=flow_a, context="victim")
# result includes new_flow_id

# 6. Compare — if responses match, IDOR confirmed
traffic_diff(flow_a, new_flow_id_from_result)
traffic_link(flow_a, new_flow_id, relation="identity_swap")
traffic_tag(flow_a, tag="bola_alice_order")

# 7. Multi-step chain & evidence
evidence_bundle(flow_id=flow_a, depth=2)     # Markdown report ready to drop into a SRC submission
session_stop()
```

`X-AgentProxy-Context` header is auto-injected per context and stripped before the request leaves the proxy, so the target server never sees it. Each captured flow is labeled with `profile_label` in SQLite.

## Triage Notes

After judging a flow, record the verdict — even when no vulnerability was found. "tested X / Y / Z, no anomaly" is the most useful note for the next session, and the report builder auto-pulls notes into `evidence_bundle`.

```text
# Researching a flow
traffic_inspect(flow_id="<id>", level="full")
traffic_params(flow_id="<id>")
traffic_replay_via_browser(flow_id="<id>", context="victim")
traffic_diff(flow_a, flow_b)

# Done — record what happened (verdict ∈ vulnerable | not_vulnerable | inconclusive)
note_add(
  flow_id="<id>",
  verdict="not_vulnerable",
  scenario="POST /api/order/cancel; orderId in JSON; auth via session cookie.",
  sensitive_fields="orderId (object_id_param), userId (cookie, identity_param)",
  test_steps="Replayed via victim ctx -> 403; mutated orderId=1 -> identical baseline; tried negative ints -> 400.",
  conclusion="Server enforces ownership check + numeric type. Did not test cross-tenant orderId; flag for follow-up if multi-tenant."
)

# Re-visiting later? Read your prior judgement first
note_get(flow_id="<id>")
note_get(verdict="inconclusive")        # what still needs followup
```

If the agent forgets the structure, calling the `triage_note` MCP prompt with the flow_id returns a 4-section template inline (auto-populated with the flow's method/url so the agent doesn't lose context).

`evidence_bundle(flow_id)` automatically embeds every related flow's note into the Markdown report — so by the end of a session, the bundle reads like a full SRC submission with no extra step.

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
cd /path/to/AgentProxy
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
session_start(proxy_port=8080, headless=true, profile_dir?, unsafe_disable_web_security?)
session_connect_cdp(endpoint_url="http://127.0.0.1:9222", proxy_port=8080)
session_save_profile(name?, path?)
session_create_context(name, from_profile=true)
session_use_context(name)
session_list_contexts()
session_status()
session_stop()
config_show(section?)
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
traffic_list(limit=20, with_findings=false)
traffic_inspect(flow_id, level="preview")    # meta | preview | full
traffic_search(query?, domain?, method?, limit)
traffic_clear()
traffic_extract(flow_id, json_path?, css_selector?)
traffic_replay(flow_id, method?, headers_json?, body?, timeout)
traffic_replay_via_browser(flow_id, method?, headers_json?, body?, timeout_ms, context="default")
traffic_diff(flow_a, flow_b, max_lines=50)
traffic_fuzz(flow_id, target_param, param_type, payload_category)
traffic_findings(severity?, category?, rule_id?, flow_id?, kind="finding", limit=50)   # kind in finding|signal|all
traffic_findings_stats()
traffic_params(flow_id)                      # parameter map with semantic tags
traffic_tag(flow_id, tag)                    # name a flow
traffic_untag(flow_id, tag)
traffic_find_by_tag(tag)
traffic_link(source_id, target_id, relation="")    # declare A → B
traffic_chain(flow_id, depth=2)              # walk DAG
note_add(flow_id, verdict, scenario, sensitive_fields, test_steps, conclusion)
note_get(flow_id?, verdict?, limit=50)       # verdict ∈ vulnerable|not_vulnerable|inconclusive
note_remove(flow_id)
evidence_bundle(flow_id, depth=3)            # Markdown report (auto-includes notes)
site_map(domain?)
traffic_auth_detect(flow_ids?)
traffic_api_patterns(domain?, limit?)
traffic_openapi(domain?, limit?)
traffic_generate_code(flow_ids, framework)
traffic_set_session_variable(name, value)
traffic_extract_session_variable(name, flow_id, regex_pattern, group_index=1)
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
command = "/absolute/path/to/AgentProxy/.venv/bin/python"
args = ["-m", "agent_proxy.main"]
cwd = "/absolute/path/to/AgentProxy"
```

Then restart Codex and run `/mcp`.

### `ModuleNotFoundError: No module named 'agent_proxy'`

Install the project into the virtual environment:

```bash
cd /path/to/AgentProxy
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
