import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..core.session_manager import SessionManager
from ..models import SessionConfig, InterceptionRule


def register_all_tools(mcp: FastMCP, session: SessionManager):
    @mcp.tool()
    async def session_start(proxy_port: int = 8080, headless: bool = True, profile_dir: str = None) -> str:
        """Start a complete AgentProxy session: MITM proxy + browser with proxy configured.
        All browser traffic will automatically go through the MITM proxy for capture.
        Args:
            proxy_port: Port for the MITM proxy (default: 8080)
            headless: Run browser in headless mode (default: True)
            profile_dir: Optional directory to persist browser storage state across sessions
                        (cookies, localStorage). When set, login state is restored on next start
                        and saved on stop. CDP mode does not use this.
        """
        return await session.start_session(proxy_port=proxy_port, headless=headless, profile_dir=profile_dir)

    @mcp.tool()
    async def session_connect_cdp(endpoint_url: str = "http://127.0.0.1:9222", proxy_port: int = 8080) -> str:
        """Start MITM proxy and connect to an already-running Chrome/Chromium via CDP.
        Launch the browser separately with flags such as:
          --remote-debugging-port=9222 --proxy-server=http://127.0.0.1:<proxy_port>
        Args:
            endpoint_url: Chrome DevTools Protocol endpoint URL (default: http://127.0.0.1:9222)
            proxy_port: Port for the MITM proxy that the external browser should use
        """
        return await session.connect_cdp_session(endpoint_url=endpoint_url, proxy_port=proxy_port)

    @mcp.tool()
    async def session_stop() -> str:
        """Stop the AgentProxy session: close browser and MITM proxy."""
        return await session.stop_session()

    @mcp.tool()
    async def session_status() -> str:
        """Get current session status including proxy, browser, and traffic info."""
        return json.dumps(session.get_status(), indent=2)

    @mcp.tool()
    async def session_save_profile(path: str = None) -> str:
        """Snapshot the current browser storage state (cookies + localStorage) to disk.
        Useful right after a manual login so the session can be restored next time.
        Args:
            path: Optional explicit path. Defaults to <profile_dir>/state.json from session_start.
        """
        return await session.browser.save_storage_state(path=path)

    # ==================== Browser Tools ====================

    @mcp.tool()
    async def browser_navigate(url: str, wait_until: str = "domcontentloaded") -> str:
        """Navigate browser to a URL. All traffic is automatically captured by the MITM proxy.
        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete ('domcontentloaded', 'load', 'networkidle')
        """
        return await session.browser.navigate(url, wait_until=wait_until)

    @mcp.tool()
    async def browser_click(selector: str) -> str:
        """Click an element on the page.
        Args:
            selector: CSS/XPath selector for the element to click
        """
        return await session.browser.click(selector)

    @mcp.tool()
    async def browser_fill(selector: str, value: str) -> str:
        """Fill a form field with a value.
        Args:
            selector: CSS selector for the input field
            value: Value to fill in
        """
        return await session.browser.fill(selector, value)

    @mcp.tool()
    async def browser_type(selector: str, value: str, delay: int = 50) -> str:
        """Type text into a field character by character (simulates real typing).
        Args:
            selector: CSS selector for the input field
            value: Text to type
            delay: Delay between keystrokes in ms (default: 50)
        """
        return await session.browser.type_text(selector, value, delay=delay)

    @mcp.tool()
    async def browser_select_option(selector: str, value: str) -> str:
        """Select an option in a dropdown.
        Args:
            selector: CSS selector for the select element
            value: Value of the option to select
        """
        return await session.browser.select_option(selector, value)

    @mcp.tool()
    async def browser_press_key(key: str) -> str:
        """Press a keyboard key (e.g., 'Enter', 'Tab', 'Escape').
        Args:
            key: Key to press
        """
        return await session.browser.press_key(key)

    @mcp.tool()
    async def browser_screenshot() -> str:
        """Take a screenshot of the current page. Returns base64-encoded image."""
        return await session.browser.screenshot()

    @mcp.tool()
    async def browser_get_text(selector: str = None) -> str:
        """Get text content from the page or a specific element.
        Args:
            selector: CSS selector (optional, defaults to entire page body)
        """
        return await session.browser.get_text(selector)

    @mcp.tool()
    async def browser_get_html(selector: str = None) -> str:
        """Get HTML content from the page or a specific element.
        Args:
            selector: CSS selector (optional, defaults to entire page)
        """
        return await session.browser.get_html(selector)

    @mcp.tool()
    async def browser_execute_js(script: str) -> str:
        """Execute JavaScript in the browser page context.
        Args:
            script: JavaScript code to execute
        """
        return await session.browser.execute_js(script)

    @mcp.tool()
    async def browser_wait_for(selector: str, timeout: int = 30000) -> str:
        """Wait for an element to appear on the page.
        Args:
            selector: CSS selector to wait for
            timeout: Maximum wait time in ms (default: 30000)
        """
        return await session.browser.wait_for_selector(selector, timeout=timeout)

    @mcp.tool()
    async def browser_go_back() -> str:
        """Navigate back in browser history."""
        return await session.browser.go_back()

    @mcp.tool()
    async def browser_go_forward() -> str:
        """Navigate forward in browser history."""
        return await session.browser.go_forward()

    @mcp.tool()
    async def browser_reload() -> str:
        """Reload the current page."""
        return await session.browser.reload()

    @mcp.tool()
    async def browser_get_cookies() -> str:
        """Get all cookies from the browser context."""
        return await session.browser.get_cookies()

    @mcp.tool()
    async def browser_set_cookies(cookies: str) -> str:
        """Set cookies in the browser context.
        Args:
            cookies: JSON array of cookie objects, e.g. [{"name":"token","value":"abc","domain":"example.com"}]
        """
        try:
            cookie_list = json.loads(cookies)
            return await session.browser.set_cookies(cookie_list)
        except json.JSONDecodeError:
            return "Invalid JSON for cookies"

    @mcp.tool()
    async def browser_set_headers(headers: str) -> str:
        """Set extra HTTP headers for all browser requests.
        Args:
            headers: JSON object of headers, e.g. {"Authorization":"Bearer token123"}
        """
        try:
            headers_dict = json.loads(headers)
            return await session.browser.set_extra_http_headers(headers_dict)
        except json.JSONDecodeError:
            return "Invalid JSON for headers"

    @mcp.tool()
    async def browser_set_offline(offline: bool = True) -> str:
        """Set browser to offline/online mode.
        Args:
            offline: True to go offline, False to go online
        """
        return await session.browser.set_offline(offline)

    @mcp.tool()
    async def browser_accessibility_tree() -> str:
        """Get the accessibility tree of the current page (useful for understanding page structure)."""
        return await session.browser.get_accessibility_tree()

    # ==================== MITM / Traffic Tools ====================

    @mcp.tool()
    async def traffic_list(limit: int = 20, with_findings: bool = False) -> str:
        """List captured HTTP/HTTPS traffic flows. Returns a compact summary by default.
        Each row is just id/method/url/status/size — call traffic_inspect for details.
        Args:
            limit: Maximum number of flows to return (default: 20)
            with_findings: When True, attach a per-flow finding count
        """
        flows = session.mitm.db.get_summary(limit=limit, with_findings=with_findings)
        return json.dumps(flows, indent=2)

    @mcp.tool()
    async def traffic_inspect(flow_id: str, level: str = "preview", full_body: bool = False) -> str:
        """Inspect a captured flow at one of three detail levels.
        Args:
            flow_id: The ID of the flow to inspect
            level: One of 'meta' (headers only), 'preview' (default, body truncated to 2KB),
                   or 'full' (entire body up to 256KB cap)
            full_body: Legacy alias — when True, equivalent to level='full'
        """
        if full_body:
            level = "full"
        if level not in ("meta", "preview", "full"):
            return f"Invalid level '{level}'. Use 'meta', 'preview', or 'full'."
        body_len = 2000 if level == "preview" else (256 * 1024 if level == "full" else 0)
        data = session.mitm.db.get_detail(flow_id, level=level, body_preview_length=body_len)
        if not data:
            return "Flow not found"
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def traffic_search(query: str = None, domain: str = None, method: str = None, limit: int = 50) -> str:
        """Search captured traffic with filters.
        Args:
            query: Keywords to search in URL or body
            domain: Filter by domain name
            method: Filter by HTTP method (GET, POST, etc.)
            limit: Max results (default: 50)
        """
        results = session.mitm.db.search(query=query, domain=domain, method=method, limit=limit)
        return json.dumps(results, indent=2)

    @mcp.tool()
    async def traffic_clear() -> str:
        """Clear all captured traffic from the database."""
        session.mitm.db.clear()
        return "Cleared all traffic history"

    @mcp.tool()
    async def traffic_extract(flow_id: str, json_path: str = None, css_selector: str = None) -> str:
        """Extract specific data from a flow's response body using JSONPath or CSS selectors.
        Args:
            flow_id: The ID of the flow
            json_path: JSONPath expression to extract from JSON response
            css_selector: CSS selector to extract from HTML/XML response
        """
        return session.mitm.extract_from_flow(flow_id, json_path=json_path, css_selector=css_selector)

    @mcp.tool()
    async def traffic_replay(
        flow_id: str,
        method: str = None,
        headers_json: str = None,
        body: str = None,
        timeout: float = 30.0,
    ) -> str:
        """Replay a captured flow with optional modifications. Uses curl_cffi for stealth (browser fingerprint impersonation).
        Args:
            flow_id: The ID of the flow to replay
            method: Override HTTP method (optional)
            headers_json: JSON object of headers to override/add (optional)
            body: Override request body (optional)
            timeout: Request timeout in seconds (default: 30)
        """
        parsed_headers = None
        if headers_json:
            try:
                parsed_headers = json.loads(headers_json)
            except json.JSONDecodeError:
                return "headers_json must be valid JSON"

        resolved_body = body
        if resolved_body == "__omit__":
            resolved_body = None

        if session.mitm.session_variables:
            if resolved_body:
                for k, v in session.mitm.session_variables.items():
                    resolved_body = resolved_body.replace(f"${k}", str(v))
            if parsed_headers:
                for hk, hv in parsed_headers.items():
                    if isinstance(hv, str):
                        for k, v in session.mitm.session_variables.items():
                            hv = hv.replace(f"${k}", str(v))
                        parsed_headers[hk] = hv

        return await session.mitm.replay_request(
            flow_id=flow_id,
            method=method,
            headers=parsed_headers,
            body=resolved_body,
            timeout=timeout,
        )

    @mcp.tool()
    async def traffic_fuzz(
        flow_id: str,
        target_param: str,
        param_type: str = "query",
        payload_category: str = "sqli",
        timeout: float = 10.0,
    ) -> str:
        """Fuzz an endpoint by substituting a parameter with security payloads. Detects anomalies like 5xx errors, status code deviations, and content length changes.
        Args:
            flow_id: The flow to use as base request
            target_param: Name of the parameter to fuzz
            param_type: Parameter location: 'query' or 'json_body'
            payload_category: Category of payloads: 'sqli', 'xss', 'path_traversal', 'ssrf', 'command_injection'
            timeout: Request timeout in seconds (default: 10)
        """
        return await session.mitm.fuzz_endpoint(
            flow_id=flow_id,
            target_param=target_param,
            param_type=param_type,
            payload_category=payload_category,
            timeout=timeout,
        )

    @mcp.tool()
    async def traffic_auth_detect(flow_ids: str = None) -> str:
        """Detect authentication patterns in captured traffic (Bearer, JWT, API keys, OAuth2, CSRF, session cookies, Basic auth).
        Args:
            flow_ids: Comma-separated flow IDs to analyze (optional, analyzes all if omitted)
        """
        ids = None
        if flow_ids:
            ids = [fid.strip() for fid in flow_ids.split(",") if fid.strip()]
        result = session.mitm.detect_auth_patterns(flow_ids=ids)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def traffic_api_patterns(domain: str = None, limit: int = None) -> str:
        """Cluster captured traffic into API endpoint patterns. Useful for API discovery and documentation.
        Args:
            domain: Filter by domain (optional)
            limit: Max flows to analyze (optional)
        """
        return session.mitm.get_api_patterns(domain=domain, limit=limit)

    @mcp.tool()
    async def traffic_openapi(domain: str = None, limit: int = None) -> str:
        """Generate OpenAPI v3 specification from captured API traffic.
        Args:
            domain: Filter by domain (optional)
            limit: Max flows to analyze (optional)
        """
        return session.mitm.export_openapi_spec(domain=domain, limit=limit)

    @mcp.tool()
    async def site_map(domain: str = None) -> str:
        """Build a site map: hosts → endpoints → (method, path, params, status_dist,
        auth_required, finding count, sample_flow_id). One call gives the agent the
        target's attack surface in a flat, scannable structure.
        Args:
            domain: Optional substring filter on URL
        """
        return session.mitm.site_map(domain=domain)

    @mcp.tool()
    async def traffic_findings(severity: str = None, category: str = None,
                                rule_id: str = None, flow_id: str = None,
                                limit: int = 50) -> str:
        """List passive-scan findings (signals worth investigating). One row per finding:
        rule_id / severity / category / flow_id / short evidence.
        Use this BEFORE traffic_list when triaging — it surfaces the high-value flows.
        Args:
            severity: Filter by 'info' | 'low' | 'medium' | 'high'
            category: Filter by category, e.g. 'secret_leak', 'sqli_signal', 'cors_misconfig'
            rule_id: Filter by a specific rule
            flow_id: Show findings for one flow only
            limit: Max rows (default 50)
        """
        rows = session.mitm.db.list_findings(severity=severity, category=category,
                                              rule_id=rule_id, flow_id=flow_id, limit=limit)
        return json.dumps(rows, indent=2)

    @mcp.tool()
    async def traffic_findings_stats() -> str:
        """Aggregate finding counts by severity and category — quick attack-surface overview."""
        return json.dumps(session.mitm.db.findings_stats(), indent=2)

    @mcp.tool()
    async def traffic_replay_via_browser(
        flow_id: str,
        method: str = None,
        headers_json: str = None,
        body: str = None,
        timeout_ms: int = 30000,
    ) -> str:
        """Replay a captured request through the live browser context — automatically reuses
        the current session's cookies, refreshed tokens, and CSRF state. The fix for
        'replay always 401' problems. Falls back to curl_cffi if the browser is not running.
        Args:
            flow_id: Flow to replay
            method: Override HTTP method
            headers_json: JSON object of headers to override/add
            body: Override request body
            timeout_ms: Request timeout in milliseconds (default 30000)
        """
        parsed_headers = None
        if headers_json:
            try:
                parsed_headers = json.loads(headers_json)
            except json.JSONDecodeError:
                return "headers_json must be valid JSON"
        if session.mitm.session_variables and parsed_headers:
            for hk, hv in list(parsed_headers.items()):
                if isinstance(hv, str):
                    for k, v in session.mitm.session_variables.items():
                        hv = hv.replace(f"${k}", str(v))
                    parsed_headers[hk] = hv
        resolved_body = body
        if resolved_body and session.mitm.session_variables:
            for k, v in session.mitm.session_variables.items():
                resolved_body = resolved_body.replace(f"${k}", str(v))
        return await session.replay_via_browser(
            flow_id=flow_id, method=method,
            headers_override=parsed_headers, body=resolved_body,
            timeout_ms=timeout_ms,
        )

    @mcp.tool()
    async def traffic_diff(flow_a: str, flow_b: str, max_lines: int = 50) -> str:
        """Compare two captured flows. Outputs status/size deltas plus a JSON field-level diff
        (added/removed/changed paths) for JSON responses, or a unified text diff otherwise.
        Use for IDOR / privilege-escalation / parameter-pollution verification.
        Args:
            flow_a: First flow id (baseline)
            flow_b: Second flow id (comparison)
            max_lines: Cap for unified text diff lines (default 50)
        """
        return session.mitm.diff_flows(flow_a, flow_b, max_lines=max_lines)

    @mcp.tool()
    async def traffic_generate_code(flow_ids: str, framework: str = "curl_cffi") -> str:
        """Generate executable scraper/automation code from captured flows.
        Args:
            flow_ids: Comma-separated list of flow IDs
            framework: Target framework: 'curl_cffi' or 'playwright'
        """
        ids = [fid.strip() for fid in flow_ids.split(",") if fid.strip()]
        return session.mitm.generate_scraper_code(flow_ids=ids, target_framework=framework)

    @mcp.tool()
    async def traffic_set_session_variable(name: str, value: str) -> str:
        """Set a session variable for use in replay (referenced as $name in headers/body).
        Args:
            name: Variable name
            value: Variable value
        """
        session.mitm.session_variables[name] = value
        return f"Set session variable ${name} = {value}"

    @mcp.tool()
    async def traffic_extract_session_variable(
        name: str, flow_id: str, regex_pattern: str, group_index: int = 1
    ) -> str:
        """Extract a value from a flow's response using regex and store as session variable.
        Args:
            name: Variable name (referenced as $name in replay)
            flow_id: Flow to extract from
            regex_pattern: Regex pattern with capture groups
            group_index: Which capture group to extract (default: 1)
        """
        import re
        flow_data = session.mitm.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
        if not flow_data:
            return "Flow not found"
        response = flow_data.get("response")
        body_content = response.get("body") if response else None
        if not body_content:
            return "Flow has no response body"
        try:
            match = re.search(regex_pattern, body_content)
            if match:
                value = match.group(group_index)
                session.mitm.session_variables[name] = value
                return f"Extracted and set ${name} = {value}"
            else:
                return "Pattern not found in response body"
        except Exception as e:
            return f"Regex error: {str(e)}"

    # ==================== Interception Tools ====================

    @mcp.tool()
    async def intercept_add_rule(
        rule_id: str,
        action_type: str,
        url_pattern: str = ".*",
        method: str = None,
        key: str = None,
        value: str = None,
        search_pattern: str = None,
        phase: str = "request",
    ) -> str:
        """Add a traffic interception rule to modify requests/responses on the fly.
        Args:
            rule_id: Unique identifier for this rule
            action_type: Action type: 'inject_header', 'replace_body', or 'block'
            url_pattern: Regex pattern to match URLs (default: '.*' matches all)
            method: HTTP method to match (optional)
            key: Header key (for inject_header action)
            value: Header value or replacement value
            search_pattern: Regex pattern to search in body (for replace_body action)
            phase: When to apply: 'request' or 'response' (default: 'request')
        """
        if phase not in ["request", "response"]:
            return "Phase must be 'request' or 'response'"

        rule = InterceptionRule(
            id=rule_id,
            url_pattern=url_pattern,
            method=method,
            phase=phase,
            action_type=action_type,
            key=key,
            value=value,
            search_pattern=search_pattern,
        )

        if not session.mitm.interceptor.add_rule(rule):
            return f"Invalid regex for rule '{rule_id}'"
        return f"Added interception rule '{rule_id}'"

    @mcp.tool()
    async def intercept_list_rules() -> str:
        """List all active traffic interception rules."""
        rules_dict = {
            rid: {
                "action": r.action_type,
                "url_pattern": r.url_pattern,
                "phase": r.phase,
                "method": r.method,
            }
            for rid, r in session.mitm.interceptor.rules.items()
        }
        return json.dumps(rules_dict, indent=2)

    @mcp.tool()
    async def intercept_remove_rule(rule_id: str = None) -> str:
        """Remove an interception rule by ID, or all rules if no ID specified.
        Args:
            rule_id: Rule ID to remove (optional, removes all if omitted)
        """
        if rule_id:
            session.mitm.interceptor.remove_rule(rule_id)
            return f"Removed rule: {rule_id}"
        else:
            session.mitm.interceptor.clear_rules()
            return "Cleared all interception rules"

    @mcp.tool()
    async def intercept_set_global_header(key: str, value: str) -> str:
        """Set a global header that will be injected into all matching requests.
        Args:
            key: Header name
            value: Header value
        """
        rule_id = f"global_{key.lower()}"
        rule = InterceptionRule(
            id=rule_id,
            url_pattern=".*",
            phase="request",
            action_type="inject_header",
            key=key,
            value=value,
        )
        session.mitm.interceptor.add_rule(rule)
        return f"Set global header: {key} = {value}"

    @mcp.tool()
    async def intercept_remove_global_header(key: str) -> str:
        """Remove a global header injection rule.
        Args:
            key: Header name to remove
        """
        rule_id = f"global_{key.lower()}"
        session.mitm.interceptor.remove_rule(rule_id)
        return f"Removed global header: {key}"

    # ==================== Scope Tools ====================

    @mcp.tool()
    async def scope_set(allowed_domains: str) -> str:
        """Set the traffic scope - only capture traffic matching these domains.
        Args:
            allowed_domains: Comma-separated list of domains to capture (e.g., 'api.example.com,cdn.example.com')
        """
        domains = [d.strip() for d in allowed_domains.split(",") if d.strip()]
        session.mitm.scope_manager.update_domains(domains)
        return f"Scope updated. Now tracking: {', '.join(domains) if domains else 'everything'}"

    @mcp.tool()
    async def scope_clear() -> str:
        """Clear scope restrictions - capture all traffic."""
        session.mitm.scope_manager.update_domains([])
        return "Scope cleared. Now tracking all domains."

    # ==================== High-Level Workflow Tools ====================

    @mcp.tool()
    async def browse_and_capture(url: str, wait_until: str = "domcontentloaded", actions: str = None) -> str:
        """Navigate to a URL and capture all resulting traffic. High-level workflow combining browser navigation + traffic capture.
        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete ('domcontentloaded', 'load', 'networkidle')
            actions: JSON array of actions to perform after navigation, e.g. [{"type":"fill","selector":"#search","value":"test"},{"type":"click","selector":"#submit"}]
        """
        parsed_actions = None
        if actions:
            try:
                parsed_actions = json.loads(actions)
            except json.JSONDecodeError:
                return "Invalid JSON for actions"
        return await session.browse_and_capture(url, wait_until=wait_until, actions=parsed_actions)

    @mcp.tool()
    async def api_discover(domain: str = None) -> str:
        """Discover all API endpoints from captured traffic. Clusters requests into endpoint patterns.
        Args:
            domain: Filter by domain (optional)
        """
        return await session.api_discover(domain=domain)

    @mcp.tool()
    async def security_scan(flow_id: str, target_param: str, param_type: str = "query", payload_categories: List[str] = None) -> str:
        """Run a comprehensive security scan on a captured request. Tests multiple vulnerability categories.
        Args:
            flow_id: The flow to use as base request
            target_param: Parameter name to test
            param_type: Parameter location: 'query' or 'json_body'
            payload_categories: List of categories. Defaults to ['sqli','xss','path_traversal'].
                Available: sqli, xss, path_traversal, ssrf, command_injection
        """
        categories = payload_categories or ["sqli", "xss", "path_traversal"]
        return await session.security_scan(
            flow_id=flow_id,
            target_param=target_param,
            param_type=param_type,
            payload_categories=categories,
        )

    @mcp.tool()
    async def export_session(format: str = "openapi", domain: str = None) -> str:
        """Export session data in various formats.
        Args:
            format: Export format: 'openapi' (OpenAPI spec), 'patterns' (API patterns), 'traffic' (all traffic JSON)
            domain: Filter by domain (optional)
        """
        if format == "openapi":
            return session.mitm.export_openapi_spec(domain=domain)
        elif format == "patterns":
            return session.mitm.get_api_patterns(domain=domain)
        elif format == "traffic":
            flows = session.mitm.db.get_all_for_analysis()
            return json.dumps(flows, indent=2)
        else:
            return f"Unknown format: {format}. Use 'openapi', 'patterns', or 'traffic'"
