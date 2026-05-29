# AgentProxy 设计文档

## 1. 设计原则

1. **智能体优先**：所有工具设计以 AI 智能体的使用习惯为核心，而非人类 GUI 操作
2. **上下文友好**：严格控制返回数据量，避免 MCP 上下文爆炸
3. **零配置集成**：浏览器 + MITM 代理一体化，无需手动配置
4. **渐进式复杂度**：L1-L6 工具分层，简单任务用简单工具，复杂任务用工作流工具
5. **攻防实战导向**：每个功能都经过安全测试场景验证

## 2. 模块设计

### 2.1 核心模块

#### models.py - 数据模型

```
SessionConfig          - 会话配置（代理端口、headless、超时等）
InterceptionRule       - 拦截规则（URL匹配、动作类型、阶段等）
ScopeConfig            - 作用域配置（允许域名、忽略扩展名等）
FlowSummary            - 流量摘要（ID、URL、方法、状态码等）
FlowDetail             - 流量详情（请求/响应完整数据）
AuthSignal             - 认证信号（检测类型、匹配信号、关联flow）
FuzzAnomaly            - 模糊测试异常（payload、异常类型、状态码）
BrowserState           - 浏览器状态（URL、标题、运行状态）
```

#### core/traffic_db.py - 流量数据库

**设计决策**：
- 使用 SQLite 而非内存存储，确保流量持久化和大流量场景下的内存效率
- UPSERT 语义：同一 flow 的 request 和 response 可能分两次写入，需要覆盖更新
- 索引策略：timestamp（时间排序）、url（域名搜索）、method（方法过滤）
- Header 存储格式：有序列表 `[[key, value], ...]`，保留顺序和重复键

**关键方法**：
- `save_flow()` - 保存/更新流量记录
- `get_summary()` - 获取流量摘要列表
- `get_detail()` - 获取流量详情（含 body 预览）
- `search()` - 多条件搜索
- `get_all_for_analysis()` - 获取全量分析数据（支持 lightweight 模式）
- `get_by_ids()` - 批量查询（支持字段选择）

#### core/mitm_controller.py - MITM 控制器

**设计决策**：
- 使用 mitmproxy 的 `DumpMaster` 而非 `mitmdump` 命令行，实现进程内控制
- TrafficRecorder 和 TrafficInterceptor 作为 mitmproxy addon 注册
- 重放引擎使用 curl_cffi 而非 requests，模拟浏览器 TLS 指纹
- 模糊测试支持 5 种 payload 类别，每种包含 3-5 个经典 payload
- 异常检测基于三个维度：5xx 状态码、状态码偏差、响应体长度偏差（>20%）

**ScopeManager 设计**：
- 域名匹配支持精确匹配和通配符（`*.example.com`）
- 默认忽略静态资源扩展名和 OPTIONS 方法
- 空域名列表 = 允许所有

**TrafficInterceptor 设计**：
- 三种动作类型：inject_header（注入Header）、replace_body（正则替换Body）、block（阻断请求）
- 规则匹配：URL 正则 + HTTP 方法 + 阶段（request/response）
- 正则编译缓存，避免重复编译

#### core/browser_controller.py - 浏览器控制器

**设计决策**：
- 代理配置在浏览器启动时注入，所有页面自动走代理
- `--ignore-certificate-errors` 解决 MITM 的 HTTPS 证书问题
- `--disable-web-security` 允许跨域请求，便于测试
- 默认 User-Agent 模拟 Chrome 120
- 支持 Accessibility Tree 获取，便于智能体理解页面结构

**关键方法**：
- `start()` / `stop()` - 浏览器生命周期管理
- `navigate()` - 页面导航（支持 wait_until 参数）
- `click()` / `fill()` / `type_text()` - 元素操作
- `screenshot()` - 截图（返回 base64）
- `get_text()` / `get_html()` - 内容获取
- `execute_js()` - JavaScript 执行
- `get_accessibility_tree()` - 无障碍树获取
- `set_extra_http_headers()` / `set_offline()` - 网络控制

