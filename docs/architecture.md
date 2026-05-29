# AgentProxy 架构文档

## 1. 系统概述

AgentProxy 是一个面向 AI 智能体（Claude Code / Codex / Cursor 等）的 Web 调试代理系统，通过 MCP（Model Context Protocol）协议将浏览器自动化与 MITM 流量拦截能力统一暴露给智能体，使其能够像使用 Burp Suite / Yakit 一样进行 Web 应用安全测试和流量分析。

**核心创新点**：浏览器启动时自动配置代理指向 mitmproxy，实现"操作浏览器即自动抓包"的一体化体验，无需手动配置代理或证书。

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│              AI Agent (Claude Code / Codex)              │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              MCP Client                           │  │
│  │  通过 .mcp.json 配置，发现并调用 AgentProxy 工具   │  │
│  └───────────────────────┬───────────────────────────┘  │
└──────────────────────────┼──────────────────────────────┘
                           │ MCP Protocol (stdio/sse)
                           ▼
┌─────────────────────────────────────────────────────────┐
│              AgentProxy MCP Server                      │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Tool Registration Layer                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │  │ Session  │ │ Browser  │ │  MITM/Traffic    │  │  │
│  │  │ Tools    │ │ Tools    │ │  Tools           │  │  │
│  │  │ (7)      │ │ (19)     │ │  (27)            │  │  │
│  │  └──────────┘ └──────────┘ └──────────────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │  │ Intercept│ │ Scope    │ │  Workflow        │  │  │
│  │  │ Tools    │ │ Tools    │ │  Tools           │  │  │
│  │  │ (5)      │ │ (2)      │ │  (4)             │  │  │
│  │  └──────────┘ └──────────┘ └──────────────────┘  │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │                               │
│  ┌───────────────────────┴───────────────────────────┐  │
│  │           Session Manager (协调层)                 │  │
│  │  - 统一管理 Browser + MITM 生命周期               │  │
│  │  - 高级工作流编排                                  │  │
│  │  - 状态一致性保证                                  │  │
│  └───────┬───────────────────────┬───────────────────┘  │
│          │                       │                       │
│  ┌───────▼───────┐       ┌───────▼───────────────────┐  │
│  │   Browser     │       │   MITM Controller         │  │
│  │   Controller  │       │                           │  │
│  │               │       │  ┌─────────────────────┐  │  │
│  │  Playwright   │       │  │  Traffic Recorder   │  │  │
│  │  Python API   │       │  │  (mitmproxy addon)  │  │  │
│  │               │       │  │  +X-AgentProxy-Ctx  │  │  │
│  │               │       │  │   strip → label DB  │  │  │
│  │  - 多 Context │       │  └─────────────────────┘  │  │
│  │  - 页面导航   │       │  ┌─────────────────────┐  │  │
│  │  - 元素操作   │       │  │  Traffic Interceptor│  │  │
│  │  - JS执行     │       │  │  (mitmproxy addon)  │  │  │
│  │  - 截图       │       │  └─────────────────────┘  │  │
│  │  - Cookie管理 │       │  ┌─────────────────────┐  │  │
│  │  - 代理配置   │◄──────┼──│  Passive Scanner    │  │  │
│  │  - 多 profile │       │  │  (kind: finding /   │  │  │
│  │    storage    │       │  │   signal)           │  │  │
│  │    state持久化│       │  └─────────────────────┘  │  │
│  │  - 上下文重放 │       │  ┌─────────────────────┐  │  │
│  │  (冷热融合)   │       │  │  Param Extractor    │  │  │
│  └───────┬───────┘       │  │  (semantic tags)    │  │  │
│          │               │  └─────────────────────┘  │  │
│          │               │  ┌─────────────────────┐  │  │
│          │               │  │  Traffic DB         │  │  │
│          │               │  │  (SQLite: flows /   │  │  │
│          │               │  │   findings /        │  │  │
│          │               │  │   flow_tags /       │  │  │
│          │               │  │   flow_links /      │  │  │
│          │               │  │   flow_notes)       │  │  │
│          │               │  └─────────────────────┘  │  │
│          │               │  ┌─────────────────────┐  │  │
│          │               │  │  Scope Manager      │  │  │
│          │               │  └─────────────────────┘  │  │
│          │               │  ┌─────────────────────┐  │  │
│          │               │  │  Replay Engine      │  │  │
│          │               │  │  (curl_cffi +       │  │  │
│          │               │  │   storage_state)    │  │  │
│          │               │  └─────────────────────┘  │  │
│          │               └───────────────────────────┘  │
│          │                                               │
└──────────┼───────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                    Target Web Application                │
│                                                         │
│  浏览器通过代理访问 → mitmproxy 拦截所有流量            │
│  → 流量存入 SQLite → 智能体可查看/搜索/重放/模糊测试    │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流架构

