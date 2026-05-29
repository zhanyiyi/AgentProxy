# AgentProxy PRD - 产品需求文档

## 1. 产品概述

### 1.1 产品名称
AgentProxy - AI-Agent-Native Web Debug Proxy

### 1.2 产品定位
面向 AI 智能体（Claude Code / Codex / Cursor 等）的一体化 Web 调试代理，将浏览器自动化与 MITM 流量拦截能力通过 MCP 协议统一暴露，使智能体能像使用 Burp Suite / Yakit 一样进行 Web 应用安全测试和流量分析。

### 1.3 目标用户
- 安全研究员：使用 AI 智能体辅助 Web 渗透测试
- 开发者：使用 AI 智能体调试 Web 应用 API
- 自动化测试工程师：使用 AI 智能体进行 DAST（动态应用安全测试）

### 1.4 核心价值主张
**"让 AI 智能体拥有 Burp 级别的 Web 调试能力"**

现有方案的痛点：
1. Playwright MCP 只能"看流量 + mock"，不能 MITM 抓包/改包/重放
2. mitmproxy-mcp 能抓包但不能控制浏览器
3. 没有一个项目能同时做到"浏览器操作 + 全功能 MITM + 智能体原生"

AgentProxy 的解决方案：
1. 浏览器自动走 MITM 代理，操作即抓包
2. 64 个 MCP 工具覆盖完整攻防工作流
3. 智能体友好的上下文管理和数据格式（流量分层 / 站点树 / Findings 被动扫描 / 语义参数 / 双身份 / 链路证据）

## 2. 功能需求

### 2.1 P0 - 核心功能（必须实现）

#### FR-001: 会话管理
- 启动/停止一体化会话（MITM 代理 + 浏览器）
- 浏览器自动配置代理指向 MITM
- 会话状态查询

#### FR-002: 浏览器自动化
- 页面导航（支持 wait_until 参数）
- 元素操作（点击、填充、选择、按键）
- 内容获取（文本、HTML、截图）
- JavaScript 执行
- Cookie 管理
- 自定义 HTTP Header
- 离线模式
- 无障碍树获取

#### FR-003: 流量捕获与查看
- 自动捕获所有浏览器流量（HTTP + HTTPS）
- 流量列表（摘要信息）
- 流量详情（完整请求/响应）
- 流量搜索（域名、方法、关键词）
- 流量清除

#### FR-004: 请求重放
- 基于捕获的 flow 重放请求
- 支持修改方法、Header、Body
- 使用 curl_cffi 模拟浏览器指纹
- 会话变量系统（动态替换 Token 等）

#### FR-005: 流量拦截
- 添加/移除拦截规则
- 三种动作：注入 Header、替换 Body、阻断请求
- 支持请求和响应两个阶段
- 全局 Header 注入

#### FR-006: 模糊测试
- 5 种 payload 类别：SQLi、XSS、路径遍历、SSRF、命令注入
- 支持查询参数和 JSON Body 两种参数位置
- 异常检测：5xx、状态码偏差、响应体长度偏差

### 2.2 P1 - 重要功能（应该实现）

#### FR-007: 认证模式检测
- 自动识别 Bearer Token、JWT、API Key、OAuth2、Session Cookie、CSRF Token、Basic Auth
- 返回检测到的认证类型和关联 flow

#### FR-008: API 端点发现
- 从捕获流量中聚类 API 端点
- 自动归一化路径参数（数字→{id}、UUID→{uuid}）
- 统计请求次数、状态码分布、Content-Type

#### FR-009: OpenAPI 规范生成
- 从捕获流量自动生成 OpenAPI v3 规范
- 支持域名过滤

#### FR-010: 代码生成
- 从捕获流量生成可执行的爬虫/自动化代码
- 支持 curl_cffi 和 Playwright 两种框架

#### FR-011: 数据提取
- JSONPath 从 JSON 响应中提取数据
- CSS Selector 从 HTML 响应中提取数据

#### FR-012: 作用域管理
- 域名白名单过滤
- 忽略静态资源扩展名
- 忽略 OPTIONS 方法

### 2.3 P2 - 增强功能（可以实现）

#### FR-013: 高级工作流
- browse_and_capture：导航 + 自动抓包 + 后续操作
- api_discover：一键 API 发现
- security_scan：多类别安全扫描
- export_session：会话数据导出

#### FR-014: HAR 文件导入
- 导入 HAR/mitmproxy flow 文件
- 支持域名过滤和追加模式