#### core/session_manager.py - 会话管理器

**设计决策**：
- 统一管理 BrowserController 和 MitmController 的生命周期
- 启动顺序：先启动 mitmproxy → 再启动浏览器（浏览器需要代理已就绪）
- 停止顺序：先关闭浏览器 → 再关闭代理（避免代理关闭后浏览器请求失败）
- 高级工作流方法封装常见操作组合

**高级工作流**：
- `browse_and_capture()` - 导航 + 自动抓包 + 可选后续操作
- `api_discover()` - API 端点自动发现
- `security_scan()` - 多类别安全扫描

### 2.2 工具模块

#### tools/tools.py - MCP 工具注册

**工具分类设计**：

| 类别 | 工具 | 输入 | 输出 |
|------|------|------|------|
| Session | session_start | proxy_port, headless, profile_dir?, unsafe_disable_web_security? | JSON状态 |
| Session | session_stop | - | JSON状态 |
| Session | session_status | - | JSON状态（含 contexts/active_context） |
| Session | session_save_profile | name?, path? | 文本结果 |
| Session | session_create_context | name, from_profile=True | 文本结果 |
| Session | session_use_context | name | 文本结果 |
| Session | session_list_contexts | - | JSON |
| Session | config_show | section? | JSON 当前生效的规则包 |
| Browser | browser_navigate | url, wait_until | JSON导航结果 |
| Browser | browser_click | selector | 文本结果 |
| Browser | browser_fill | selector, value | 文本结果 |
| Browser | browser_type | selector, value, delay | 文本结果 |
| Browser | browser_select_option | selector, value | 文本结果 |
| Browser | browser_press_key | key | 文本结果 |
| Browser | browser_screenshot | - | Base64图片 |
| Browser | browser_get_text | selector? | 文本内容 |
| Browser | browser_get_html | selector? | HTML内容 |
| Browser | browser_execute_js | script | JSON结果 |
| Browser | browser_wait_for | selector, timeout | 文本结果 |
| Browser | browser_go_back | - | 文本结果 |
| Browser | browser_go_forward | - | 文本结果 |
| Browser | browser_reload | - | 文本结果 |
| Browser | browser_get_cookies | - | JSON cookies |
| Browser | browser_set_cookies | cookies(JSON) | 文本结果 |
| Browser | browser_set_headers | headers(JSON) | 文本结果 |
| Browser | browser_set_offline | offline | 文本结果 |
| Browser | browser_accessibility_tree | - | JSON树 |
| Browser | browser_get_console_logs | clear=False | JSON 日志列表 |
| Traffic | traffic_list | limit, with_findings? | JSON列表 |
| Traffic | traffic_inspect | flow_id, level=meta\|preview\|full | JSON详情 |
| Traffic | traffic_search | query, domain, method, limit | JSON列表 |
| Traffic | traffic_clear | - | 文本结果 |
| Traffic | traffic_extract | flow_id, json_path/css_selector | JSON数据 |
| Traffic | traffic_replay | flow_id, method, headers, body, timeout | JSON结果(含 new_flow_id) |
| Traffic | traffic_replay_via_browser | flow_id, method, headers_json, body, timeout_ms, context | JSON结果(含 new_flow_id, via, context) |
| Traffic | traffic_diff | flow_a, flow_b, max_lines | JSON差异 |
| Traffic | traffic_fuzz | flow_id, target_param, param_type, payload_category | JSON异常+反射标记 |
| Traffic | traffic_findings | severity?, category?, rule_id?, flow_id?, kind, limit | JSON线索 |
| Traffic | traffic_findings_stats | - | JSON聚合(拆 findings/signals) |
| Traffic | traffic_params | flow_id | JSON 参数地图 + 11 类语义标签 |
| Traffic | traffic_tag | flow_id, tag | 文本结果 |
| Traffic | traffic_untag | flow_id, tag | 文本结果 |
| Traffic | traffic_find_by_tag | tag | JSON flow_ids |
| Traffic | traffic_link | source_id, target_id, relation | 文本结果 |
| Traffic | traffic_chain | flow_id, depth | JSON 拓扑 |
| Traffic | evidence_bundle | flow_id, depth | Markdown 报告（含笔记） |
| Traffic | note_add | flow_id, verdict, scenario, sensitive_fields, test_steps, conclusion | JSON 写入结果 |
| Traffic | note_get | flow_id?, verdict?, limit | JSON 笔记列表 |
| Traffic | note_remove | flow_id | 文本结果 |
| Traffic | site_map | domain? | JSON站点树 |
| Traffic | traffic_auth_detect | flow_ids? | JSON认证模式 |
| Traffic | traffic_api_patterns | domain?, limit? | JSON端点列表 |
| Traffic | traffic_openapi | domain?, limit? | JSON OpenAPI |
| Traffic | traffic_generate_code | flow_ids, framework | 代码文本 |
| Traffic | traffic_set_session_variable | name, value | 文本结果 |
| Traffic | traffic_extract_session_variable | name, flow_id, regex, group | 文本结果 |
| Intercept | intercept_add_rule | rule_id, action_type, url_pattern, ... | 文本结果 |
| Intercept | intercept_list_rules | - | JSON规则列表 |
| Intercept | intercept_remove_rule | rule_id? | 文本结果 |
| Intercept | intercept_set_global_header | key, value | 文本结果 |
| Intercept | intercept_remove_global_header | key | 文本结果 |
| Scope | scope_set | allowed_domains | 文本结果 |
| Scope | scope_clear | - | 文本结果 |
| Workflow | browse_and_capture | url, wait_until, actions | JSON结果 |
| Workflow | api_discover | domain? | JSON端点列表 |
| Workflow | security_scan | flow_id, target_param, ... | JSON扫描结果 |
| Workflow | export_session | format, domain? | JSON/代码 |

