# AgentProxy 实战测试报告 — www.baidu.com

- **测试时间**：2026-05-22 01:49 (UTC+8)
- **测试目标**：https://www.baidu.com（公开站点，仅做被动抓包与无害重放，未触发任何主动攻击 payload）
- **代理**：headless Playwright + mitmproxy on `127.0.0.1:8083`
- **profile_dir**：`/tmp/agentproxy/baidu_test`

> 备注：用户原话 "bdidu" 应为 baidu 笔误，已按 www.baidu.com 执行。

---

## 1. 测试范围与本轮关注点

本轮重点验证最近两次提交（`ff73331` 被动扫描 + 流量分诊、`46c0308` README 重构）落地的新能力，以及未提交的本地改动（双浏览器上下文、Tag/Link/Chain、evidence_bundle、param_extractor 等）是否达到 README 宣传的能力。

| 能力 | 工具 | 是否达标 |
| --- | --- | --- |
| 会话启动 + profile_dir | `session_start` | ✅ |
| 浏览器抓包 | `browser_navigate` / `_fill` / `_click` / `_wait_for` | ✅ |
| 分层抓包（meta/preview/full） | `traffic_list` + `traffic_inspect` | ✅ |
| 站点地图聚合 | `site_map` | ✅ |
| 参数语义图 | `traffic_params` | ✅（部分类目仍可加强） |
| 被动扫描 finding/signal 分流 | `traffic_findings*` | ✅ |
| Tag + Link + Chain 三件套 | `traffic_tag` / `_link` / `_chain` / `_find_by_tag` | ✅ |
| 证据包 Markdown 输出 | `evidence_bundle` | ✅ |
| 双浏览器上下文 | `session_create_context` / `_use_context` / `_list_contexts` | ✅ |
| 跨身份重放 | `traffic_replay_via_browser(context="victim")` | ✅ |
| 跨身份对比 | `traffic_diff` | ✅ |
| Profile 持久化 | `session_save_profile` | ✅（仅手动保存的会落盘，见后文） |

---

## 2. 关键操作与证据

### 2.1 启动会话并访问 baidu

```
session_start(proxy_port=8083, headless=true, profile_dir="/tmp/agentproxy/baidu_test")
→ proxy 8083 OK，browser OK，contexts=["default"]
browser_navigate("https://www.baidu.com")
→ 200, title="百度一下，你就知道"
browser_fill("#kw", "agentproxy mcp") + browser_click("#su")
→ 进入 /s 搜索结果页
```

### 2.2 分层抓包成本对比（同一 flow，3 个 level）

`9a8d4c68-…`（搜索结果页，837 KB）：

| level | 含 body | 实测响应大小 | 适用场景 |
| --- | --- | --- | --- |
| `meta` | ❌ | 仅 headers + curl_command（~3 KB） | 快速扫一眼 attack surface |
| `preview` | ✅ 截断（默认 ~2 KB） | 多 ~4 KB body 片段 | 大多数判断 |
| `full` | ✅ 全文 | 837 KB | 必须检索内容时再上 |

分层效果符合 README 设计意图：在 8 条流量里只对 1 条调用 `full`，其它走 `meta`，agent context 占用大幅压低。

### 2.3 站点地图聚合

`site_map(domain="baidu.com")` 把 9 条流量聚合成 5 个 host：

```text
www.baidu.com         2 flows  10 findings  (/, /s)
hectorstatic.baidu.com 2 flows  0 findings
hector.baidu.com       1 flow   2 findings
t9.baidu.com           3 flows  0 findings
t15.baidu.com          1 flow   0 findings
```

`/s` 端点的 12 个 query 参数（wd、ie、tn、…）全部被自动抽出，可直接喂给 fuzz。

### 2.4 参数语义图

`traffic_params(/s 搜索请求)`：

- query：12 个参数全部正确归类，但 **`wd`（搜索词）未被打 `xss_candidate` 标签** —— 当前 param_extractor 对“关键词类参数”识别保守，可考虑在新提交里加上 `keyword_param`/`xss_candidate` 启发式。
- cookies：`BAIDUID` 正确识别为 `identity_param`；`BIDUPSID/PSTM` 没有进 identity 桶（属于次要 ID，可接受）。

### 2.5 被动扫描分流 — finding vs signal

```
traffic_findings_stats()
→ total=12  findings.count=0  signals.count=12
   (info=1 missing_csp + low=11 cookie_insecure)
```

- 公开页面被动扫无任何高/中危 finding，符合预期。
- 12 条 signal 都进了低置信桶（HttpOnly/Secure 缺失 + 缺 CSP），不会污染 agent 主上下文。
- **轻微口径瑕疵**：`traffic_list(with_findings=true)` 把 signal 也合到 `findings` 字段（91dee21… 报 4，9a8d4c6… 报 6），但 stats 里 `findings.count=0`。建议把列表字段改名 `signal_count` 或 `finding_total` 让 agent 不会误判严重度。

