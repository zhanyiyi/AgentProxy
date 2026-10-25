# AgentProxy 与 10 个相关 GitHub 项目的比较

核对日期：2026-10-25。AgentProxy 代码基线：`fea67f0`，并结合本轮压缩 SSE 的开发范围。竞品资料来自当天可访问的官方仓库和官方文档，相关页面后续可能变化。本报告核对了文档和本地实现，没有安装并实测全部竞品，没有同场任务成功率、性能、资源占用或成本基准，也不按 Star 数排名。

AgentProxy 目前是一个早期的 **Agent 浏览器操作与持久流量观察内核**。它已经把浏览器、代理、消息查询和步骤状态接到一起，但距离成熟的调试产品或业务流程平台仍有差距。值得保留的方向是这几部分之间明确、可靠的行为约定：页面观察来自哪个快照，动作进行到哪里，消息是否完整，重启后哪些结果仍未知。有 MCP、元素 refs、增量快照或 SSE/WebSocket 支持，都不能单独作为独有优势。

这 10 个项目并非全部直接替代品。前 6 个覆盖浏览器工具、Agent SDK 和业务工作流；后 4 个覆盖代理与流量调试，其中 mitmproxy 还是 AgentProxy 使用的上游底座。

| 项目与定位 | 官方资料证实的能力 | AgentProxy 当前的相对位置 |
|---|---|---|
| [Playwright MCP](https://github.com/microsoft/playwright-mcp)：通用浏览器 MCP | ARIA 快照、元素与 iframe refs、快照搜索和子树裁剪、表单与标签页、网络详情、存储和追踪；支持多浏览器和持久配置。[快照说明](https://github.com/microsoft/playwright.dev/blob/main/mcp/snapshots.mdx)、[工具与配置](https://github.com/microsoft/playwright-mcp/blob/main/README.md)。 | AgentProxy 的原生 refs 和基础交互沿用相同底层能力，不能当作独创。它多做了浏览器操作与独立 MITM 数据库的整合；Playwright MCP 已公开的浏览器能力面更广。 |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)：编码 Agent 的 Chrome 调试工具 | 页面操作、网络和控制台检查、性能 trace 与洞察，以及堆快照和内存分析。[官方工具说明](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/tool-reference.md)。 | 对页面加载、JS 内存和运行时问题，它有明确的专用工具。AgentProxy 的重点是请求、消息和本地操作记录，现有抓取能力不能等同于完整 DevTools 调试。 |
| [Browser Use](https://github.com/browser-use/browser-use)：带模型的浏览器 Agent 库 | 任务执行循环、自定义工具、结构化输出、本地或云浏览器，以及保存历史后带变量重放操作。[官方 README](https://github.com/browser-use/browser-use#faq)。 | AgentProxy 主要向外部 Agent 提供工具与状态，本身不是同等任务执行器。其检查点恢复活页位置并保留未知结果，与历史动作重放是不同机制；云端托管能力也应与开源库分开比较。 |
| [Stagehand](https://github.com/browserbase/stagehand)：浏览器 Agent SDK | `act/observe/extract`、自然语言定位、模式约束数据提取、自适应定位；当前提供 TypeScript、Python、Go，并支持本地和 Browserbase。[当前能力说明](https://github.com/browserbase/stagehand#why-stagehand)。 | AgentProxy 有确定性 refs 和失效检查，但尚无同等语义定位恢复与页面结构化提取接口。可借鉴其明确的观察、动作和提取分工；托管浏览器与缓存属于另外的产品层。 |
| [Skyvern](https://github.com/Skyvern-AI/skyvern)：浏览器业务工作流平台 | LLM/视觉驱动，提供 SDK、本地 UI/服务和无代码构建器；流程块涵盖任务、提取、验证、循环、文件解析等。[工作流说明](https://github.com/Skyvern-AI/skyvern#skyvern-workflows)。 | AgentProxy 的步骤检查点和动作记录属于基础能力，不能等同于完整业务流程编排。流程编辑、人工介入和任务结果呈现，仍是产品层差距。 |
| [agent-browser](https://github.com/vercel-labs/agent-browser)：面向 Agent 的浏览器 CLI/MCP | 已有 refs、按标签页维护的 delta、会话保存恢复、网络/HAR、安装诊断；MCP 按 core/network/state/debug 等分组。[MCP 分组](https://github.com/vercel-labs/agent-browser#mcp-server)、[快照配置](https://github.com/vercel-labs/agent-browser#snapshot-options)。 | AgentProxy 不能以“有 MCP、增量或恢复”宣称领先。对方的工具发现和安装诊断值得借鉴；AgentProxy 的比较价值是浏览器与持久流量数据的一体使用。 |
| [mitmproxy](https://github.com/mitmproxy/mitmproxy)：协议代理与插件底座 | 提供 HTTP、WebSocket 等协议实现、插件和终端/Web 工作界面；不同协议及代理模式有明确支持边界。[官方文档](https://docs.mitmproxy.org/stable/)、[协议与限制](https://docs.mitmproxy.org/stable/concepts/protocols/)。 | 它是 AgentProxy 的上游，而非被替换掉的协议实现。AgentProxy 新增的是浏览器与 MCP 接口、本地数据模型和操作状态；底层支持 HTTP/3 等协议，不代表当前封装和实际代理模式已经覆盖。 |
| [Whistle](https://github.com/avwo/whistle)：规则驱动的可视化流量调试 | HTTP/HTTPS/HTTP2/WebSocket 抓取、规则修改、请求编辑，以及插件和多种代理模式。[官方产品说明](https://wproxy.org/en/)。 | Whistle 的规则配置与人工排查界面更完整。AgentProxy 主要服务 Agent 的结构化查询和浏览器操作，目前不能以 MCP 接口代替这些交互体验。 |
| [HTTP Toolkit](https://github.com/httptoolkit/httptoolkit)：面向开发者的流量调试产品 | 客户端接入、流量详情与过滤、WebSocket 查看、请求修改与 mock；其查看页面标注 HAR 导入/导出等 Pro 能力。[官方查看页说明](https://httptoolkit.com/docs/reference/view-page/)、[修改请求说明](https://httptoolkit.com/docs/getting-started/rewriting/)。 | AgentProxy 的本地消息记录适合机器查询，但安装接入和人工排障呈现仍需打磨。HTTP Toolkit 的开源仓库与付费产品功能须区分，不能把全部桌面功能等同于免费开源版本。 |
| [ZAP](https://github.com/zaproxy/zaproxy)：可扩展的 Web 调试与安全工具平台 | 已有 [MCP 集成](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/)、[SSE 展示](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/)、[WebSocket 支持](https://www.zaproxy.org/docs/desktop/addons/websockets/about/)与 [YAML 自动化框架](https://www.zaproxy.org/docs/automate/automation-framework/)。 | 不能将传统平台描述为“没有 MCP”或“看不到流式消息”。AgentProxy 的取舍是较轻的浏览器与持久观察组合，而非已经覆盖 ZAP 的平台、插件和自动化生态。 |

表中的相对位置是根据上述资料与本地实现作出的工程判断，不是实测排名。未在某份 README 中看到某项功能，不构成该项目无法实现它的证据；同名的“恢复”“流式支持”也不保证相同的状态、存储和完整性语义。

AgentProxy 已经做到什么、还不能推断什么：

- 浏览器快照有 `snapshot_id`、增量基线和原生 refs；失效引用明确拒绝。iframe、标签页、原生对话框和下载有显式接口。实现见 [browser_snapshot.py](https://github.com/zhanyiyi/AgentProxy/blob/fea67f041939ad6f3888582a648e51cba0227753/src/agent_proxy/core/browser_snapshot.py) 与 [工具入口](https://github.com/zhanyiyi/AgentProxy/blob/fea67f041939ad6f3888582a648e51cba0227753/src/agent_proxy/tools/tools.py)。这改善了操作确定性，但不会自动理解业务任务是否成功。
- SSE 事件与 WebSocket 完整消息进入同一后台写入链路，连接开放时可通过递增游标查询；消息有保留上限和截断标记。它是有预算的消息观察，不是完整无损流量归档。本轮已补齐 gzip、deflate、Brotli、Zstandard 及编码链的增量 SSE 采集，支持范围与 21 个单元用例、1 个本地场景的验收记录见 [IMPLEMENTATION.md](https://github.com/zhanyiyi/AgentProxy/blob/codex/runtime-browser-polish/IMPLEMENTATION.md) 第三轮。
- 每步保存检查点，重启可读取进度，并对唯一匹配的现有页面重新绑定。执行中断时的未知结果保留，恢复不会自动重放操作。实现见 [session_manager.py](https://github.com/zhanyiyi/AgentProxy/blob/fea67f041939ad6f3888582a648e51cba0227753/src/agent_proxy/core/session_manager.py) 与 [workflow_state.py](https://github.com/zhanyiyi/AgentProxy/blob/fea67f041939ad6f3888582a648e51cba0227753/src/agent_proxy/core/workflow_state.py)。这属于本地执行状态恢复，不能等同于整条业务流程自动恢复。
- 动作回执和流量记录可以按时间辅助排查。动作完成只说明相应浏览器原语完成；时间相近的请求或消息只是候选关联，现有实现没有证明“该动作导致该请求”，也没有证明服务器业务已成功。

接下来优先打磨以下 5 件事，每项都应先形成一个小而完整的使用流程：

1. **明确任务结果。** 允许调用方为一个步骤指定简单可观察的成功条件，例如页面出现预期文字、下载已保存、已观察到某条消息；回执展示条件及证据，区分已满足、未满足和未知。保持调用方定义目标，不增加通用业务规划框架。
2. **让一次操作容易排查。** 提供同一视图中的动作、页面变化、同期请求和消息游标，显示时间与来源。明确标注时间相关性，缺少实际因果证据时不自动归因；这比继续增加零散工具更有用。
3. **缩短安装与接入路径。** 增加只读诊断入口，一次解释 Python/浏览器依赖、代理端口、CA、CDP、数据库路径和待写入状态，给出具体修复建议。先把首次使用和常见失败说清楚。
4. **减少工具发现负担。** 保留现有接口兼容性，按浏览器、流量查询和会话管理提供较小的可选工具组及短示例；让 Agent 先获取摘要，再按需读取正文、消息或截图，避免一次加载全部能力。
5. **补齐存储生命周期。** 展示每次采集的数据库和附件大小、保留预算、丢弃或失败计数；提供明确的导出与清理范围。当前清库会保留附件，产品入口应清楚表达这一点，后续再增加按会话管理的清理能力。

这些建议服务于正常业务操作的可解释性和诊断体验，不以增强自主漏洞攻击为目标。当前适合继续完善一个可靠、易用的观察与操作工具；是否形成更强产品竞争力，需要后续真实使用证据，而不是更多功能名。