## 3. 关键设计决策

### 3.1 为什么用 Python 而非 Node.js？

- mitmproxy 是 Python 原生，Node.js 集成需要子进程或 IPC
- Playwright Python API 与 Node.js API 功能对等
- MCP Python SDK (FastMCP) 成熟度足够
- 统一语言减少依赖复杂度

### 3.2 为什么用 mitmproxy 而非 CDP 网络监控？

| 维度 | CDP 网络监控 | mitmproxy MITM |
|------|-------------|----------------|
| HTTPS 解密 | 需要额外处理 | 原生支持 |
| 请求修改 | 有限（route/fulfill） | 完整（任意修改） |
| 请求阻断 | 支持 | 支持 |
| 请求重放 | 不支持 | 支持（curl_cffi隐身） |
| 模糊测试 | 不支持 | 支持 |
| 认证检测 | 不支持 | 支持 |
| 代码生成 | 不支持 | 支持 |
| 独立运行 | 依赖浏览器 | 可独立运行 |

### 3.3 上下文管理策略

1. **流量列表**：默认返回最近 20 条，仅含摘要信息
2. **流量详情**：body 默认截断到 2000 字符，full_body 模式截断到 50KB
3. **搜索结果**：默认最多 50 条
4. **API 模式**：lightweight 模式不返回 body，减少内存
5. **批量查询**：支持字段选择，只返回需要的列

### 3.4 会话变量系统

设计用于在重放请求时动态替换参数：

```
1. 智能体通过 traffic_extract_session_variable 从响应中提取 Token
2. Token 存储为会话变量 $token
3. 重放时 headers/body 中的 $token 自动替换为实际值
4. 支持链式操作：登录 → 提取 Token → 带 Token 重放
```

### 3.5 流量分层抽象（v0.2）

**核心问题**：智能体每次只能消化几 KB 上下文，几百条流量逐条 inspect 必爆。

**解决方案**：把流量数据分三档暴露，让 agent 按需下钻。

