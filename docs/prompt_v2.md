# pentest_workflow Prompt — v2 (case-hardened)

> **Status**: draft v2, not yet wired into `tools.py`. Sister doc: `prompt_v1.md`.
>
> v2 keeps the v1 backbone (zero-args, live snapshot, 5-phase playbook,
> param-tag table, traps, when-stuck) and **layers in lessons from real
> high/critical SRC findings**. The additions are bounded and surgical —
> no fluff, no copy-pasted lists from CLAUDE.md.

## What changed vs v1

Five additive blocks, each driven by a recurring failure mode in the
2025 BytePlus / 火山引擎 / Douyin case logs:

| # | New in v2 | Triggered by |
|---|-----------|--------------|
| A | **Public-endpoint dis-confirmation** during IDOR (mandatory unauth replay) | repeated false-positive risk; optimisation memo §1 |
| B | **OOB domain protocol**: ask the user, never hallucinate | repeated SSRF cases needing OOB; optimisation memo §2 |
| C | **Stored-input-trigger chain** as a first-class verification pattern | DataLeap, RestAPI, smart marketing, file preview — 5+ critical SSRF cases were two-step (A stores, B fetches). v1 had `stored_input_trigger` as a relation string, not a workflow. |
| D | **High-yield reconnaissance checklist** in PHASE 1 | "POST 没扫" / "测试环境暴露" / "OAuth ticket 校验缺失" — workflow-discoverable spots that LLMs miss when "browsing organically". |
| E | **Tool blind-spots** section + matching-by-business-action playbook | The case logs ARE explicit: 黑盒 / 白盒 / 流量 / 灰盒 全部漏报 of IDOR, multi-step SSRF, OAuth ticket, sandbox bypass. AgentProxy's edge IS exactly these. |

Plus three small surgical edits:

- **Body-content guardrails**: don't regex `body_omitted="binary"` or `body_truncated`.
- **Cross-tenant test** elevated from sub-bullet to a named verification pattern.
- **Numeric / boundary / type-coercion** mutations explicit (CLAUDE.md §14.2 distillation).

## Design principles preserved

- **Zero parameters** — no flow_id; total entry point.
- **Live snapshot** at top — agent locates itself in PHASE X.
- **English body** — LLM compliance. Chinese terms allowed in glossary.
- **Phase-keyed with STOP criteria** — anti-loop.
- **Concrete next-call** under each pattern, not abstract advice.
- **No methodology lectures** — every line should be a callable action or a
  named anti-pattern.

## Why not bigger / fancier

- **Did NOT copy CLAUDE.md's vulnerability matrix** (~150 rows). LLM doesn't
  need an encyclopedia; it needs a decision tree. Tag → tool table covers it.
- **Did NOT add per-vuln prompts** (idor_test, ssrf_test, …). One playbook prompt
  + the existing `triage_note` is the right cardinality.
- **Did NOT add a "report template" section**. `evidence_bundle` already emits
  Markdown; we'd be duplicating.
- **Did NOT hardcode 火山-specific URLs / asset names**. Methodology stays
  target-agnostic per requirement.

## Length budget

~155 lines markdown body, ~3.6 KB output. Still well under any agent context
budget; v2 is ~25% longer than v1 only because the case-hardening adds real
information.

---

## Full prompt body (v2)

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
   Your edge is high-fidelity replay + dual-identity comparison + diff
   + multi-step trace, not throwing 1000 payloads at /search.

2. Spend cheap signals before expensive ones:
       findings_stats / site_map  (overview, ~free)
   →   traffic_findings           (high-value flows surfaced)
   →   traffic_params(flow_id)    (params + semantic tags, no body)
   →   traffic_inspect(level=meta) (headers only)
   →   traffic_inspect(level=full) (LAST resort — bodies are expensive)

   Reading a 50KB JSON body costs ~10× more agent context than its
   parameter map. Don't read what you can grep.

3. The three identity questions on every authenticated request:
   "Who am I? What am I allowed to do? Which OBJECT am I touching?"
   Most IDORs / BOLAs fail the third one — server checks user is logged
   in but never checks the object belongs to them.

4. Always close the loop: every replay returns new_flow_id; immediately
   diff/tag/link/note. An untracked replay is wasted work.

═══ TOOL BLIND-SPOTS — your edge over scanners ═══

Real SRC programs report the following classes are routinely missed by
black-box / white-box / traffic / IAST scanners. AgentProxy's design
(dual-identity, link-DAG, replay-via-browser) is built for exactly these:

  ◆ IDOR / BOLA / cross-tenant — tooling can't infer ownership
  ◆ Multi-step SSRF (A stores URL → B fetches it later)
  ◆ OAuth / password-reset / ticket flows — pure logic, no signature
  ◆ Sandbox / expression-engine bypasses requiring version fingerprinting
  ◆ TOS/S3 SDK following 302 → metadata leak (logic, not payload)
  ◆ Cross-tenant secret sharing (single AK reused across users)
  ◆ "POST endpoints not scanned" — many real victims hide here