#### FR-015: 流量对比
- 对比两次请求的差异
- 检测响应变化

### 2.4 P0 v0.2 - 信噪比与线索密度（已实现）

#### FR-016: Findings 被动扫描
- 每条流量进入时自动跑 8 条精选规则，命中写入独立 findings 表
- 规则覆盖：AWS Key / Private Key / JWT 泄露、SQL 错误指纹、栈跟踪、CORS 误配、调试端点、Cookie 缺 Secure/HttpOnly、缺 CSP、敏感参数名（redirect/url/file/cmd 等）
- 工具：`traffic_findings` / `traffic_findings_stats`
- 设计：高精度优先、低召回为辅，避免 agent 上下文被噪音吞掉

#### FR-017: 流量分层抽象
- `traffic_list` 默认仅返回 `id/method/url/status_code/size`，可选 `with_findings` 附 finding 计数
- `traffic_inspect(level=)` 三档：`meta`（仅 headers）/`preview`（body 截断 2KB）/`full`（256KB 上限完整 body）
- agent 先看 list/findings 决定是否下钻，避免一次性拉满上下文

#### FR-018: 站点树 / Site Map
- `site_map(domain?)` 按 host 聚合 endpoint，每个 endpoint 含 method、path、param 集合、status 分布、`auth_required`、findings 计数、sample_flow_id
- 扁平结构，agent 一次拿到目标"攻击面地图"

#### FR-019: 浏览器状态保持
- `session_start(profile_dir=...)` 启动时自动 restore `storage_state.json`，停止时自动 save
- `session_save_profile(name?)` 工具支持登录后立即快照（v0.3 扩展支持多 context）
- 解决"每次启动都要重登录"的痛点；CDP 模式由用户自管 user-data-dir 不重复实现

#### FR-020: 浏览器上下文重放
- `traffic_replay_via_browser` 走 `context.request.fetch()`，自动复用活的 cookie / 刷新 token / CSRF
- 解决"重放总 401"问题；浏览器未启动时自动降级到 curl_cffi（v0.3 加冷热路由 + 多身份）

#### FR-021: 流量对比（Diff）
- `traffic_diff(flow_a, flow_b)` 输出 status/size 差异 + JSON 字段级 diff（added/removed/changed 路径）或 text 行级 diff
- 用于 IDOR、越权、参数污染验证

#### FR-022: Fuzz 反射检测
- `traffic_fuzz` 现在在响应中搜索 payload 是否原样回显，命中标 `reflected: true`
- XSS / SSTI 候选信号比长度差异精确得多

### 2.5 P0 v0.3 - 闭环、双身份、链路证据（已实现）

#### FR-023: P0 闭环修复
- 修复 `body_preview` 字段残留（fuzz baseline / replay fallback / extract / codegen 全部统一到 `body`，并保留 `body_preview` 别名兼容下游）
- 注册 `browser_get_console_logs` MCP 工具（v0.2 已收集但未暴露）
- `--disable-web-security` 改默认关，移到 `unsafe_disable_web_security` 显式开关，CORS 漏洞验证保真
- replay 闭环：`traffic_replay` / `traffic_replay_via_browser` 返回 `new_flow_id`，agent 可直接 chain 进 `traffic_diff` / `evidence_bundle`

#### FR-024: 双身份冷热融合
- `BrowserController` 多 context 字典化，一个 Browser 进程管理任意命名 context（默认创建 `default`）
- `session_create_context(name)` / `session_use_context(name)` / `session_list_contexts()` 三件套
- 每个 context 自动注入 `X-AgentProxy-Context: <name>` 头；MITM 层在转发前剥头并写入 `flows.profile_label` 列
- `session_save_profile(name)` 多 profile 持久化到 `<profile_dir>/<name>_state.json`
- `traffic_replay_via_browser(context=)` 冷热路由：活 context > 磁盘 storage_state 唤醒 > curl_cffi+cookies fallback > 默认身份重放
- 解决 IDOR / 水平越权 / 垂直越权"无法做双身份对比"的核心痛点

#### FR-025: Trace Link + Tag
- `flow_tags` / `flow_links` 两张极小关系表，覆盖多步骤 DAG 的"叫什么"和"怎么连"
- 5 个工具：`traffic_tag` / `traffic_untag` / `traffic_find_by_tag` / `traffic_link` / `traffic_chain(depth=)`
- 解决存储型 SSRF / 二阶段越权 / OAuth ticket 这类多步骤漏洞 agent 在长对话里靠记忆漂移、报告丢证据的痛点