| 层级 | API | 内容 | 用途 |
|------|-----|------|------|
| L0 摘要 | `traffic_list` | id / method / url / status_code / size（每行 < 200 字节） | 浏览全局 |
| L1 线索 | `traffic_findings` | rule_id / severity / category / flow_id / 短 evidence | 优先关注高价值流量 |
| L2 站点 | `site_map` | 按 host 聚合的 endpoint 列表 + 参数集 + auth_required + finding 计数 | 攻击面地图 |
| L3 头 | `traffic_inspect(level=meta)` | request/response headers，no body | 看认证 / 类型判断 |
| L4 预览 | `traffic_inspect(level=preview)` | headers + body 截断 2KB（默认） | 大多数场景够用 |
| L5 完整 | `traffic_inspect(level=full)` | headers + body 上限 256KB | 提取 / 重放前确认 |

agent 的工作流：先看 `traffic_findings_stats` → 拿 `site_map` 看面 → `traffic_findings(severity="high")` 拿点 → 选定 flow 用 `level=meta` 确认 → 必要时再下 `level=full`。

### 3.6 浏览器状态保持（v0.2）

**问题**：每次 `session_stop` 后 cookie/localStorage 全部丢失，下次启动还得重登录；curl_cffi 重放使用 db 里 cookie，浏览器一刷新就过期。

**两件事一起做**：

1. **Profile 持久化** — `session_start(profile_dir=...)` 启动时若 `<dir>/state.json` 存在就 `new_context(storage_state=...)` 恢复；停止时自动 `context.storage_state(path=...)` 保存。`session_save_profile` 工具支持登录后立刻快照（避免崩溃丢失）。
2. **浏览器上下文重放** — `traffic_replay_via_browser` 用 `context.request.fetch()` 走活的浏览器会话，自动复用最新 cookie / 续期后的 token / CSRF。浏览器未启动时降级到 curl_cffi。

CDP 模式不引入额外抽象——用户已经用 `--user-data-dir` 自管 profile。

### 3.7 PassiveScanner 设计（v0.2）

**核心权衡**：高精度 vs 高召回。

agent 的上下文比一份漏报更稀缺：误报一次让 agent 浪费几次工具调用，比漏报一个低危问题代价大得多。所以 8 条规则全部按"出现即高确信度"标准筛选：

- **不做**：basic SSRF 检测（误报海量）/ XSS pattern 匹配（同上）/ 模糊的"可疑"标记
- **做**：明确签名（AKIA 前缀的 AWS Key、JWT 三段、SQLSTATE 关键字）/ 行为型误配（CORS 通配符 + credentials）/ 路径已知风险点（`.git/`、`/actuator`）

规则集中在 `core/passive_scan.py`，新增规则 = 加一行 `(rule_id, severity, category, regex)` 到 `_RESPONSE_BODY_RULES`。

### 3.8 Findings 表与去重

`UNIQUE(flow_id, rule_id, evidence)` 自动去重 — 同一 flow 的同一规则、同一 evidence 只入一条。这意味着规则可以放心地重复扫描历史流量（`scan_existing_flows`），不会污染。

存储成本：每条 finding ~150 字节，10 万条流量预期产生 ~3000 条 finding，~450KB，可忽略。

### 3.9 双身份冷热融合（v0.3）

**核心矛盾**：单纯的"双 BrowserContext"在长会话下吃内存且崩溃丢状态；单纯的"profile 快照 + curl_cffi"在动态前端签名/CSRF 校验下保真度差。Playwright 的 `storage_state` 把同一份数据具象成"热（活 context）"和"冷（磁盘 JSON）"两种形态，两态可在 < 200ms 内互转。

**实现选择**：

```
活 context  (热)  ←──── ensure_context_from_profile() ──── <name>_state.json (冷)
   │ Playwright BrowserContext               │ /<profile_dir>/<name>_state.json
   │ 自动带最新 cookie / 续期 token / CSRF      │ stop_session() 时所有 contexts dump
   │ replay 走 context.request.fetch()         │ 下次 start_session 时只恢复 default
   │ 高保真                                   │ 其他 name 的快照按需 hydrate
```