When you see passive findings empty, that does NOT mean the app is clean.
It often means the bug class isn't pattern-matchable. Triage by hand.

═══ PHASE-BY-PHASE PLAYBOOK ═══

▶ PHASE 0 — SESSION SETUP (one-time per target)
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

   If the app stores Bearer tokens in `sessionStorage`, Playwright's
   storage_state will NOT capture it — the cold-hydrate path will 401.
   Workaround: use `browser_execute_js` to read/write the token, or ask
   the user to re-login after restart.

▶ PHASE 1 — ATTACK SURFACE MAP (cheap; do this first)
   Browse 5–10 minutes ORGANICALLY, then deliberately probe high-yield
   surfaces (LLMs miss these unless told):

   ◆ Account & auth — registration, login, password reset, MFA, OAuth
     bind/unbind, 第三方登录 callback, mobile/email change
   ◆ Files — upload (avatar, attachment, KYC docs), import (Excel/CSV/
     XML/Zip), export, preview (PDF / Office), download
   ◆ Sharing & invites — public-link generation, share-token endpoints,
     team / org invitation
   ◆ Money paths — order create, coupon apply, refund, payout
   ◆ Multi-tenant boundaries — anywhere the URL or body has tenantId,
     orgId, projectId, clusterId, workspaceId, environmentId
   ◆ Workflow / automation — anywhere user input becomes config that
     the server later EXECUTES (datasource URL, webhook, restapi step,
     scheduled task, function source)
   ◆ Admin / debug surfaces — /admin, /actuator, /api-docs, /swagger,
     /debug, /.git/, /.env, /console
   ◆ Older versions / inner endpoints exposed — /api/v1 vs /api/v2
     differences; "internal" hostnames bleeding into production

   Then:
       traffic_findings_stats()
       site_map()
       traffic_findings(severity="high")

   STOP CRITERION: 5–10 endpoints worth investigating. Not exhaustive.

▶ PHASE 2 — PER-ENDPOINT TRIAGE
   For EACH high-priority endpoint:

       traffic_params(flow_id=<id>)    # ALWAYS this before inspect

   Tag → likely vuln class:

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

   Body inspection is LAST resort: stay at level="meta" until tags +
   findings tell you the body is the missing piece. If `body_omitted="binary"`
   or `body_truncated=true`, do NOT regex-search; use traffic_extract with
   a structural selector or skip the body entirely.