#### FR-026: 语义参数地图
- `traffic_params(flow_id)` 提取 path/query/json/form/headers/cookies 的可变参数名
- 每个参数附 11 类语义标签：identity_param / object_id_param / privilege_param / money_param / ssrf_candidate / object_storage / redirect_candidate / file_param / sql_candidate / expression_candidate / command_candidate / state_token
- agent 不需要 inspect 整个 body，一眼看到攻击面
- Cookie 仅暴露 name 列表不暴露 value；Authorization 标 Bearer/JWT/Basic 但不输出原值

#### FR-027: Findings vs Signals 分层
- findings 表加 `kind` 列；高置信问题为 `finding`，低置信线索为 `signal`
- 现有 10 条规则按精度重新分类：missing_csp / sensitive_param / cookie_insecure 退为 signal
- `traffic_findings(kind="finding"|"signal"|"all")` 默认只查 finding，避免低价值线索刷屏
- `traffic_findings_stats` 拆分 findings / signals 计数

#### FR-028: Evidence Bundle
- `evidence_bundle(flow_id, depth=3)` 沿 link DAG 收集相关 flow，渲染 Markdown 证据链
- 含每条 flow 的 method/url/status/profile_label/tags/findings/body 预览/curl 复现
- 一键产出 SRC 报告材料

#### FR-029: YAML 规则包配置
- 所有内容型可调数据抽到包内 `src/agent_proxy/config/defaults.yaml`：11 类语义参数词表 / interesting_headers / 被动扫描 debug_paths / sensitive_param_names / body_rules（id/severity/category/kind/regex/flags）/ fuzz_payloads
- 用户可通过 `--config <path>` 命令行 flag、`AGENT_PROXY_CONFIG` 环境变量、或 `<cwd>/agent_proxy.yaml` 提供 override；优先级递减
- 深合并：dict 递归合并；list 整体替换（避免"加 1 条要列全集"和"想替换却被 append"两种困惑）
- 无效 regex 被跳过 + 警告日志，其他规则继续生效
- 新增 `config_show(section?)` MCP 工具：返回当前生效的合并后配置（包含所有 source_paths 的来源）
- 用户加新 fuzz category（如 `ssti / xxe / nosql`）后，`traffic_fuzz(payload_category="ssti")` 立刻可用，不需要改代码

#### FR-030: 研判笔记系统
- 新增 `flow_notes` 表（一 flow 一笔记，重复 `note_add` 覆盖）
- 4 段式结构 + verdict 三档枚举（vulnerable / not_vulnerable / inconclusive），每段 1500 字符上限避免上下文浪费：
  1. **scenario** — 这是什么场景，可能出什么问题，流量中有什么
  2. **sensitive_fields** — 可测试的敏感字段（含语义标签）
  3. **test_steps** — 测了什么、结果如何
  4. **conclusion** — 研判结论 + 证据 / 为何无漏洞 / 是否欠缺考虑
- 3 个工具：`note_add` / `note_get` / `note_remove`
- `evidence_bundle` 自动把笔记拼进 Markdown 报告（沿 link 拓扑收集时一并导出）
- MCP prompt `triage_note(flow_id)` 提供 4 步指引模板（v0.3.1 起从 `prompts/` 目录加载，不再硬编码到代码）
- 关键工具 docstring（fuzz / diff）末尾提示"完成研判后调用 note_add"，引导但不强制

#### FR-031: 文件系统 Prompt Pack
- 新增 `prompts/` 目录（`.gitignore` 排除），AgentProxy 启动时自动扫描注册为 MCP prompts
- 每个 prompt 一个 `.md` 文件（YAML front-matter 元数据 + Markdown body）+ 可选同名 `.py` 提供动态上下文（`context(session, **args) -> dict`）
- `{{ placeholder }}` 占位符由 `.py` 的 context() 或前端参数填充，不冲突 f-string
- 解析顺序：`AGENT_PROXY_PROMPTS_DIR` 环境变量 → `<cwd>/prompts/` → `<repo_root>/prompts/`
- 目录缺失或为空时静默跳过，零 prompt 注册，AgentProxy 正常运行
- 设计目的：将"操作员私有 SRC 战术 / 客制化 prompt"从打包代码中剥离 — pip install 不带 prompts，git push 不带 prompts，全部本地 intel 化
- 内置自带的 prompts（pentest_workflow / triage_note）从 tools.py 内嵌实现迁移到此机制下