每个 context 启动时由 BrowserController 注入 `X-AgentProxy-Context: <name>` 头；MITM Recorder 在 `request()` 阶段剥头并写 `flows.profile_label`，目标服务器永远看不到这个头。

`replay_via_browser` 的四级路由（按代价递增）：
1. **活 context** — 已 create_context，直接 `request.fetch`，最快最准
2. **冷 hydrate** — `<profile_dir>/<name>_state.json` 存在 → `_create_named_context(from_profile=True)` 在内存里复活，单次 ~150ms
3. **完全冷启动 fallback** — 浏览器停止但磁盘 storage_state 在 → `replay_with_storage_state` 用 curl_cffi 加载 cookies 发包；保真度低但能跑
4. **默认身份** — 都没匹配上 → 最朴素的 curl_cffi replay

CDP 模式不引入额外抽象 — 用户已经用 `--user-data-dir` 自管 profile。

### 3.10 多步骤 Trace：Tag + Link

LLM 自己就是状态机，让 agent 维护后端 workflow 状态会高频出错。所以**不做** workflow 状态机，只做两个最小原语：

- **Tag**（"这是什么"）：把语义别名挂到 flow 上，agent 后续可用 `traffic_find_by_tag("login")` 找回去，避免在 Prompt 里硬塞 flow_id。
- **Link**（"怎么连"）：声明 A→B 的有向数据流（relation 是自由文本，如 `stored_input_trigger` / `payload_mutation` / `identity_swap`）。

两张表 < 100 行 SQL，配 5 个工具：`traffic_tag` / `traffic_untag` / `traffic_find_by_tag` / `traffic_link` / `traffic_chain(depth)`。

`evidence_bundle(flow_id)` 是这套机制的最大消费者：沿 chain 的上下游 BFS 收集相关 flow，渲染成 Markdown，自然就是攻击链证据报告。

### 3.11 traffic_params 语义参数地图（v0.3）

agent 看一个接口要决定"改哪个参数"时，最贵的成本是把 body 拉进上下文。`traffic_params` 把所有可变参数名（path/query/json/form/headers/cookies）按位置分组列出，每个参数附 11 类语义标签：

```
identity_param, object_id_param, privilege_param, money_param,
ssrf_candidate, object_storage, redirect_candidate, file_param,
sql_candidate, expression_candidate, command_candidate, state_token
```

词表全部来自真实 SRC 报告，不做泛化（`uid` 是 identity，`uid_xxx` 不是）。匹配按 `[-_.]` 分词后精确比对。

JSON body 嵌套递归，key 用 `.` 拼路径（如 `user.profile.userId`）；二进制/超大 body（>256KB）跳过。

Cookie 仅暴露 **name 列表**不暴露 value（避免 agent 上下文里出现真实 session token）；Authorization 标 Bearer/JWT/Basic 类型不输出原值。

### 3.12 Findings vs Signals 分层（v0.3）

agent 的上下文比一份漏报更稀缺。`missing_csp / cookie_insecure / sensitive_param` 这三类规则在真实流量里命中率高、单独不构成漏洞，混进 findings 会刷屏。

实现：findings 表加 `kind` 列（`finding` / `signal`），规则在 passive_scan.py 里显式声明 kind。`traffic_findings` 默认 `kind="finding"`，传 `"signal"` 或 `"all"` 拿低置信线索。`findings_stats` 把 findings / signals 拆成两个独立计数。

agent 工作流：先 `traffic_findings()` 看高置信问题；缺乏线索时再 `traffic_findings(kind="signal")` 探索；最终用 site_map 看面、用 traffic_params 看具体接口。

### 3.13 Replay 闭环（v0.3）

旧版 `traffic_replay` 返回字符串，agent 拿到结果不知道新 flow 的 id，只能 `traffic_list` 翻最新再猜。

新版结构化返回：

```json
{
  "via": "browser_context|curl_cffi|curl_cffi+storage_state",
  "context": "victim",
  "status_code": 200,
  "size": 1234,
  "new_flow_id": "abc-123-...",
  "headers": {...},
  "body_preview": "..."
}
```