```
浏览器请求流:
  Browser → proxy(127.0.0.1:8080) → mitmproxy → Target Server
                                              ↓
                                        TrafficRecorder
                                              ↓
                                        SQLite Database
                                              ↓
                                        MCP Tool 查询

智能体操作流:
  AI Agent → MCP Protocol → AgentProxy Server → Tool Handler
                                                    ↓
                                          SessionManager 协调
                                           ↓           ↓
                                    BrowserController  MitmController
                                           ↓           ↓
                                      Playwright    mitmproxy/curl_cffi
```

### 2.3 核心组件

#### 2.3.1 SessionManager（会话管理器）

**职责**：统一管理浏览器和 MITM 代理的生命周期，提供高级工作流编排。

**关键设计决策**：
- 浏览器启动时自动配置 `proxy={"server": "http://127.0.0.1:PORT"}`，确保所有流量经过 mitmproxy
- 浏览器启动参数包含 `--ignore-certificate-errors`，解决 HTTPS 证书问题
- 会话变量系统支持在重放时动态替换 `$variable` 占位符

#### 2.3.2 BrowserController（浏览器控制器）

**职责**：封装 Playwright Python API，提供页面操作能力。

**关键特性**：
- 自动配置代理，无需手动设置
- 支持 headless/headful 模式
- 支持 Cookie 管理、Header 注入、离线模式
- 支持无障碍树（Accessibility Tree）获取，便于智能体理解页面结构
- 支持自定义 JavaScript 执行

#### 2.3.3 MitmController（MITM 控制器）

**职责**：管理 mitmproxy 实例，提供流量捕获、拦截、重放、模糊测试能力。

**关键特性**：
- 使用 mitmproxy 的 DumpMaster 作为代理核心
- TrafficRecorder 作为 mitmproxy addon，实时将流量存入 SQLite
- TrafficInterceptor 作为 mitmproxy addon，实时应用拦截规则
- 使用 curl_cffi 进行隐身重放（模拟 Chrome 120 指纹）
- 支持多种模糊测试 payload：SQLi、XSS、路径遍历、SSRF、命令注入

#### 2.3.4 TrafficDB（流量数据库）

**职责**：基于 SQLite 的流量持久化存储 + Findings 表。

