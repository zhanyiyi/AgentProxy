# AgentProxy 实现对齐与开发清单

代码基线：`7b537db`；已合并远端 `b2bee3b` 的本地文档管理约定。本文记录本轮实现与验收；旧版设计和问题分析仅保留在本地 `docs/`，不重新发布。

## 约束与设计

- 保持 BrowserController / SessionManager / MitmController / TrafficDB 分工，不引入编排框架。
- 实例拥有自己启动的资源；CDP 连接借用的 Context、页面不得被关闭。
- 启动、停止串行执行；取消和普通异常都释放已取得的资源。启动与清理分别有时间预算。
- 默认每个 MCP 实例使用独立数据库目录；显式 `--db-path` 用于用户主动复用历史记录。
- 入队不等于落库，队列为空不等于写完；写入完成、丢弃和错误必须可见。
- 浏览器动作回执区分动作完成、待处理弹窗和仍在进行的下载。按时间观察到的流量仅表示相关性。
- 保存事实与可用性元数据；相似度不替代业务权限预期。
- 保留旧工具，新工具只补齐实际使用缺口；不为工具数量目标大规模重命名。
- 不默认接受确认框，不默认关闭上游 TLS 校验。
- 不实现自动漏洞挖掘、跨身份攻击编排、参数攻击变异或自动利用链。

## 代码与文档对齐

| 项目 | 基线实现/核验 | 本轮工作与完成条件 | 状态 |
|---|---|---|---|
| 启动取消、并发与清理 | session_manager.py 只捕获 Exception，无生命周期锁 | 串行启动/停止，取消释放资源，状态可查询 | 已完成 |
| 浏览器半启动泄漏 | stop 依赖 running=True | 按已持有句柄清理，失败后可重新启动 | 已完成 |
| CDP 所有权 | 借用 Context 后无条件关闭 | 只关闭本实例创建的 Context/页面 | 已完成 |
| 进程退出 | main.py 无 MCP lifespan 清理 | transport 生命周期结束时关闭 Session | 已完成 |
| 超时与日志 | 部分底层超时已有，整体预算和文件日志缺失 | 启动/清理预算，统一旋转文件日志，记录阶段与异常 | 已完成 |
| 多实例隔离 | 默认同 cwd 同库 | 默认实例目录，显式数据库仍兼容 | 已完成 |
| 后台写入 | drain 只检查 queue.empty，丢弃未配对 task_done | 等待实际处理结束，停止超时不丢线程句柄，状态可见 | 已完成 |
| 响应完整性 | 非 UTF-8 硬解码，二进制省略 | 按 charset 解码，附件落盘与文件哈希元数据，多值头可读取 | 已完成 |
| 流量搜索 | LIKE 通配符和 URL 子串域名匹配 | 字面量关键词、按 hostname 匹配 | 已完成 |
| 采集范围 | 默认过滤 .pdf / OPTIONS | 保存 PDF 与预检元数据，继续尊重域名范围 | 已完成 |
| 无障碍观察 | 已移除的 Page.accessibility | ARIA snapshot，显式 frame 选择 | 已完成 |
| 多页交互 | 每 Context 单活动页 | 追踪 popup，可列出/切换/关闭自己拥有的 tab | 已完成 |
| Dialog | 无事件模型 | 显式待处理状态与 accept/dismiss 工具 | 已完成 |
| Download | 无保存与完成状态 | 跟踪任务、保存文件、大小/hash/失败可查询 | 已完成 |
| 动作反馈与时间线 | Clicked 文本，无持久动作日志 | 通用动作回执与可查询时间线，不承诺精确因果归因 | 已完成 |
| MCP 输出 | 截图为 Base64 文本，失败为成功字符串 | 原生图片，新浏览器接口/导航/流量详情明确报错，准确工具提示；其余旧工具返回格式保留 | 已完成 |
| 重型只读分析 | 同步执行阻塞 loop | 工具层将重型分析移至工作线程 | 已完成 |
| Windows 证书工具 | 系统 certutil 被误当 NSS 工具 | 区分 NSS/系统命令，给出准确支持说明 | 已完成 |
| Prompt 动态签名 | front matter 参数直接拼接 exec | 校验参数为 Python 标识符，移除同步探测阻塞 | 已完成 |
| 验收可信度 | E2E 捕获断言后不抛出，Windows 0600 测试不适用 | 失败真实传播，适量故障回归与本地多步场景验收 | 已完成 |