实现：replay 前 `time.time()` 拿到 `before_ts`，发包后 SQL 找 `WHERE timestamp > before_ts AND url = ? AND method = ? ORDER BY timestamp DESC LIMIT 1`。

闭环：`traffic_replay → new_flow_id → traffic_diff(orig, new_flow_id) → traffic_link(orig, new_flow_id, "identity_swap") → evidence_bundle(orig)`。

### 3.14 YAML 规则包（v0.3）

**问题**：v0.3 之前所有词表（30+ 高敏参数名）/ 正则规则（10 条 passive 规则）/ payload 字典（5×3-5 个 payload）都硬编码在 Python 文件里。每次接新目标想加个 `larkAccountID` / `Stripe key` regex / `SSTI {{7*7}}` 都要改代码 + commit + 重 build，单纯的内容变更绑死研发节奏。

**解法**：所有"内容型"可调数据抽到 `src/agent_proxy/config/defaults.yaml`，启动时与用户 override 文件深合并：

```
explicit --config flag    →  AGENT_PROXY_CONFIG env  →  ./agent_proxy.yaml  →  bundled defaults
```

合并规则刻意保持简单：
- **dict 递归合并** — 用户想加几个新 semantic 类别，`semantic_params: {my_cat: [...]}` 即可，其他类别原样保留
- **list 整体替换** — 用户改 body_rules 必须列全集，避免"加 1 条"和"想替换却被 append"两种期望冲突
- **invalid regex skipped** — 单条坏规则被记 warning 跳过，其他规则继续生效，避免一条 typo 全盘失败

数据流：`SessionManager.__init__` → `load_rule_config(user_config_path)` → `RuleConfig` 一次构建 → 注入给 `MitmController(rules=)` → 进而注入给 `PassiveScanner(rules=)`；`extract_params(flow_detail, rules=)` 以参数形式拿。**绝不**搞模块全局 + 热重载——配置错就 fail loud，下次启动重读。

新工具 `config_show(section?)` 让 agent 在工作中查"我现在装了哪些规则？"——尤其在用户改了 yaml 之后，agent 用这个验证规则已生效。

新加 fuzz category（如 `ssti`）零代码改动：yaml 加 `fuzz_payloads.ssti: [...]` → `traffic_fuzz(payload_category="ssti")` 立刻可用。

### 3.16 文件系统 Prompt Pack（v0.3.1）

**问题**：MCP prompts 是给 LLM 看的"作战手册"，里面浓缩了多年实战的 SRC 战术。把这些写进 `tools.py` 等于和库一起公开发布——但运营者通常希望它们留在本地：私有 intel、客户特定情报、不轻易 push 到仓库。同时硬编码 prompt 也使得"加 / 改 / 替换 prompt = 改代码 + 重 build + 重启"，迭代极慢。

**解法**：把 prompts 从代码里完全剥离到 `prompts/` 目录。每个 `.md` 文件 = 一个 MCP prompt，按需配 `.py` 同名文件提供动态上下文。

```
prompts/
├── pentest_workflow.md  (frontmatter description/arguments + body)
├── pentest_workflow.py  (def context(session, **args) -> dict)
├── triage_note.md
└── triage_note.py
```

**为什么 `.md` 不是 `.yaml`**：prompt 主体是上百行 markdown，YAML 的 block scalar 写起来 OK 但**改起来痛苦**（缩进 / 引号 / 锚点全部手动）。markdown 自带语法高亮 / 折叠 / 预览，编辑体验完胜。frontmatter 处理元数据，body 维持原生 markdown。

**`{{ placeholder }}` 不和 f-string 冲突**：占位符用双大括号，loader 用正则做替换，不走 Python 字符串插值。

**加载顺序**：`AGENT_PROXY_PROMPTS_DIR` env → `<cwd>/prompts/` → `<repo_root>/prompts/`。三个都没找到 = 静默 no-op，零 prompt 注册，AgentProxy 正常运行。

