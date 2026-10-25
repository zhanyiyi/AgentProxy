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

首轮没有实现 SSE/WebSocket 消息级存储、增量 ARIA ref 与跨步骤恢复。下面记录后续开发，不将首轮结论当作这些能力已经完成。保留现有重放/模糊测试接口，不增强自动攻击能力。

## 第二轮：流式观察、引用与步骤恢复

本轮代码基线为 `c55de24`，继续在 `codex/runtime-browser-polish` 提交。

| 项目 | 当前实现 | 本轮接口与验收条件 | 状态 |
|---|---|---|---|
| SSE 消息 | response 等待结束，没有增量消息存储 | responseheaders 安装透传 observer；完整事件产生即入后台队列，连接关闭前可查询，原字节不变 | 已完成 |
| WebSocket 消息 | 只保存 HTTP 握手 | 保存重组后的文本/二进制消息、方向、时间和 flow_id；查询使用递增游标 | 已完成 |
| 流消息预算 | 无独立流消息预算 | 单消息保留至多 64 KiB，每连接至多 1000 条及一次限额记录；截断/编码不支持均有标记 | 已完成 |
| 增量快照 | 每次完整 ARIA，无元素引用 | 复用 Playwright 1.60 原生 AI ARIA 快照及 refs；首次全量，随后明确基线的增量，tab/frame 分开管理 | 已完成 |
| 引用操作 | 仅 selector | browser_act 支持 ref 与 snapshot_id；引用必须来自已交付快照，失效引用明确报错，不猜测替换目标 | 已完成 |
| 步骤检查点 | 有历史回执，无待续游标 | 每步自动保存本地观察位置与执行状态；同一数据库重启能读取检查点，不保存表单输入 | 已完成 |
| 恢复 | 无恢复判定 | 自动重绑仍存在的同 Context/URL 页面；否则返回待续计划。中断时执行结果未知的步骤标 needs_review，不自动重放 | 已完成 |

### 完成语义

- SSE 是事件而不是网络 chunk；WebSocket 是完整消息而不是底层 frame。采集只观察已经过代理的连接，不发包、不修改消息。
- `traffic_messages(flow_id?, after_id=0, limit=50, protocol?)` 只读查询已保存消息，返回 messages 与 next_after_id。二进制以 base64 表达，消息头尾和截断状态不混为完整正文。
- 快照返回 `snapshot_id`、`base_snapshot_id` 和 full/delta 模式。导航、文档变化、快照截断等使旧基线不可用时返回全量；refs 依赖其对应快照。
- 检查点恢复只处理本地状态和待续位置。浏览器页面已关闭或进程已退出时，不自动导航、登录、提交、删除或重放原步骤；工具返回明确恢复计划，调用方再决定下一次新操作。
- 自动保存与恢复本地步骤进度属于本轮范围；自动继续执行网站业务链不属于本轮范围。原语完成依旧不等于业务任务完成。

### 本轮验证计划

实现后统一执行一次离线回归，并用一个仅访问本地 fixture 的完整场景检查：SSE 连接未关闭时读取事件、WebSocket 双向消息、增量 snapshot/ref、页面绑定恢复及不重放未知步骤。只有实际失败或代码修正才重跑受影响用例。实现完成后把实际结果补入本文。


### 第二轮实际验证与接口

- 统一离线回归一次：`python -m pytest -m "not integration" -q -p no:cacheprovider`，123 passed、3 skipped、7 deselected，17.21 秒。
- 两条本地集成场景一次执行：`AGENTPROXY_RUN_INTEGRATION=1 python -m pytest tests/test_browser_workflow_integration.py tests/test_stream_workflow_integration.py -q -p no:cacheprovider`，2 passed，10.25 秒。未重跑完整测试集。
- 新场景覆盖 SSE 尚未关闭即读取事件、WebSocket 双向与查询游标、原生 iframe ref、增量基线与不变引用、活页位置恢复、同库重启未知结果保留；原场景继续覆盖确认框、下载、PDF 捕获与原生图片。
- 新增 `traffic_messages` 与 `browser_checkpoint`；`browser_snapshot` 新增 incremental，`browser_act` 新增 ref/snapshot_id。旧 selector 参数继续可用，旧 accessibility 接口返回全量快照。
- 检查点的 inspect/save/restore/acknowledge 共用现有 workflow 锁；标签页、Context 切换及 dialog 处理与步骤写入串行。存储只记录脱敏动作元数据，重启后未完成或待弹窗的步骤保留 unknown。
- 显式导航允许调用方重新观察位置，但不会清掉上一次未知业务结果。恢复本身不导航、不执行网站操作；找不到唯一匹配活页时给出 resume_required。
- SSE 始终按 UTF-8 解码，忽略 charset 标签；压缩流保留原样转发并明确记录解析不支持。消息和 Flow 继续共用一个后台 writer，未增加编排框架或自动重试。

