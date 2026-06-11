import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..core.cert_installer import (
    DEFAULT_CA_PATH,
    DEFAULT_NICKNAME,
    cert_status as cert_status_impl,
    install_chrome as cert_install_chrome_impl,
    install_firefox as cert_install_firefox_impl,
)
from ..core.session_manager import SessionManager
from ..models import InterceptionRule


def register_all_tools(mcp: FastMCP, session: SessionManager):
    def _subst_vars(body, headers):
        """Substitute $name session variables into a request body and header values."""
        sv = session.mitm.session_variables
        if not sv:
            return body, headers
        if body:
            for k, v in sv.items():
                body = body.replace(f"${k}", str(v))
        if headers:
            for hk, hv in list(headers.items()):
                if isinstance(hv, str):
                    for k, v in sv.items():
                        hv = hv.replace(f"${k}", str(v))
                    headers[hk] = hv
        return body, headers

    @mcp.tool()
    async def session_start(proxy_port: int = 8080, headless: bool = True, profile_dir: str = None, unsafe_disable_web_security: bool = False) -> str:
        """Start a complete AgentProxy session: MITM proxy + browser with proxy configured.
        All browser traffic will automatically go through the MITM proxy for capture.
        Args:
            proxy_port: Port for the MITM proxy (default: 8080)
            headless: Run browser in headless mode (default: True)
            profile_dir: Optional directory to persist per-context storage state across sessions.
                Each named context dumps to <profile_dir>/<name>_state.json.
            unsafe_disable_web_security: When True, launches Chromium with --disable-web-security.
                This breaks SOP/CORS enforcement, so leave it OFF for real CORS-related testing.
        """
        return await session.start_session(
            proxy_port=proxy_port, headless=headless,
            profile_dir=profile_dir,
            unsafe_disable_web_security=unsafe_disable_web_security,
        )

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
    async def session_start_proxy_only(proxy_port: int = 8080) -> str:
        """Start only the MITM proxy — no Playwright browser, no CDP attach.

        Use this for browser-less / passive capture: any external client
        (system Chrome, Firefox, mobile device, curl, script) that you
        point at http://127.0.0.1:<proxy_port> will have its traffic
        captured into SQLite. Agent-side traffic_*/site_map/findings keep
        working as usual.

        Caveats:
          - browser_* tools, browse_and_capture, and
            traffic_replay_via_browser require a live page and will return
            an error in this mode. Use traffic_replay for curl_cffi-based
            replay instead.
          - For HTTPS, the external client must trust mitmproxy's CA at
            ~/.mitmproxy/mitmproxy-ca-cert.pem. See README's HTTPS
            troubleshooting section for the per-browser steps.

        Args:
            proxy_port: Port for the MITM proxy (default: 8080)
        """
        return await session.start_mitm_only(proxy_port=proxy_port)

    @mcp.tool()
    async def session_attach_browser(
        headless: bool = True,
        profile_dir: str = None,
        unsafe_disable_web_security: bool = False,
        hydrate_host: str = None,
    ) -> str:
        """Hot-attach a Playwright browser to an existing mitm-only session.

        Reuses the running mitm proxy at its current port — no restart,
        no traffic loss. Required state: a session is active and only
        the proxy is running (typical after session_start_proxy_only).

        Use it to upgrade passive capture to active driving while keeping
        every flow you collected. If `hydrate_host` is set, the default
        context is automatically seeded with cookies / auth headers from
        the DB for that host (equivalent to browser_hydrate_from_traffic
        run right after).

        Args:
            headless: Run browser in headless mode (default True).
            profile_dir: Optional storage_state directory.
            unsafe_disable_web_security: Disable SOP/CORS (default False).
            hydrate_host: Optional hostname — auto-hydrate after start.
        """
        return await session.attach_browser(
            headless=headless,
            profile_dir=profile_dir,
            unsafe_disable_web_security=unsafe_disable_web_security,
            hydrate_host=hydrate_host,
        )

    @mcp.tool()
    async def session_stop() -> str:
        """Stop the AgentProxy session: close browser and MITM proxy."""
        return await session.stop_session()

    @mcp.tool()
    async def cert_status(ca_path: str = DEFAULT_CA_PATH, nickname: str = DEFAULT_NICKNAME) -> str:
        """Report whether the mitmproxy CA is installed in each Firefox
        profile and the Chrome NSS DB on this machine. Read-only — call it
        to diagnose 'Not Secure' / MOZILLA_PKIX_ERROR_MITM_DETECTED before
        running cert_install_firefox / cert_install_chrome.

        Args:
            ca_path: Path to mitmproxy's CA pem (defaults to
                ~/.mitmproxy/mitmproxy-ca-cert.pem).
            nickname: NSS nickname to look up (defaults to 'mitmproxy').
        """
        return json.dumps(cert_status_impl(ca_path=ca_path, nickname=nickname), indent=2)

    @mcp.tool()
    async def cert_install(browser: str = "both", ca_path: str = DEFAULT_CA_PATH, nickname: str = DEFAULT_NICKNAME) -> str:
        """Install the mitmproxy CA into Firefox profiles and/or the Chrome
        NSS DB so external browsers trust captured HTTPS. Fixes
        MOZILLA_PKIX_ERROR_MITM_DETECTED (Firefox) and the 'Not Secure' lock
        (Chrome). Not needed for AgentProxy's built-in Playwright Chromium.

        Requires `certutil` (Debian/Kali/Ubuntu: `sudo apt-get install -y
        libnss3-tools`). Restart the browser afterwards.

        Args:
            browser: 'firefox', 'chrome', or 'both' (default).
            ca_path: Path to the mitmproxy CA pem file.
            nickname: NSS nickname to register the CA under.
        """
        if browser not in ("firefox", "chrome", "both"):
            return json.dumps({"error": "browser must be 'firefox', 'chrome', or 'both'"})
        out = {}
        if browser in ("firefox", "both"):
            out["firefox"] = cert_install_firefox_impl(ca_path=ca_path, nickname=nickname)
        if browser in ("chrome", "both"):
            out["chrome"] = cert_install_chrome_impl(ca_path=ca_path, nickname=nickname)
        return json.dumps(out, indent=2)

    @mcp.tool()
    async def session_status() -> str:
        """Get current session status including proxy, browser, and traffic info."""
        return json.dumps(session.get_status(), indent=2)

    @mcp.tool()
    async def session_save_profile(name: str = None, path: str = None) -> str:
        """Snapshot the current browser storage state (cookies + localStorage) to disk.
        Useful right after a manual login so the session can be restored next time.
        Args:
            name: Context name to save (defaults to the active context). Saved to
                <profile_dir>/<name>_state.json.
            path: Optional explicit path overriding profile_dir resolution.
        """
        return await session.browser.save_storage_state(name=name, path=path)

    @mcp.tool()
    async def session_create_context(name: str, from_profile: bool = True) -> str:
        """Create an isolated browser context (separate cookies/localStorage) within
        the same browser process. The context is auto-tagged with X-AgentProxy-Context
        so captured traffic carries `profile_label=<name>`.
        Use it for dual-identity testing (e.g. attacker vs victim, low-priv vs admin).
        Args:
            name: Context name (e.g. 'victim', 'admin')
            from_profile: When True (default) and a saved <name>_state.json exists,
                restore that login state. Set False to start fresh.
        """
        return await session.browser.create_context(name, from_profile=from_profile)

    @mcp.tool()
    async def session_use_context(name: str) -> str:
        """Switch the active browser context. All subsequent browser_* calls
        operate on this context (its page / cookies / localStorage).
        Args:
            name: One of the names returned by session_list_contexts.
        """
        return session.browser.use_context(name)

    @mcp.tool()
    async def session_list_contexts() -> str:
        """List all browser contexts currently live in the session, plus the active one."""
        return json.dumps({
            "contexts": session.browser.list_contexts(),
            "active": session.browser.active,
        }, indent=2)

    @mcp.tool()
    async def config_show(section: str = None) -> str:
        """Inspect the active rule pack — semantic_params dictionaries, passive
        scan rules, fuzz payload categories, etc.

        Useful when adapting AgentProxy to a new target / language / framework:
        you can verify what tags an agent will currently see before editing
        the YAML.

        Args:
            section: Optional top-level section name to limit the response, e.g.
                'semantic_params', 'passive_scan', 'fuzz_payloads',
                'fuzz_categories', 'interesting_headers', 'source_paths'.
                Pass None to dump everything.
        """
        from ..config import to_inspectable_dict
        full = to_inspectable_dict(session.rules)
        if section:
            if section not in full:
                return json.dumps({
                    "error": f"unknown section '{section}'",
                    "available": sorted(full.keys()),
                }, indent=2)
            return json.dumps({section: full[section]}, indent=2)
        return json.dumps(full, indent=2)

    @mcp.tool()
    async def config_add(
        kind: str,
        category: str = None,
        rule_id: str = None,
        regex: str = None,
        severity: str = "medium",
        confidence: str = "finding",
        flags: str = "i",
        rescan: bool = True,
        payloads: List[str] = None,
        words: List[str] = None,
    ) -> str:
        """Adapt the LIVE rule pack in-band (in-memory only; not persisted to YAML).

        Three kinds, selected by `kind`:
          - kind='passive_rule': add a body-scan regex. Requires rule_id + regex.
            Optional: severity (info|low|medium|high), category, flags (i/m/s/x),
            confidence ('finding' high-confidence | 'signal' low-confidence),
            rescan (also scan already-captured flows now).
          - kind='fuzz': append target-specific payloads to a fuzz category.
            Requires category + payloads. Available immediately to traffic_fuzz.
          - kind='semantic': add param-name keywords to a semantic category so
            traffic_params tags them. Requires category + words.

        Examples:
          config_add(kind='passive_rule', rule_id='corp_token',
                     regex='AKLT[0-9A-Za-z]{16}', severity='high', category='secret_leak')
          config_add(kind='fuzz', category='ssti', payloads=['{{7*7}}','${7*7}'])
          config_add(kind='semantic', category='identity_param', words=['larkAccountId'])
        """
        if kind == "passive_rule":
            if not rule_id or not regex:
                return json.dumps({"status": "error", "error": "passive_rule needs rule_id and regex"})
            import re as _re
            from ..core.passive_scan import scan_existing_flows, PassiveScanner
            try:
                rule = session.rules.add_body_rule(
                    rule_id=rule_id, regex=regex, severity=severity,
                    category=category or "custom", kind=confidence, flags=flags,
                )
            except _re.error as e:
                return json.dumps({"status": "error", "error": f"invalid regex: {e}"})
            new_hits = 0
            if rescan:
                new_hits = scan_existing_flows(session.mitm.db, PassiveScanner(rules=session.rules))
            return json.dumps({
                "status": "ok", "kind": "passive_rule",
                "added": {"id": rule.id, "severity": rule.severity, "confidence": rule.kind,
                          "category": rule.category, "regex": rule.pattern.pattern},
                "total_body_rules": len(session.rules.body_rules),
                "rescan_findings_written": new_hits,
                "note": "in-memory only; not persisted to YAML",
            }, indent=2)
        elif kind == "fuzz":
            if not category or not payloads:
                return json.dumps({"status": "error", "error": "fuzz needs category and payloads"})
            merged = session.rules.add_fuzz_payloads(category, payloads)
            return json.dumps({
                "status": "ok", "kind": "fuzz", "category": category,
                "payloads_in_category": merged,
                "all_categories": sorted(session.rules.fuzz_payloads.keys()),
                "note": "in-memory only; not persisted to YAML",
            }, indent=2)
        elif kind == "semantic":
            if not category or not words:
                return json.dumps({"status": "error", "error": "semantic needs category and words"})
            bucket = session.rules.add_semantic_params(category, words)
            return json.dumps({
                "status": "ok", "kind": "semantic", "category": category,
                "words_in_category": sorted(bucket),
                "all_categories": sorted(session.rules.semantic_params.keys()),
                "note": "in-memory only; not persisted to YAML",
            }, indent=2)
        return json.dumps({"status": "error",
                           "error": f"unknown kind '{kind}'; use passive_rule | fuzz | semantic"})

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
    async def browser_get_text(selector: str = None, max_chars: int = 40000) -> str:
        """Get text content from the page or a specific element.

        Output is capped at `max_chars` (default 40000) and marked when
        truncated — a full-page body on a large SPA can otherwise flood the
        agent's context. Pass a CSS `selector` to read only the relevant
        element, or raise `max_chars` if you really need more.
        Args:
            selector: CSS selector (optional, defaults to entire page body)
            max_chars: Max characters returned before truncation (default 40000)
        """
        return await session.browser.get_text(selector, max_chars=max_chars)

    @mcp.tool()
    async def browser_get_html(selector: str = None, max_chars: int = 40000) -> str:
        """Get HTML content from the page or a specific element.

        Output is capped at `max_chars` (default 40000) and marked when
        truncated. Prefer a CSS `selector` over reading the whole document —
        full page HTML is usually huge and token-expensive.
        Args:
            selector: CSS selector (optional, defaults to entire page)
            max_chars: Max characters returned before truncation (default 40000)
        """
        return await session.browser.get_html(selector, max_chars=max_chars)

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

    @mcp.tool()
    async def browser_hydrate_from_traffic(host: str, context: str = "default", limit: int = 200) -> str:
        """Seed the internal browser context with cookies and auth headers
        already captured in the traffic DB for `host`.

        Typical flow: an external browser (system Chrome / Firefox) is
        logged in to the target, mitm captured its traffic, and now you
        want the internal Playwright context to act under that identity
        without redoing the login. Run this once after starting / attaching
        the browser.

        Cookies are sourced first from request `Cookie:` headers (most
        accurate snapshot of what the server is currently honouring), then
        from `Set-Cookie` responses. Auth headers come from a fixed
        whitelist (Authorization, X-CSRF-Token, X-XSRF-Token,
        X-Auth-Token, X-Api-Token, X-Api-Key, X-Session-Token). Hostname
        scoping is exact-or-subdomain.

        Args:
            host: Target hostname (e.g. 'app.example.com').
            context: Browser context name (defaults to 'default').
            limit: Max recent flows to scan (default 200).
        """
        return await session.hydrate_browser_from_traffic(host=host, context=context, limit=limit)

    @mcp.tool()
    async def browser_get_console_logs(clear: bool = False) -> str:
        """Return JS console logs collected since session start.
        Useful for XSS debugging, OAuth/CSRF flow failures, frontend auth issues,
        and detecting CSP violations during pen testing.
        Args:
            clear: If True, clears the buffer after reading (default False)
        """
        return await session.browser.get_console_logs(clear=clear)

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
    async def traffic_extract(flow_id: str, json_path: str = None,
                              css_selector: str = None, regex: str = None,
                              group_index: int = 1, save_as: str = None) -> str:
        """Extract data from a flow's response via JSONPath, CSS selector, or regex.
        Optionally store the result as a $session variable for replay substitution.

        Args:
            flow_id: The ID of the flow
            json_path: JSONPath expression to extract from a JSON response
            css_selector: CSS selector to extract from an HTML/XML response
            regex: Regex with capture group(s) to extract from the raw response body
            group_index: Which regex capture group to return (default 1)
            save_as: If set, store the extracted value as session variable $<save_as>
                (referenced as $<save_as> in traffic_replay headers/body)
        """
        if regex is not None:
            import re as _re
            flow_data = session.mitm.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
            if not flow_data:
                return "Flow not found"
            response = flow_data.get("response")
            body_content = response.get("body") if response else None
            if not body_content:
                return "Flow has no response body"
            try:
                match = _re.search(regex, body_content)
            except _re.error as e:
                return f"Regex error: {e}"
            if not match:
                return "Pattern not found in response body"
            value = match.group(group_index)
            if save_as:
                session.mitm.session_variables[save_as] = value
                return f"Extracted and set ${save_as} = {value}"
            return value
        result = session.mitm.extract_from_flow(flow_id, json_path=json_path, css_selector=css_selector)
        if save_as and result:
            session.mitm.session_variables[save_as] = result
        return result

    @mcp.tool()
    async def traffic_replay(
        flow_id: str,
        method: str = None,
        headers_json: str = None,
        body: str = None,
        timeout: float = 30.0,
        context: str = None,
    ) -> str:
        """Replay a captured flow with optional modifications. Returns JSON with
        `new_flow_id` so you can feed it straight into traffic_diff.

        Two transports, selected by `context`:
          - context=None (default): replay via curl_cffi with browser TLS
            fingerprint impersonation (stealth). The default identity.
          - context="victim" | "admin" | any name from session_create_context:
            replay through that browser context, reusing its cookies / refreshed
            tokens / CSRF state. Use this for dual-identity / IDOR testing.
            Cold/hot resolution: live context → cold-hydrate from saved profile →
            curl_cffi+cookies fallback → plain default replay.

        $name session variables (see traffic_set_session_variable) are
        substituted into `body` and header values before sending.

        Args:
            flow_id: The ID of the flow to replay
            method: Override HTTP method (optional)
            headers_json: JSON object of headers to override/add (optional)
            body: Override request body (optional; "__omit__" forces an empty body)
            timeout: Request timeout in seconds (default: 30)
            context: Browser context name, or None for curl_cffi (default)
        """
        parsed_headers = None
        if headers_json:
            try:
                parsed_headers = json.loads(headers_json)
            except json.JSONDecodeError:
                return "headers_json must be valid JSON"

        resolved_body = None if body == "__omit__" else body
        resolved_body, parsed_headers = _subst_vars(resolved_body, parsed_headers)

        if context is not None:
            return await session.replay_via_browser(
                flow_id=flow_id, method=method,
                headers_override=parsed_headers, body=resolved_body,
                timeout_ms=int(timeout * 1000), context=context,
            )
        return await session.mitm.replay_request(
            flow_id=flow_id, method=method,
            headers=parsed_headers, body=resolved_body, timeout=timeout,
        )

    @mcp.tool()
    async def traffic_fuzz(
        flow_id: str,
        target_param: str,
        param_type: str = "query",
        payload_category: str = "sqli",
        timeout: float = 10.0,
    ) -> str:
        """Fuzz an endpoint by substituting one parameter with one or more
        categories of security payloads, then flag responses that deviate from
        the baseline.

        For a single category returns JSON:
          {
            "baseline_status": int, "baseline_len": int,
            "anomalies": [
              {"payload": str,
               "anomaly": "Server Error (5xx)" | "Status Code Deviation (a -> b)"
                          | "Content Length Deviation (>20%)"
                          | "Payload Reflected in Response" | "Request Failed: ...",
               "status": int, "len": int (when relevant),
               "reflected": bool (present when the payload echoed back)}
            ]
          }
        For multiple categories (comma-separated payload_category, e.g.
        "sqli,xss,ssrf") returns {category: <result>, ...}.

        An empty `anomalies` list means nothing deviated — NOT proof of safety.
        `"reflected": true` is the strongest signal (potential XSS/injection);
        confirm it by inspecting the captured flow. This tool does NOT return a
        new_flow_id — re-run the winning payload via `traffic_replay` (which
        does) if you need to diff it.

        After judging the result, call `note_add(flow_id, verdict, ...)` so the
        triage outcome (vulnerable / not_vulnerable / inconclusive) is recorded
        — even when nothing fires, "not_vulnerable, tested X / Y / Z" is the
        most valuable note for the next session.
        Args:
            flow_id: The flow to use as base request
            target_param: Name of the parameter to fuzz
            param_type: Parameter location: 'query' or 'json_body'
            payload_category: One category, or comma-separated list. Available:
                'sqli', 'xss', 'path_traversal', 'ssrf', 'command_injection'
            timeout: Request timeout in seconds (default: 10)
        """
        cats = [c.strip() for c in payload_category.split(",") if c.strip()]
        if len(cats) <= 1:
            return await session.mitm.fuzz_endpoint(
                flow_id=flow_id, target_param=target_param,
                param_type=param_type,
                payload_category=cats[0] if cats else payload_category,
                timeout=timeout,
            )
        results = {}
        for category in cats:
            results[category] = await session.mitm.fuzz_endpoint(
                flow_id=flow_id, target_param=target_param,
                param_type=param_type, payload_category=category, timeout=timeout,
            )
        return json.dumps(results, indent=2)

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
                                kind: str = "finding",
                                stats: bool = False,
                                limit: int = 50) -> str:
        """List passive-scan results — high-confidence FINDINGS by default,
        lower-confidence SIGNALS via kind='signal' or kind='all'.
        One row per match: rule_id / severity / category / kind / flow_id / short evidence.
        Triage workflow: start here, then traffic_inspect / traffic_params /
        traffic_replay on the flows that look interesting.

        Args:
            severity: Filter 'info' | 'low' | 'medium' | 'high'
            category: Filter category, e.g. 'secret_leak', 'sqli_signal', 'cors_misconfig'
            rule_id: Filter by a specific rule
            flow_id: Show entries for one flow only
            kind: 'finding' (default — high confidence), 'signal' (low confidence),
                or 'all' to include both
            stats: When True, return aggregate counts by severity/category instead
                of individual rows — a quick attack-surface overview.
            limit: Max rows (default 50)
        """
        if stats:
            return json.dumps(session.mitm.db.findings_stats(), indent=2)
        rows = session.mitm.db.list_findings(
            severity=severity, category=category,
            rule_id=rule_id, flow_id=flow_id,
            kind=kind, limit=limit,
        )
        return json.dumps(rows, indent=2)

    @mcp.tool()
    async def traffic_diff(flow_a: str, flow_b: str, max_lines: int = 50) -> str:
        """Compare two captured flows. Outputs status/size deltas plus a JSON field-level diff
        (added/removed/changed paths) for JSON responses, or a unified text diff otherwise.
        Use for IDOR / privilege-escalation / parameter-pollution verification.

        After you reach a verdict on the diff, call `note_add(flow_id=flow_a, ...)`
        so the conclusion isn't lost.
        Args:
            flow_a: First flow id (baseline)
            flow_b: Second flow id (comparison)
            max_lines: Cap for unified text diff lines (default 50)
        """
        return session.mitm.diff_flows(flow_a, flow_b, max_lines=max_lines)

    # ==================== Tag / Link / Chain (multi-step trace) ====================

    @mcp.tool()
    async def traffic_tag(flow_id: str, tag: str) -> str:
        """Tag a flow with a semantic alias (e.g. 'login', 'ssrf_config_create',
        'idor_target_alice'). Tags persist in SQLite and survive session restarts.
        One flow can have many tags; tags can be reused across flows.
        """
        ok = session.mitm.db.add_tag(flow_id, tag)
        return f"Tagged: {tag}" if ok else "Failed to tag (empty tag or db error)"

    @mcp.tool()
    async def traffic_untag(flow_id: str, tag: str) -> str:
        """Remove a tag from a flow."""
        ok = session.mitm.db.remove_tag(flow_id, tag)
        return f"Untagged: {tag}" if ok else "Tag not present"

    @mcp.tool()
    async def traffic_find_by_tag(tag: str) -> str:
        """List all flow_ids that carry this tag. Use it as a stable index for
        recurring entry points (login, upload, admin endpoints) instead of
        searching by URL pattern."""
        ids = session.mitm.db.find_by_tag(tag)
        return json.dumps({"tag": tag, "flow_ids": ids, "count": len(ids)}, indent=2)

    @mcp.tool()
    async def traffic_link(source_id: str, target_id: str, relation: str = "") -> str:
        """Record that source_id's output influences target_id's input.
        Examples of relation strings: 'stored_input_trigger' (stored XSS/SSRF),
        'param_passthrough' (file_id from upload to preview), 'identity_swap'
        (replay with different identity), 'payload_mutation' (variant of source).
        Used by traffic_chain and evidence_bundle to walk the multi-step DAG."""
        ok = session.mitm.db.add_link(source_id, target_id, relation)
        return f"Linked: {source_id} -> {target_id} ({relation})" if ok else "Failed to link"

    @mcp.tool()
    async def traffic_chain(flow_id: str, depth: int = 2) -> str:
        """Return the local subgraph around `flow_id`: tags + upstream/downstream
        flows reached within `depth` hops via traffic_link relations. The agent
        uses this to assemble multi-step exploit chains (stored SSRF, OAuth flows,
        chained IDOR) and to feed evidence_bundle.
        Args:
            depth: BFS depth on each side (default 2, max 5)
        """
        return json.dumps(session.mitm.db.get_chain(flow_id, depth=depth), indent=2)

    @mcp.tool()
    async def traffic_correlate(freq_cap: int = 8, max_edges: int = 200) -> str:
        """Auto-correlate data-flow across ALL captured flows: find values minted
        in one flow's response that reappear in a later flow's request, and
        secrets reused across identities. Run this ONCE after recon — it turns a
        500-flow capture into a handful of highlighted chains so you know WHICH
        flows to triage.

        It writes the edges it finds into the same graph traffic_link uses, so
        immediately afterwards:
          - traffic_findings(category="dataflow") lists the passthrough signals
          - traffic_findings(rule_id="cross_identity_secret_reuse") lists
            cross-tenant / cross-account secret exposure (high)
          - traffic_chain(flow_id=...) / evidence_bundle walk the auto-created
            value_passthrough links

        These are CANDIDATES (token reuse can be legitimate token-refresh) —
        confirm the business meaning before reporting. Heart-of-the-bug for
        OAuth code-leak, echoed SSRF (A stores → B echoes), param-passthrough,
        and leaked-STS-credential reuse.

        Args:
            freq_cap: A value minted in more than this many flows is treated as
                global (session cookie / static hash) and skipped (default 8).
            max_edges: Cap on edges written in one pass (default 200).
        """
        return session.mitm.correlate_dataflow(freq_cap=freq_cap, max_edges=max_edges)

    @mcp.tool()
    async def traffic_params(flow_id: str) -> str:
        """Extract all mutable parameters of a flow (path / query / json body /
        form / interesting headers / cookies) and tag each with semantic
        categories like identity_param, ssrf_candidate, sql_candidate,
        privilege_param, state_token, etc.

        Use this BEFORE traffic_inspect — it tells the agent what to mutate
        without burning tokens on the body. Result keys point you straight at
        the most likely IDOR / SSRF / SQLi / privilege-escalation candidates.

        Tag dictionaries are loaded from the YAML rule pack — call
        config_show() to inspect what's currently active.
        """
        from ..core.param_extractor import extract_params
        flow_data = session.mitm.db.get_detail(flow_id, level="full", body_preview_length=256 * 1024)
        if not flow_data:
            return "Flow not found"
        return json.dumps(extract_params(flow_data, rules=session.rules), indent=2)

    @mcp.tool()
    async def evidence_bundle(flow_id: str, depth: int = 3) -> str:
        """Generate a Markdown evidence bundle for a vulnerability — walks the
        flow_links DAG `depth` hops on each side, emits each related flow's
        method/url, status, profile_label, tags, findings, body previews,
        triage notes (if any), and a curl reproducer. Drop the output straight
        into a SRC report.
        Args:
            flow_id: The root flow id (typically the trigger / final exploit step).
            depth: How many hops upstream and downstream to follow (default 3, max 5).
        """
        return session.mitm.evidence_bundle(flow_id, depth=depth)

    @mcp.tool()
    async def note_add(
        flow_id: str,
        verdict: str,
        scenario: str = "",
        sensitive_fields: str = "",
        test_steps: str = "",
        conclusion: str = "",
    ) -> str:
        """Record a triage note for a flow you just researched. ALWAYS call this
        once you reach a verdict on a flow — even when no vulnerability was
        found. The note is what future-you / the report builder reads back.

        Keep each section short and concrete (1-3 sentences each is plenty;
        each field is hard-capped at 1500 chars). One note per flow_id —
        calling again overwrites.

        Args:
            flow_id: The flow being judged.
            verdict: One of 'vulnerable' | 'not_vulnerable' | 'inconclusive'.
                Use 'inconclusive' when the endpoint deserves a second look
                with more context (different account, different payload, etc).
            scenario: WHAT IS THIS — business action, what could go wrong,
                what's notable in the traffic. e.g. "POST /api/order/cancel,
                JSON body has orderId; identity_param 'userId' present in cookie."
            sensitive_fields: WHICH FIELDS WERE TESTABLE — list the params /
                headers / cookies you considered, plus their semantic tags
                (use traffic_params if unsure). e.g. "orderId (object_id_param),
                userId (identity_param), redirect (redirect_candidate)."
            test_steps: WHAT YOU DID — the mutations / replays / diffs you ran
                and what each one returned. e.g. "Replayed via victim context,
                got 403; mutated orderId to 1, response identical to baseline;
                tried redirect=https://evil, server stripped scheme."
            conclusion: VERDICT JUSTIFICATION — for vulnerable: the impact +
                evidence (which flow_id contains the proof). For not_vulnerable:
                why you're confident. For inconclusive: what's still missing.
                Mention assumptions you made or angles you skipped.
        """
        try:
            note = session.mitm.db.upsert_note(
                flow_id=flow_id, verdict=verdict,
                scenario=scenario, sensitive_fields=sensitive_fields,
                test_steps=test_steps, conclusion=conclusion,
            )
            return json.dumps({"status": "saved", "note": note}, indent=2)
        except ValueError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def note_get(
        flow_id: str = None,
        verdict: str = None,
        limit: int = 50,
    ) -> str:
        """Read triage notes back. Without arguments returns the most recent 50
        notes across all flows; pass `flow_id` for a single note or `verdict`
        to filter (vulnerable / not_vulnerable / inconclusive).

        Use this BEFORE re-investigating a flow — you may have already judged
        it in an earlier turn.
        """
        if flow_id and not verdict:
            note = session.mitm.db.get_note(flow_id)
            return json.dumps(note or {"status": "no note for this flow"}, indent=2)
        notes = session.mitm.db.list_notes(verdict=verdict, flow_id=flow_id, limit=limit)
        stats = session.mitm.db.notes_stats()
        return json.dumps({"stats": stats, "notes": notes}, indent=2)

    @mcp.tool()
    async def note_remove(flow_id: str) -> str:
        """Delete the triage note for a flow."""
        ok = session.mitm.db.remove_note(flow_id)
        return "deleted" if ok else "no note for this flow"

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
        To extract one from a response instead, use traffic_extract(..., regex=, save_as=).
        Args:
            name: Variable name
            value: Variable value
        """
        session.mitm.session_variables[name] = value
        return f"Set session variable ${name} = {value}"

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

        To inject a header into every request (a "global header"), use
        action_type='inject_header' with url_pattern='.*' (the default) and a
        stable rule_id; remove it later with intercept_remove_rule(rule_id).

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

    # ==================== Scope Tools ====================

    @mcp.tool()
    async def scope_set(allowed_domains: str = None) -> str:
        """Set or clear the traffic-capture scope.

        Args:
            allowed_domains: Comma-separated domains to capture (e.g.
                'api.example.com,cdn.example.com'). Pass None or an empty string
                to clear the scope and capture all traffic.
        """
        domains = [d.strip() for d in (allowed_domains or "").split(",") if d.strip()]
        session.mitm.scope_manager.update_domains(domains)
        return f"Scope updated. Now tracking: {', '.join(domains) if domains else 'everything'}"

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
    async def export_session(format: str = "openapi", domain: str = None, limit: int = 200) -> str:
        """Export captured traffic in various formats.

        Args:
            format: 'openapi' (OpenAPI v3 spec), 'patterns' (clustered API
                endpoint patterns — also the API-discovery view), or 'traffic'
                (raw flow JSON — WARNING: large; capped by `limit`).
            domain: Filter by domain (optional).
            limit: For format='traffic' only — max most-recent flows to dump
                (default 200). Raise deliberately; dumping the whole table with
                bodies can blow the agent's context window.
        """
        if format == "openapi":
            return session.mitm.export_openapi_spec(domain=domain)
        elif format == "patterns":
            return session.mitm.get_api_patterns(domain=domain)
        elif format == "traffic":
            flows = session.mitm.db.get_all_for_analysis(limit=limit)
            return json.dumps({"count": len(flows), "limit": limit, "flows": flows}, indent=2)
        else:
            return f"Unknown format: {format}. Use 'openapi', 'patterns', or 'traffic'"

    # ==================== Prompts ====================
    # NOTE: All MCP prompts live in the repo's `prompts/` directory and are
    # loaded by `agent_proxy.prompt_loader`. They are intentionally NOT
    # embedded in this file — see prompts/README.md for the rationale and
    # format. If `prompts/` is missing or empty AgentProxy still runs; only
    # tools are exposed.