**安全**：`.py` 同名文件会被 `import` 然后调用 `context()` — 这是完全代码执行。但因为 `prompts/` 是用户本地目录、内容用户自己写的（不从外部下载），等价于"用户编辑 settings.py"，可接受。`prompts/` 默认 `.gitignore` 排除避免误 commit。

**故障容错**：无效 YAML frontmatter → 警告日志后当作无 frontmatter 处理；`.py` 缺失 / 无 `context()` → 仅做静态渲染；`context()` 抛异常 → prompt 返回友好错误信息（包含异常文本和定位提示）而不是杀掉整个 server。

### 3.15 研判笔记系统（v0.3）

**问题**：agent 测完一条流量得出"没漏洞"或"有漏洞"的结论后，结论散落在对话历史里，下一轮新会话就丢。SRC 真实场景中"测过没漏洞"的记录和"找到漏洞"同等重要——避免重复测试、保留排除推理、补全报告时不漏接口。

**解法**：表 + 4 段式工具签名 + prompt 引导，不上模板引擎。

数据：`flow_notes` 表，一 flow_id 一条记录（PRIMARY KEY 强制），`note_add` 是 UPSERT 覆盖。verdict 三档枚举：

- `vulnerable` — 找到漏洞，conclusion 应指向证据 flow_id
- `not_vulnerable` — 测过、确认无问题，conclusion 应说覆盖了哪些角度
- `inconclusive` — 需要更多上下文（不同账号/payload/OOB），conclusion 应说欠缺什么

每段 1500 字符上限避免笔记冗长（4 段总共 ≤ 6KB）。

引导分三层（按力度递增）：

1. **Tool docstring 提示** — `traffic_fuzz` / `traffic_diff` 等研判型工具末尾加一句 "After concluding, call note_add"，0 token 成本，模型可忽略
2. **MCP prompt** — `triage_note(flow_id)` 拿到完整 4 步指引模板，agent 显式调用时收到结构化提示
3. **工具 schema** — `note_add` 5 个独立字段 + verdict 枚举强制结构，每个字段 description 说明该填什么。模型按工具签名能力最强，所以最关键的约束在这里

**为何不做自动 hook（每次 inspect 后强插）**：误伤"agent 还在探索阶段"的情况，且产生大量空洞笔记。

**集成点**：`evidence_bundle(flow_id)` 沿 link DAG 收集时，每个 flow 的 note 自动拼进 Markdown，4 段以 `*Scenario:* / *Sensitive fields:* / *Test steps:* / *Conclusion:*` 渲染。一次 `evidence_bundle` 就是包含完整推理链的报告材料。

## 4. 错误处理设计

1. **浏览器启动失败**：返回详细错误信息，包含缺失依赖提示
2. **代理端口冲突**：返回明确提示，建议使用其他端口
3. **Flow 不存在**：返回 "Flow not found" 而非异常
4. **JSON 解析失败**：返回 "Invalid JSON" 而非异常
5. **正则编译失败**：拦截规则添加时返回 False，不抛异常
6. **重放超时**：捕获超时异常，返回友好错误信息

## 5. 性能设计

1. **SQLite WAL 模式**：并发读写不阻塞
2. **流量去重**：同一 flow 的 request 和 response 通过 UPSERT 合并
3. **内存限制**：TrafficRecorder 不在内存中保留大量 flow 对象
4. **异步架构**：mitmproxy 和浏览器操作都是异步的
5. **按需加载**：流量详情和 body 内容按需查询，不在列表接口中返回

## 6. 扩展性设计

1. **新增 payload 类别**：在 `fuzz_endpoint()` 的 `payloads_map` 中添加即可
2. **新增拦截动作**：在 `TrafficInterceptor._apply_rules()` 中添加新的 action_type
3. **新增代码生成框架**：在 `generate_scraper_code()` 中添加新的 target_framework
4. **新增认证检测类型**：在 `detect_auth_patterns()` 中添加新的 auth_signals 条目
5. **新增 MCP 工具**：在 `tools/tools.py` 中添加新的 `@mcp.tool()` 函数