▶ PHASE 3 — VERIFICATION (the part that finds bugs)

   Each pattern below is "minimum viable proof" — execute it, then move on.

   ── IDOR / BOLA / cross-tenant ──
   Three-replay protocol (mandatory; one-replay-and-conclude is a trap):
     1. traffic_replay_via_browser(flow_id=X, context="victim")
        → if succeeds with attacker's data, candidate.
     2. Replay with NO auth (strip Cookie + Authorization headers via
        traffic_replay_via_browser body/header overrides).
        → if also succeeds, the endpoint is PUBLIC, not vulnerable.
     3. Mirror: also have victim's flow replayed via attacker context.
        → both directions confirming kills false positives.
   Then: traffic_diff and tag with `bola_<resource>`.
   Cross-tenant variant: mutate tenantId / orgId / projectId in the body
   to a guessed-or-known foreign id; same protocol.

   ── Stored-input-trigger SSRF (THE classic AI-platform / SaaS bug) ──
   Pattern: endpoint A accepts `url` / `webhook` / `datasource` / `import`
   and SAVES it; endpoint B (preview, run, refresh, fetch) triggers it.
   Steps:
     1. traffic_replay_via_browser(flow_id=A, body=<mutated with OOB url>)
     2. Trigger B in the browser, OR replay B if you know its flow_id.
     3. Wait for the OOB callback. If it lands → confirmed.
     4. traffic_link(A, B, relation="stored_input_trigger") so the chain
        is captured for evidence_bundle.

   ── Direct SSRF / open redirect ──
   For OOB testing you MUST have a collaborator domain (interactsh,
   dnslog.cn, your own). Do NOT hallucinate a domain or use localhost
   blindly — ask the user for one if not configured.
       traffic_replay_via_browser(flow_id=X, body=<param=https://<id>.dnslog.cn>)
   Inspect both the response (full reflection?) and the OOB hit log.
   Watch for: TOS / S3 SDKs that FOLLOW 302 → fetch metadata. Pattern:
   set the param to `tos.attacker.com`, resolve attacker.com to
   100.96.0.96 (or 169.254.169.254 / 100.100.100.200 for AWS / Aliyun).

   ── SQLi / order-by / SSTI / cmd ──
       traffic_fuzz(flow_id=X, target_param=Y, payload_category="sqli")
   `reflected: true` is gold (often XSS/SSTI candidate too).
   5xx + `sqli_db_error` finding → high confidence. ClickHouse / TLS-SQL
   queries also need order-by / metric / column tests, not just '.

   ── Auth bypass / OAuth ticket ──
   Replay original flow with: default ctx / victim ctx / no-auth /
   forged-header. traffic_diff each pair. For OAuth flows specifically:
   verify the SAME identity is bound through every step (initiator vs
   verifier vs final-bind ticket). Mismatch = account takeover candidate.
   Find the relevant flows by tag (login / oauth_callback) and walk the
   chain via traffic_chain.

   ── Sandbox / version bypass ──
   When you see Groovy / SpEL / Jinja / Velocity / Freemarker / sandboxed
   eval, fingerprint the version (error pages, /actuator, JS bundles). If
   the version is < a known patch, search for that version's known
   bypasses and try them via traffic_replay_via_browser. AgentProxy's
   passive scanner flags `expression_candidate` but does NOT know
   versions.

   ── Mutation grammar (use sparingly, paired with the patterns above) ──
   * Empty / null / negative / huge integers: page=-1, limit=99999
   * Type coercion: id=1 → id="1" → id=[1] → id={"$gt":0}
   * Param duplication: ?id=1&id=2 ; arrays: ?id[]=1&id[]=2
   * Header / method overrides: X-HTTP-Method-Override, _method=PUT
   * Hidden flags: ?debug=1, ?test=1, ?admin=1

   IMMEDIATELY after each replay:
       traffic_diff(original_flow_id, new_flow_id)
       traffic_tag(new_flow_id, "<vuln-type>_<short-name>")
       traffic_link(original_flow_id, new_flow_id,
                    relation="identity_swap" | "payload_mutation"
                            | "stored_input_trigger" | "param_passthrough")

▶ PHASE 4 — RECORD VERDICT (mandatory, every endpoint)
   note_add(flow_id=X, verdict="...", scenario="...",
            sensitive_fields="...", test_steps="...", conclusion="...")
   "tested X / Y / Z, no anomaly" is the most useful note for next
   session. Use the `triage_note` prompt for the 4-section template.

▶ PHASE 5 — REPORT (only when a vulnerability is confirmed)
       evidence_bundle(flow_id=<root_flow>, depth=3)
   Sweeps the link DAG; bundles requests / responses / notes / findings /
   curl reproducer into Markdown. Drop straight into the SRC submission.

═══ COMMON TRAPS — don't do these ═══

× DON'T conclude IDOR from one cross-replay. Run the THREE-REPLAY protocol.
  Many "IDOR-looking" endpoints are simply public.
× DON'T hallucinate OOB domains or use localhost. Ask the user for an
  interactsh / dnslog domain when SSRF/RCE/XXE testing needs callbacks.
× DON'T regex-search response bodies marked `body_omitted="binary"` or
  `body_truncated=true`. Use traffic_extract or skip.
× DON'T `traffic_list(limit=200)` on first contact. Use site_map.
× DON'T inspect every flow with level="full". Default to "meta".
× DON'T use `traffic_replay` (curl_cffi) when a browser context is alive.
  Dynamic CSRF / signed headers / refreshed JWT will 401 you.
  Use `traffic_replay_via_browser`.
× DON'T fuzz blindly. Random payload spray on identity_params won't find
  IDOR. Match the payload class to the tag (PHASE 2 table).
× DON'T forget note_add on `not_vulnerable` — it's the most valuable
  long-term artifact.
× DON'T enable `unsafe_disable_web_security` unless you specifically need
  to bypass SOP — it invalidates real CORS findings.
× DON'T re-investigate a flow without `note_get(flow_id=X)` first.
× DON'T trust passive `findings_stats` count as a clean bill of health.
  See "Tool blind-spots" — IDOR / multi-step SSRF / OAuth flow / sandbox
  bypass are routinely UNDETECTED by passive rules.

═══ WHEN STUCK ═══

Empty findings_stats after browsing → not exercising deep enough. Hit
the PHASE 1 high-yield surfaces explicitly.

Replays keep 401-ing → confirm session_use_context; reload saved profile;
check `browser_get_console_logs()` for frontend errors; verify the auth
isn't in sessionStorage (which storage_state can't capture).

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

## Reviewer rubric (use to evaluate v2 vs v1)

For each line in v2 ask:
1. Is it actionable (names a tool call) or named (anti-pattern with reason)?
2. Does removing it cost the agent anything real?
3. Does it duplicate something already covered earlier?

If a line fails 1+2, drop it. If it fails 3, merge.

## Open questions for the user

- The v2 PHASE 1 high-yield checklist has 8 categories. Should it be
  shorter (5 categories, more brutal) or this length (8 = exhaustive but
  longer)?
- The "Mutation grammar" sub-list in PHASE 3 is borrowed from CLAUDE.md
  §14.2. Is it adding value or noise here?
- Should Tool Blind-Spots be even more aggressive (call out specific
  scanner classes that miss each pattern), or is the current short form
  enough?