### 2.6 Tag + Link + Chain + Evidence

```
traffic_tag(91dee21…, "baidu_home")
traffic_tag(9a8d4c6…, "baidu_search")
traffic_link(91dee21… → 9a8d4c6…, relation="user_navigation")
traffic_chain(9a8d4c6…) → upstream=[91dee21… (user_navigation)], downstream=[]
evidence_bundle(9a8d4c6…, depth=2)
```

`evidence_bundle` 输出的 Markdown 包含：
- root + 上游每个 flow 的 method/url/status/profile/tags
- 每条 flow 的 findings（按 severity/category 编排）
- request/response body preview
- 完整 curl 复现命令

直接可以贴进 SRC 报告。这条链路按 `分析4.md` 设计的"Tag 命名 + Link 关系 + Chain 走图 + Bundle 出报告"完整跑通。

### 2.7 双浏览器上下文（重点）

```
session_create_context(name="victim", from_profile=false)
session_use_context(name="victim")
browser_navigate("https://www.baidu.com/?from=victim")
browser_get_cookies() → BAIDUID=DB1B55EC...A35C7E (victim)

session_use_context(name="default")
browser_get_cookies() → BAIDUID=BCF38349...AE0801A (default)  ← 完全不同
```

两个上下文的 cookie 完全独立，证明 `BrowserContext` 隔离正确实现。

### 2.8 跨身份重放（IDOR/BOLA 关键能力）

```
traffic_replay_via_browser(flow_id=9a8d4c6…, context="victim")
→ new_flow_id=ff22d2c7…, status=200, size=837367
```

新 flow 的请求 header 里 cookie 字段是 victim 的 `BAIDUID=DB1B55EC...`，**证明重放确实自动换上了 victim 的身份**，不是简单转发。

`traffic_diff(default_flow, victim_flow)`：

- status / size 一致
- diff 落在 `qid`、`rsv_t`、`bqid` 这种会话指纹字段（每次请求都会变）
- 没有 401/403，证明 baidu 搜索接口不强制鉴权，对 IDOR 测试场景这就是干净的 baseline

### 2.9 Profile 持久化

`session_save_profile(name="victim")` → `/tmp/agentproxy/baidu_test/victim_state.json` (1749 bytes)。

**观察到一个小差异**：README 写"`session_start(profile_dir=…)` saves storage state on stop"。session_stop 后该目录里只有 `victim_state.json`，没有 `default_state.json`。看起来 stop 不会自动 dump 当前 active context 的 storage_state，只会保存被显式 `session_save_profile` 过的 context。建议：
- 要么 stop 时为所有非 default context 都自动落盘
- 要么把 README 文案改成"login state survives across sessions when you call session_save_profile"

---

## 3. 结论

| 维度 | 结论 |
| --- | --- |
| 基础抓包链路 | 稳定。Playwright + mitmproxy + SQLite 三件全程无报错 |
| 分层抓包 | 达标，token 占用阶梯感明显 |
| 站点 / 参数 / 被动扫面三视图 | 达标，给 agent 提供"先看 surface 再读 body"的清晰路径 |
| Tag/Link/Chain/Bundle | 闭环跑通，evidence_bundle 直接出报告 |
| **双浏览器上下文** | **完全达到预期**：cookie 隔离、可切换、可跨身份重放、可持久化 |
| 跨身份重放 | victim cookie 真实带入请求，IDOR 测试链路成立 |

新工具与 README 描述基本一致，可以放心用于真实 SRC 流程。

## 4. 建议修复 / 后续优化

1. `traffic_list(with_findings=true)` 的 `findings` 字段把 signal 合并算入，与 `traffic_findings_stats` 的 finding/signal 划分口径不一致。建议拆成 `finding_count` / `signal_count` 两个字段。
2. `traffic_params` 对"搜索关键词类"参数（如 `wd`、`q`、`keyword`）应当默认加 `xss_candidate` / `sql_candidate` 启发式标签。
3. `session_stop` 是否在 profile_dir 模式下自动 dump active context 的 storage_state，需与 README 文案对齐（建议：自动 dump，让"login state survives"承诺落地）。
4. 测试覆盖：当前 `分析4.md` 设计的存储型 SSRF / 二阶段越权场景需要一个真实可控的靶场（DVWA/juiceshop 之类），baidu 公网站点只能验证抓包/重放/对比基础链路。下一步建议在内网起一个 juiceshop，跑一遍完整的 IDOR + evidence_bundle 闭环。