## 3. 非功能需求

### 3.1 性能
- NFR-001: MITM 代理启动时间 < 3 秒
- NFR-002: 浏览器启动时间 < 5 秒
- NFR-003: 流量查询响应时间 < 100ms（1000 条以内）
- NFR-004: 模糊测试 5 个 payload < 10 秒

### 3.2 可靠性
- NFR-005: 代理崩溃不影响浏览器（浏览器显示连接错误）
- NFR-006: 浏览器崩溃不影响代理（代理继续捕获其他来源流量）
- NFR-007: SQLite 数据库损坏时自动重建

### 3.3 安全性
- NFR-008: 默认监听 127.0.0.1，不暴露到外网
- NFR-009: HTTPS 证书错误仅在安全测试场景下忽略
- NFR-010: 流量数据仅存储在本地
- NFR-011: 会话变量不写入日志

### 3.4 兼容性
- NFR-012: 支持 Python 3.10+
- NFR-013: 支持 MCP stdio 和 SSE 两种传输
- NFR-014: 兼容 Claude Code、Codex、Cursor 等 MCP 客户端
- NFR-015: 支持 Linux、macOS、Windows

### 3.5 可用性
- NFR-016: 零配置启动（默认参数即可工作）
- NFR-017: 一行命令安装（pip install + playwright install）
- NFR-018: MCP 配置一行 JSON

## 4. 用户场景

### 4.1 场景一：Web 渗透测试

**用户**：安全研究员 Alice
**目标**：使用 Claude Code 对目标 Web 应用进行渗透测试

**工作流**：
1. Alice 在 `.mcp.json` 中配置 AgentProxy
2. 告诉 Claude Code："对 http://target-app.com 进行安全测试"
3. Claude Code 调用 `session_start` 启动会话
4. Claude Code 调用 `browser_navigate` 打开目标
5. Claude Code 调用 `traffic_list` 查看所有请求
6. Claude Code 调用 `traffic_auth_detect` 检测认证模式
7. Claude Code 调用 `traffic_api_patterns` 发现 API 端点
8. Claude Code 对每个端点调用 `traffic_fuzz` 进行模糊测试
9. Claude Code 调用 `traffic_replay` 验证发现的漏洞
10. Claude Code 调用 `traffic_generate_code` 生成 PoC 脚本
11. Alice 获得完整的安全测试报告和 PoC

### 4.2 场景二：API 调试

**用户**：开发者 Bob
**目标**：调试前端应用与后端 API 的交互

**工作流**：
1. Bob 启动 AgentProxy 会话
2. 在浏览器中操作前端应用
3. 所有 API 请求自动被捕获
4. Bob 让 Claude Code 分析特定 API 的请求/响应
5. Claude Code 调用 `traffic_inspect` 查看详情
6. Claude Code 调用 `traffic_replay` 修改参数重放
7. Claude Code 调用 `traffic_openapi` 生成 API 文档

### 4.3 场景三：自动化安全扫描

**用户**：安全团队
**目标**：CI/CD 流水线中自动扫描 Web 应用

**工作流**：
1. CI 脚本启动 AgentProxy
2. 自动化脚本驱动浏览器遍历应用
3. AgentProxy 捕获所有流量
4. 对每个 API 端点自动运行模糊测试
5. 生成安全扫描报告

## 5. 竞品对比

| 功能 | Burp Suite | Yakit | Playwright MCP | mitmproxy-mcp | AgentProxy |
|------|-----------|-------|----------------|---------------|------------|
| 浏览器操作 | ❌ (需外部) | ❌ (需外部) | ✅ | ❌ | ✅ |
| HTTPS 抓包 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 请求重放 | ✅ | ✅ | ❌ | ✅ | ✅ |
| 浏览器上下文重放 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 请求修改 | ✅ | ✅ | 有限 | ✅ | ✅ |
| 模糊测试 | ✅ (Pro) | ✅ | ❌ | ✅ (基础) | ✅ |
| Passive Scanner | ✅ (Pro) | 部分 | ❌ | ❌ | ✅ |
| 站点树 / Site Map | ✅ | ✅ | ❌ | ❌ | ✅ |
| 流量分层抽象 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 登录态持久化 | 半自动 | 半自动 | 半自动 | ❌ | ✅ (storage_state) |
| 认证检测 | ❌ | ❌ | ❌ | ✅ | ✅ |
| API 发现 | ❌ | ❌ | ❌ | ✅ | ✅ |
| OpenAPI 生成 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 代码生成 | ❌ | ✅ | ❌ | ✅ | ✅ |
| AI 智能体集成 | ❌ | ❌ | ✅ | ✅ | ✅ |
| 浏览器+抓包一体化 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 隐身重放 | ❌ | ✅ | ❌ | ✅ | ✅ |