原生引用和流式消息语义分别依据 [Playwright AI ARIA snapshot](https://playwright.dev/python/docs/api/class-page#page-aria-snapshot)、[mitmproxy hooks](https://docs.mitmproxy.org/stable/api/events.html) 与 [SSE 标准](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)；实际兼容性已由本地安装版本与上述场景验证。

- 最终检查修正了过期 ref 的状态：原语执行前的验证拒绝记录为 not_started/ready，刷新快照即可继续，不误报业务结果未知。只复验受影响检查点用例：9 passed，3.42 秒；没有重跑完整回归或本地集成。
- 补齐既有 browse_and_capture 入口的同一检查点路径，并在 pending 决策处终止显式动作列表，避免后续步骤在未确认页面状态上继续。只验证这一个受影响场景：1 passed，1.99 秒；未重跑其它用例。

## 第三轮：压缩 SSE 与竞品核对

代码基线为 `fea67f0`。本地旧方案提出的实时消息盲区已由第二轮解决；本轮缺口是 Content-Encoding 解码，消息表、游标和后台 writer 已存在，不另建存储链路。

| 项目 | 基线实现 | 本轮完成条件 |
|---|---|---|
| 压缩 SSE | identity 可解析，其余编码记 unsupported | 增量解析 gzip、deflate、br、zstd；按逆序处理编码链，复用 SSEParser 和消息预算 |
| 转发合同 | observer 原样返回 transport chunk | 不改响应头和转发字节；解码无输出不触发 SSE EOF；未知编码仍明确省略 |
| 消息存储 | stream_messages 已支持 metadata、游标、共用 writer | 保存原 content_encoding；损坏/截断压缩流保存诊断，保留已收到的尾事件；连接未关闭即可查询 |
| 收尾 | 正常空块和 error hook 共用 EOF | 正常结束检查压缩完整性，异常断连标记 transport_interrupted；不重复收尾、不重试上游 |
| 横向比较 | 尚无本轮官方来源对比 | 核对 10 个 GitHub 项目，区分直接竞品与上游/相邻工具；不把有 MCP、refs 或流式消息宣称为独有能力 |

实现后执行一次流采集相关单元用例，并将既有本地多步场景改为 gzip SSE，验证浏览器与消息查询在连接开放时同时收到事件。仅在实际失败或代码修正后复验受影响部分，不重复完整测试集。Brotli 与 Zstandard 使用公开增量 API；存储保留预算不等于第三方解压库的严格峰值内存上限。

### 第三轮交付与验证

- 已完成上表各项。新增一个 content decoder 和一个 SSE observer，复用原 parser、StreamCapture、writer 与消息表，没有数据库迁移。直接声明 Brotli/Zstandard 依赖，不依赖上游偶然安装它们。
- 支持 gzip/x-gzip、标准及 raw deflate、br、zstd 与编码链；gzip 连续成员和 zstd 连续帧在同块或跨块时均能解析。每条事件保留 content_encoding，原始 HTTP 头与转发字节不变。
- 解码损坏记录 decode_error；正常结束但缺少压缩尾记录 incomplete_stream。传输异常结束仅给已解出的尾事件标记 transport_interrupted，保留 incomplete 语义。未知编码保持 unsupported；诊断与事件共用已有消息预算和 writer。
- 一次定向执行：`AGENTPROXY_RUN_INTEGRATION=1 python -m pytest tests/test_stream_capture.py tests/test_stream_workflow_integration.py -q -p no:cacheprovider`，21 passed、1 failed，6.14 秒。失败是新增集成断言使用小写键读取保留原大小写的 Content-Encoding；当时浏览器与数据库均已收到压缩 SSE。
- 修正该断言后只复验受影响集成文件：1 passed，4.15 秒。没有重复单元或完整回归。场景同时覆盖 gzip SSE 未关闭时可查询、原响应头、WebSocket 双向消息、增量 refs 与步骤状态恢复。
- 10 项对比见 [COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md)。依据官方仓库及文档，不提供未经实测的性能、任务成功率或名次结论。

实现核对了 [mitmproxy stream 合同](https://docs.mitmproxy.org/stable/api/mitmproxy/http.html)、[Brotli Python 增量 API](https://github.com/google/brotli/blob/master/python/_brotli.c) 与 [Zstandard 增量解码及结束状态](https://python-zstandard.readthedocs.io/en/latest/decompressor.html)，并由本地定向场景验证当前环境。