**关键特性**：
- 自动建表和索引（timestamp, url, method, findings.flow_id, findings.severity）
- 支持 UPSERT 操作，同一 flow 更新时覆盖
- 支持按域名、方法、关键词搜索
- 支持轻量级查询（lightweight mode）减少内存占用
- 支持批量查询和字段选择
- WAL + `synchronous=NORMAL` 提升并发读写
- Body 大小上限 256KB，超过截断并标记 `body_truncated`
- 二进制 Content-Type（image/* / video/* / font/* / application/octet-stream / pdf / zip）跳过 body 存储，标记 `body_omitted="binary"`
- `findings` 独立表，与 flows 通过 flow_id 关联，唯一约束 `(flow_id, rule_id, evidence)` 自动去重

#### 2.3.5 PassiveScanner（被动扫描器）— v0.2 新增

**职责**：每条 response 进入时同步跑一组高精度规则，把"值得看的"线索写入 findings 表。

**10 条规则**（v0.3 起按 kind 分两类）：

`kind=finding` (高置信，默认 traffic_findings 显示)：
1. `aws_access_key` (high) — 响应体含 `AKIA[0-9A-Z]{16}`
2. `private_key_block` (high) — 响应体含 `-----BEGIN ... PRIVATE KEY-----`
3. `jwt_in_body` (medium) — 响应体含 JWT 三段格式
4. `sqli_db_error` (high) — SQLSTATE / ORA-XXXX / MySQL syntax / PostgreSQL ERROR / SQLite / SqlException
5. `stacktrace` (medium) — Python Traceback / Java `at xxx(...)` / Spring Whitelabel
6. `cors_misconfig` (high) — `ACAO: *|<reflected origin>` 同时 `ACAC: true`
7. `debug_endpoint` (high) — `/actuator` `/debug` `/swagger` `/api-docs` `/.git/` `/.env` `/phpinfo` 等

`kind=signal` (低置信，仅在 traffic_findings(kind="signal") 显示)：
8. `cookie_insecure` (low) — HTTPS Set-Cookie 缺 `Secure` 或 `HttpOnly`
9. `missing_csp` (info) — HTML 响应缺 `Content-Security-Policy`
10. `sensitive_param` (medium) — query/json/form 中含 `redirect|url|next|callback|file|path|cmd|template|include` 等高敏参数名

设计原则：宁可漏报、不要误报。signal/finding 分层避免低价值规则刷屏。

#### 2.3.6 BrowserController 多 Context（v0.3 新增）

`BrowserController` 维护一个 `contexts: Dict[str, BrowserContext]`，对应 Playwright 的多 BrowserContext 能力。每个 context 完全隔离（独立 cookie/localStorage），但共享同一 Browser 进程和同一代理端口。

- `_context` / `_page` 是 property，指向 `self.contexts[self.active]`，所有现有方法（navigate / click / fill 等）零改动透明工作
- `start()` 默认创建 `default` context（如果有 `<profile_dir>/default_state.json` 自动恢复）
- `create_context(name, from_profile=True)` 在同一 Browser 上加 context；同名 storage_state 存在则恢复
- `use_context(name)` 切换 active；后续 browser_* 工具操作新 context
- 每个 context 自动 `set_extra_http_headers({"X-AgentProxy-Context": name})`

`TrafficRecorder` 在 `request()` 阶段把 `X-AgentProxy-Context` 头从 flow 上剥掉（防止泄露给目标），值写入 `flow.metadata["profile_label"]`，最终持久化到 `flows.profile_label` 列。

`replay_via_browser` 的冷热路由：
1. 命中活 context → 直接 `context.request.fetch()`
2. 活 context 不存在但磁盘有 `<profile_dir>/<name>_state.json` → `_create_named_context(name, from_profile=True)` 唤醒
3. 浏览器停止但磁盘有 storage_state → `replay_with_storage_state` 用 curl_cffi + cookies 发包
4. 都没有 → 默认身份 curl_cffi 重放

#### 2.3.7 Param Extractor（v0.3 新增）

`core/param_extractor.py` 提供 `extract_params(flow_detail)`，返回 path/query/json/form/headers/cookies 六类参数列表，每个参数附 11 类语义标签。

`SEMANTIC_DICT` 共 11 类：identity_param / object_id_param / privilege_param / money_param / ssrf_candidate / object_storage / redirect_candidate / file_param / sql_candidate / expression_candidate / command_candidate / state_token。词表来源于真实 SRC 报告，不做泛化。

匹配规则：参数名 lowercase 后按 `[-_.]` 分词，每个 token 与字典精确比对；同时检查首尾 prefix/suffix。

JSON 参数支持嵌套（key 用 `.` 拼路径）；Cookie 仅暴露 name 列表不暴露 value；Authorization header 标 Bearer/JWT/Basic 类型不输出原值。

#### 2.3.8 Tag / Link / Chain（v0.3 新增）

两张极小关系表：

```sql
flow_tags(flow_id, tag, created_at)   -- 静态语义别名
flow_links(source_id, target_id, relation, created_at)   -- 动态数据流向
```

`tag` 解决"叫什么"（agent 用稳定别名找入口流量），`link` 解决"怎么连"（多步骤 DAG）。`get_chain(flow_id, depth)` BFS 上下游收集子图，是 `evidence_bundle` 的输入。

#### 2.3.9 RuleConfig — YAML 规则包（v0.3 新增）

所有"内容型"可调数据（语义参数词表 / 被动扫描规则 / fuzz payload）从代码里抽出，集中到 `src/agent_proxy/config/defaults.yaml`。

```
启动时 RuleConfig 加载顺序（后者覆盖前者）：
  1. 包内 defaults.yaml（始终加载）
  2. 用户 override：--config CLI > AGENT_PROXY_CONFIG env > <cwd>/agent_proxy.yaml
```

合并语义：dict 递归深合并；list 在叶节点整体替换（用户想动 body_rules 必须列全集）。无效正则被记日志后跳过，剩余规则继续生效——避免一条坏规则全盘失败。

`PassiveScanner` / `extract_params` / `MitmController.fuzz_endpoint` 都从注入的 `RuleConfig` 读数据，`SessionManager` 在 `__init__` 阶段一次加载、持有一份给所有下游。`config_show` MCP 工具可让 agent 实时看到当前生效的规则集合。

新增 fuzz category（如 `ssti / xxe / nosql`）只需在 yaml 加一段 `fuzz_payloads.<name>: [...]`，`traffic_fuzz(payload_category="<name>")` 立即可用，0 代码改动。

#### 2.3.10 Triage Notes（v0.3 新增）

`flow_notes` 表（一 flow 一笔记）持久化 agent 对每条流量的研判：

```sql
flow_notes(flow_id PRIMARY KEY, verdict, scenario, sensitive_fields,
           test_steps, conclusion, created_at, updated_at)
```

`verdict` 三档枚举：`vulnerable` / `not_vulnerable` / `inconclusive`。每段最多 1500 字符避免笔记膨胀消耗 agent 上下文。重复 `note_add` 是 UPSERT（覆盖内容，保留 created_at）。

笔记会被 `evidence_bundle` 自动嵌入 Markdown 输出 —— agent 只要在研判完一条流量后调一次 `note_add`，整段攻击链最后导出时就带着完整推理。

引导机制（不强制）：`triage_note(flow_id)` MCP prompt 提供 4 步指引模板；`traffic_fuzz` / `traffic_diff` 等"研判型"工具的 docstring 末尾提示完成后调用 `note_add`。

### 2.4 MCP 工具分层

| 层级 | 工具类别 | 工具数量 | 说明 |
|------|----------|----------|------|
| L1 | Session 管理 | 8 | 会话启停、状态查询、profile 保存、create/use/list context、config_show |
| L2 | Browser 操作 | 19 | 页面导航、元素操作、Cookie/Header、console_logs |
| L3 | Traffic 分析 | 30 | 流量分层 / 站点树 / Findings(signal/finding) / Params 语义 / Replay 闭环 / Diff / 反射 Fuzz / Tag / Link / Chain / Evidence Bundle / Notes (4 段式研判) / 代码生成 |
| L4 | Intercept 拦截 | 5 | 拦截规则管理、全局Header注入 |
| L5 | Scope 作用域 | 2 | 域名过滤 |
| L6 | Workflow 工作流 | 4 | 高级组合操作 |

此外暴露 1 个 MCP prompt：`triage_note(flow_id)` — 4 段式研判检查清单。

## 3. 技术选型

| 组件 | 技术选择 | 选择理由 |
|------|----------|----------|
| MCP 框架 | FastMCP (Python) | 官方 Python SDK，与 mitmproxy 同语言 |
| 浏览器自动化 | Playwright Python | 跨浏览器支持，原生代理配置 |
| MITM 代理 | mitmproxy | 成熟的 HTTPS 中间人代理，Python 原生 |
| 流量存储 | SQLite | 轻量级，无需额外服务，适合单机场景 |
| 隐身重放 | curl_cffi | 模拟浏览器 TLS 指纹，绕过基础反爬 |
| 数据提取 | jsonpath-ng + BeautifulSoup | JSON 和 HTML 两种响应格式的数据提取 |
| 数据模型 | Pydantic v2 | 类型安全，自动验证，与 FastMCP 兼容 |
| 规则配置 | PyYAML | 词表/正则/payload 抽到 yaml；写正则不需要双层转义 |

## 4. 与现有项目的关系

### 4.1 继承关系

| 现有项目 | 继承内容 | 改进点 |
|----------|----------|--------|
| playwright-mcp | 浏览器操作工具设计思路 | 用 Playwright Python 替代 Node.js，原生代理配置 |
| mitmproxy-mcp | MITM 核心、流量存储、重放、模糊测试 | 增加浏览器集成，统一会话管理 |
| playwright-min-network-mcp | CDP 网络监控思路 | 用 mitmproxy 替代 CDP 监控，获得完整 MITM 能力 |
| agent-browser | 网络拦截和域名过滤思路 | 用 Python 替代 Rust，降低集成复杂度 |

### 4.2 关键差异化

1. **一体化设计**：现有项目都是"浏览器"或"抓包"单方面能力，AgentProxy 是首个将两者统一在一个 MCP 服务器中的方案
2. **零配置代理**：浏览器自动走 MITM 代理，无需手动配置
3. **攻防导向**：内置 SQLi/XSS/SSRF/路径遍历/命令注入模糊测试，不是简单的"看流量"
4. **智能体友好**：上下文管理（body 预览限制、字段选择）、会话变量系统、高级工作流工具

## 5. 部署架构

### 5.1 单机部署（推荐）

```
┌─────────────────────────────────────────┐
│            开发者工作站                   │
│                                         │
│  Claude Code / Codex                    │
│       ↓ (.mcp.json)                     │
│  AgentProxy MCP Server (stdio)          │
│       ├── mitmproxy (port 8080)         │
│       ├── Playwright Browser            │
│       └── SQLite (agent_proxy_traffic.db)│
└─────────────────────────────────────────┘
```

### 5.2 Docker 部署

```dockerfile
FROM python:3.11-slim
RUN pip install agent-proxy && playwright install chromium --with-deps
ENTRYPOINT ["python", "-m", "agent_proxy.main"]
```

### 5.3 SSE 远程部署

```json
{
  "mcpServers": {
    "agent-proxy": {
      "url": "http://remote-host:3000/sse"
    }
  }
}
```

## 6. 安全考量

1. **证书处理**：浏览器启动时自动忽略 HTTPS 证书错误，仅用于安全测试场景
2. **代理隔离**：默认监听 127.0.0.1，不暴露到外网
3. **作用域控制**：支持域名白名单，限制抓包范围
4. **数据安全**：流量数据存储在本地 SQLite，不上传任何外部服务
5. **会话变量**：敏感信息（Token、Cookie）通过会话变量管理，不直接暴露在 MCP 上下文中