## 收回或暂不采用的旧方案断言

- `upsert_note` 的 SELECT 不在所声称的显式读事务中，不能据此宣布锁升级死锁。
- 当前 MITM 已有就绪轮询；Playwright launch/CDP 也有内部超时，仍需整体生命周期预算。
- `Page.accessibility` 在 1.57 移除，1.49 引入 ARIA snapshot；open Shadow DOM 可被默认定位器穿透。
- CDP initiator、时间窗口只能提供关联线索，不能证明所有请求的唯一用户动作因果关系。
- 多值头已在数据库中以有序列表保存，应补齐读取接口而非重复设计捕获格式。
- 不采用未经测量的 50 倍吞吐、固定 token 节省率、100% 命中率等收益承诺。
- 不引入自绑定 Win32 Job Object、父进程强制退出与大型批处理重构；先修复实际生命周期与完成语义。

## 验证与交付

开发后运行一次相关单元回归，以及本地可控网页的多页、弹窗、下载场景。仅在出现实际失败或实现变化时重跑受影响部分。记录真实结果，不把 skip 计为通过。

公开说明位于 README 与本文；本地历史文档不纳入提交。代码提交到 `codex/runtime-browser-polish` 并推送 origin。


### 实际验收

- 离线统一回归：`python -m pytest -m "not integration" -q -p no:cacheprovider`，102 passed、3 skipped、6 deselected，15.44 秒。
- 本地多步骤验收：`AGENTPROXY_RUN_INTEGRATION=1 python -m pytest tests/test_browser_workflow_integration.py -q -p no:cacheprovider`，1 passed，7.61 秒。
- 本地流程覆盖 iframe 观察与输入、确认框显式处理、popup 选择、下载保存/hash、PDF 代理捕获、持久动作记录与原生 MCP 图片，并确认 lifespan 结束后资源关闭。
- 跳过项：2 个依赖 NSS certutil 的用例，以及 Windows 不适用的 POSIX 权限位断言。另 5 个旧固定端口集成套件本轮未运行。
- 对取消、并发、写入未完成、CDP 所有权和驱动停止重试采用定向故障回归，不以反复运行测试代替设计。

### 接口与边界

新增 `browser_snapshot`、`browser_act`、`browser_tabs`、`browser_dialog`、`browser_downloads`、`session_timeline` 六个工具；保留原有工具名。click/fill/type/select/key 返回动作回执 JSON，截图返回 MCP 原生图片，调用方需据此读取结果。

`completed` 表示浏览器原语完成，不证明业务任务完成。弹窗保留 pending 等待显式决策；下载只在保存和哈希完成后标为 completed。动作时间线保存当时回执，下载最新状态由下载查询读取。没有引入网络因果判断或业务权限自动裁决。

附件保存的是已捕获响应消息字节，不下载远程链接、不自动解析 PDF/Office。`traffic_clear` 清数据库记录，保留本地附件文件；删除整个实例目录可清理该次采集。默认目录为 `.agentproxy/sessions/<instance-id>`，显式数据库路径表示用户主动复用。

本轮没有实现 SSE/WebSocket 消息级存储、增量 ARIA ref、跨步骤自动恢复、强杀宿主进程树等额外能力；这些需要独立场景、资源预算和完成条件，不作为当前已解决问题。保留现有重放/模糊测试接口，未增强自动攻击能力。