## 6. 里程碑

### M1 - MVP（v0.1.0）
- ✅ 会话管理（MITM + 浏览器一体化）
- ✅ 浏览器自动化（18 个工具）
- ✅ 流量捕获/查看/搜索
- ✅ 请求重放（curl_cffi 隐身）
- ✅ 流量拦截（Header 注入、Body 替换、请求阻断）
- ✅ 模糊测试（5 种 payload）
- ✅ 认证检测
- ✅ API 发现 + OpenAPI 生成
- ✅ 代码生成
- ✅ 作用域管理
- ✅ 高级工作流

### M2 - 信噪比版（v0.2.0）
- ✅ Findings 被动扫描（8 条精选规则 + 独立 findings 表）
- ✅ 流量分层抽象（traffic_list 减法 + traffic_inspect level）
- ✅ 站点树（site_map 按 host 聚合）
- ✅ 浏览器登录态持久化（storage_state dump/restore）
- ✅ 浏览器上下文重放（traffic_replay_via_browser）
- ✅ 流量对比（traffic_diff JSON 字段级 + 文本行级）
- ✅ Fuzz 反射检测（payload 回显标记）
- ✅ ScopeManager 完整过滤（修复 v0.1 静态资源 / OPTIONS 漏过滤）
- ✅ DB 优化（WAL / 256KB body 上限 / 二进制内容跳过 / findings 索引）
- ✅ 修复 5 处 v0.1 bug（console_logs / extract var 用 full body / payload_categories 类型 / 二进制 body 处理）

### M3 - 闭环、双身份、链路证据（当前 v0.3.0）
- ✅ A. P0 闭环修复（body_preview / console_logs 注册 / disable-web-security 显式化 / replay 返回 new_flow_id）
- ✅ B. 双身份冷热融合（BrowserContext 字典 + storage_state 多文件 + 冷热路由）
- ✅ C. Trace Link + Tag（多步骤 DAG / IDOR / 越权 / 存储型 SSRF）
- ✅ D. 语义参数地图（traffic_params + 11 类语义标签）
- ✅ E. Findings vs Signals 分层（kind 列 / 默认只查 finding）
- ✅ F. Evidence Bundle（沿 link 拓扑生成 Markdown 报告）
- ✅ G. YAML 规则包（defaults.yaml + 用户 override / config_show 工具）
- ✅ H. 研判笔记系统（flow_notes 4 段式 / triage_note prompt / evidence_bundle 集成）

### 后续路线
- WebSocket / SSE 流量捕获
- 参数发现（Param Mining，类似 Burp Pro）
- HAR 文件导入/导出
- 自定义 payload 字典 / 自定义 finding 规则
- traffic_replay_mutate 声明式参数变异（json.x / query.y / header.z）

## 7. 成功指标

1. **功能完整性**：68 个 MCP 工具 + 1 个 prompt 全部可用
2. **测试覆盖**：14 + 16 + 8 + 20 + 11 + 10 项烟雾测试全部通过（基础 / 安全 / v0.2 / v0.3 / config / notes）
3. **端到端验证**：完整的渗透测试场景可走通（findings → site_map → traffic_params → replay_via_browser(victim) → diff → tag/link → note_add → evidence_bundle）
4. **上下文效率**：traffic_list 单条 < 200 字节；traffic_inspect 三档可选；traffic_params 不读 body 即可看攻击面；笔记单段 1500 字符上限
5. **启动时间**：会话启动 < 8 秒（代理 + 浏览器）
6. **信噪比**：scope filter 默认过滤静态资源/OPTIONS；Findings 仅命中高精度规则；signals 单独通道避免刷屏
7. **闭环**：所有 replay 返回 new_flow_id；evidence bundle 沿 link 拓扑收集 + 嵌入笔记
8. **可扩展**：所有词表/规则/payload 抽到 YAML，加规则 = 改 yaml + 重启，0 代码改动
9. **可复盘**：每个研判结果（含"测过没漏洞"）都强制四段式记录，agent 跨会话不丢失推理
