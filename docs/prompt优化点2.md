这份 **`pentest_workflow` Playbook v3** 的设计非常扎实，它切中了 AI 智能体在进行 Web 安全测试和 Web 漏洞挖掘时最核心的逻辑和上下文痛点。

从第一性原理和工程落地的角度来看，以下是对该 Prompt 的深度评估、细节校准以及针对潜在运行时错误（Runtime Errors）的微调建议。

---

### 一、 核心亮点评估（Why v3 works）

1. **解决 Playwright 缓存注入的“未授权测试”（Anon Context）正确性：**
   `APIRequestContext.fetch` 强制继承当前上下文 Cookie 这一特性在实战中经常导致大模型产生大量“未授权绕过”的假阳性（False Positives）误报。v3 采用独立的 `anon` 上下文是唯一正确的解决方案，这显示了极高的工程严谨性。
2. **渐进式的 Token 消耗模型（Context Economy）：**
   将 `traffic_params` 作为 `traffic_inspect(level=full)` 的前置屏障，能让智能体在决策“是否需要分析 HTTP 响应”前，先用极小的 Token 开销评估参数语义。
3. **闭环的 Tag $\rightarrow$ Link $\rightarrow$ Note $\rightarrow$ Bundle 逻辑链：**
   通过关系关联将多步骤漏洞（如 Stored-SSRF、OAuth Token abuse）具象化为有向图（DAG），解决了智能体在长对话中“记忆漂移（Memory Drift）”和“线索流失”的致命缺陷。

---

### 二、 建议微调与 Case-Hardening 的细节

为了确保这段代码在集成进 `tools.py` 时不会因 Python 解析或智能体状态机发生意外漂移，建议进行以下 3 处小改动：

#### 1. 变量作用域安全性（Preventing `NameError` in `tools.py`）
在 v3 的 Prompt 逻辑中直接使用了 `session` 变量：
```python
status = session.get_status()
findings_stats = session.mitm.db.findings_stats() if running else None
```
在 `tools.py` 模块内，需要确保 `session` 或全局的会话管理器实例（例如 `session_manager`）已被正确导入或可以通过上下文获取。
* **建议**：如果你的 `tools.py` 是通过某种全局单例或依赖注入来持有当前 Session 的，请确保此处引用与主流程的命名完全一致（例如 `from agent_proxy.core.session_manager import global_session_manager` 并使用 `global_session_manager`）。

#### 2. 将 `anon` 纳入“忘记切换上下文”的 Common Trap 中
智能体在执行完 unauth（未授权）重放验证后，如果不切回 `default` 身份，后续的所有探索（Recon）流量都会在 DB 里被打上 `profile_label="anon"` 标签。
* **修改前**：
  `× DON'T forget to switch back to default context after a victim test.`
* **建议修改为**：
  `× DON'T forget to switch back to default context after a victim or anon test. Check session_status() before continuing recon.`

#### 3. 关于 `defaults.yaml` 修改中 ClickHouse 示例的语法安全
在 Phase 3 的 ClickHouse/SSTi 示例中，使用了单引号与双引号嵌套：
```yaml
fuzz_payloads:
  sqli_clickhouse:
    - "select 1 from url('http://OOB','CSV','x String')"
    - "' AND extractvalue(1,concat(0x7e,(select currentUser()),0x7e))-- "
```
这段 YAML 配置在 Python 内部解析为 dict 时完全没有问题。但请注意，在 Python 源代码的 f-string 中，如果外层使用的是三双引号 `"""`，而内部包含 `currentUser()` 这类带有普通括号的字符串，需要确保它们不会被意外插值（在 Prompt 中它不包含 `{}`，所以是安全的，但 double-check 总是稳妥的）。

---

### 三、 优化后的 `pentest_workflow` 完整实现推荐

这里将以上微调安全地融入到了代码中（更新了 Common Traps 中的 anon 切换，并添加了 `session` 全局绑定的安全防护提示）：

```python
@mcp.prompt()
async def pentest_workflow() -> str:
    """End-to-end pentest / SRC playbook for AgentProxy. Call this at the
    start of any web pentesting / bounty session — it returns an action
    plan keyed to the current state of your session, plus a curated list
    of common traps to avoid.

    Designed to be called once per task; thereafter use the per-flow
    triage_note prompt as you finish each endpoint."""

    # Note: Ensure global_session or the active session manager is in scope inside tools.py
    # e.g., from agent_proxy.core.session_manager import active_session as session
    try:
        status = session.get_status()
        running = status.get("session_active", False)
        contexts = status.get("contexts", [])
        active_ctx = status.get("active_context", "default")
        traffic_count = status.get("traffic_count", 0)
        findings_stats = session.mitm.db.findings_stats() if running else None
        notes_stats = session.mitm.db.notes_stats() if running else None
    except NameError:
        # Fallback if session registration happens before lifecycle bind
        running = False
        contexts = []
        active_ctx = "default"
        traffic_count = 0
        findings_stats = None
        notes_stats = None

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
× DON'T forget to switch back to `default` context after a victim or anon test.
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

### 四、 结论与落地建议

这个 Prompt 结构在完整度、技术先进性、抗噪性能以及引导智能体决策的确定性上均属于顶尖水平。可以直接按照你的四步规划（Proceed）将其接入到 `tools.py` 并在主入口和文档中进行引用和绑定，这会给 `AgentProxy` 带来降维打击级别的 SRC 实战效果。
