# AgentProxy 与 10 个相关项目：完整公开功能清单及横向对比

核对日期：2026-10-25（Asia/Shanghai）。AgentProxy 比较基线为 `codex/runtime-browser-polish` 的 `e8ca17e781272ab3a690e348ab4415211ccde148`，包含上一轮压缩 SSE；不以较旧的默认 main 代替。竞品源码按各自默认分支固定 SHA，已发行版本、开发分支、旧版文档和云端 API 分开记录。

本报告覆盖 **11 个项目、106 个统一维度、541 个功能分组、2240 个具名接口/命令/配置条目、439 条来源记录**。每个矩阵单元格可点击查看具体范围和证据。条目粒度因产品形态不同，不用这些数量计算优劣、成功率或排名。

## 范围与核对方法

这里的“完整”指在记录版本上，按官方完整工具目录、SDK/CLI 参考、功能导航、官方插件类别及必要源码枚举公开产品能力。动态生成工具、任意用户脚本、第三方插件的所有组合、每条扫描规则与所有参数取值，无法作为有限功能表逐个穷尽；对应扩展机制与边界已经列出。涉及安全测试的项目只比较高层能力，不提供操作或利用流程。

资料核对顺序是：固定源码接口定义 → 同版本文档/迁移说明 → 官方在线产品文档。默认分支并不必然等于最新稳定发行；在线文档仍可能变化。未安装并实测全部竞品，不把官方功能说明写成实测效果。没有找到明确证据的项目保留“未证实”，不会因为 README 没写就填“没有”。

统一维度用于比较主要交集；项目特有能力继续保留在完整明细。例如 WebMCP、PWA/WebAuthn、无障碍审计、剪贴板、PDF处理、电子表格集成、各类内容视图、规则协议与官方插件，不会为压缩总表而删掉。具体交付范围仍以每条状态和来源为准。

本次只调研与编写文档，不修改业务实现，不运行产品功能测试。

## 状态说明

| 标记 | 含义 |
|---|---|
| 原生 | 项目正式实现的产品能力；默认开关、依赖和具体暴露范围仍需读明细，不表示所有工具默认开启。 |
| 可选 | 需要官方插件、工具组、扩展或明确启用的额外组件。 |
| 付费 | 官方明确归入 Pro/收费层；不据此推断其它功能都免费。 |
| 云端 | 属于托管产品/API；不自动算作开源本地版，也不表示免费。 |
| 部分 | 只有子能力、限定模式或不同合同，不能与完整支持直接等价。 |
| 未提供 | 已核对的公开入口或明确实现没有提供该能力；不代表通过任意脚本永远做不到。 |
| 未证实 | 已核对范围仍不足以确认；是调研剩余不确定性，不记为缺失。 |
| 不适用 | 超出这个项目的产品职责，例如代理工具的页面元素定位。 |

## 项目、固定版本与详细功能目录

前六个竞品覆盖浏览器工具、Agent SDK 和业务流程；后四个覆盖代理、调试及测试工作台。mitmproxy 是 AgentProxy 的上游依赖，比较时保留这层关系。

| 项目 | 固定源码 SHA | 版本 / 授权边界 | 功能分组 / 具名条目 | 未证实维度 |
|---|---|---|---|---|
| [AgentProxy](research/competitive/agentproxy.md) | [e8ca17e78127](https://github.com/zhanyiyi/AgentProxy/commit/e8ca17e781272ab3a690e348ab4415211ccde148) | pyproject 0.1.0；对比 codex/runtime-browser-polish 的 e8ca17e，不是默认 main；pyproject 声明 MIT；当前跟踪目录没有单独 LICENSE 文件 | 78 / 84 | 0 |
| [Playwright MCP](research/competitive/playwright-mcp.md) | [0c4107acbecb](https://github.com/microsoft/playwright-mcp/commit/0c4107acbecb75472b23c05c0e42471a0011874f) | 0.0.83（package.json；正式发布 v0.0.83 于 2026-09-28；HEAD 可能含发布后文档变化）；Apache-2.0 | 33 / 124 | 24 |
| [Chrome DevTools MCP](research/competitive/chrome-devtools-mcp.md) | [ada7963246c0](https://github.com/ChromeDevTools/chrome-devtools-mcp/commit/ada7963246c0c91eae185125a57aecd13cbe0376) | 1.12.0（package.json；正式发布 chrome-devtools-mcp-v1.12.0 于 2026-10-22）；Apache-2.0 | 36 / 178 | 27 |
| [Browser Use](research/competitive/browser-use.md) | [3df5806a0d09](https://github.com/browser-use/browser-use/commit/3df5806a0d097a1546d92c49bcf1b28c9972c3bd) | 0.13.13（仓库pyproject；Cloud API v4与CLI 3.0单独标注）；MIT | 47 / 265 | 25 |
| [Stagehand](research/competitive/stagehand.md) | [8023f34161d6](https://github.com/browserbase/stagehand/commit/8023f34161d650c196dc343d2c232fb5e129a826) | 4.0.0（当前monorepo package.json；v3兼容文档不等同当前API）；MIT | 49 / 179 | 25 |
| [Skyvern](research/competitive/skyvern.md) | [c4022ddeb209](https://github.com/Skyvern-AI/skyvern/commit/c4022ddeb209834672c6224ee2fe486e087ea83c) | 1.0.56（仓库pyproject）；云端引擎Default/3.0与自托管能力另述；AGPL-3.0 | 87 / 424 | 15 |
| [agent-browser](research/competitive/agent-browser.md) | [372ac5ce20fa](https://github.com/vercel-labs/agent-browser/commit/372ac5ce20fab885dbf45ee0c9d510ec8c3b6fdb) | 0.39.2（package.json；正式发布 v0.39.2 于 2026-10-22）；Apache-2.0 | 50 / 393 | 12 |
| [mitmproxy](research/competitive/mitmproxy.md) | [7cb38827580f](https://github.com/mitmproxy/mitmproxy/commit/7cb38827580fa8a87af28c43441ab11132747e4a) | 12.3.0（GitHub 最新正式发布 v12.3.0，2026-10-22；比较源码为 main HEAD）；MIT | 39 / 189 | 14 |
| [Whistle](research/competitive/whistle.md) | [16607ba277b3](https://github.com/avwo/whistle/commit/16607ba277b383d050bc6efce046b4c92cc0ae39) | 2.10.12（master HEAD 的 package.json；GitHub /releases/latest 返回 404，不虚构发布标签）；MIT | 39 / 201 | 17 |
| [HTTP Toolkit](research/competitive/http-toolkit.md) | [bb579a8ceadf](https://github.com/httptoolkit/httptoolkit/commit/bb579a8ceadfe86b98160843c0447a5b9eec554f) | 桌面最新 v1.27.3（2026-10-20）；元仓库无独立 release。UI/server/desktop 是独立更新组件，见 notes 固定 HEAD。；产品专属组件主要 AGPL-3.0；通用库采用 Apache-2.0/MIT。元仓库未声明单一 license；免费与 Pro 是产品功能分层，源码公开不等于全部预构建功能免费。 | 47 / 66 | 10 |
| [ZAP](research/competitive/zap.md) | [1228a82745c5](https://github.com/zaproxy/zaproxy/commit/1228a82745c5bb22d9e33e0eeb826c533c359443) | 2.17.0（最新正式 core release，2025-12-15）；比较 main HEAD 与当日独立更新的插件。；Apache-2.0（core）；独立插件和第三方组件各自核对。 | 36 / 137 | 24 |

## 可以筛选和复核的数据

- [完整横向 CSV](COMPETITIVE_FEATURE_MATRIX.csv)：106 行维度，11 个项目并排；每格包含状态和限定说明，适合 Excel 筛选。
- [逐项证据 CSV](research/competitive/feature-evidence.csv)：每个“项目 × 维度”一行，保留完整说明及来源 URL。
- 每个项目的 Markdown 明细列出功能、具名接口和 106 项判断依据；对应 JSON 是同一份可复用调研数据。
- [统一维度定义](research/competitive/dimensions.json)：避免同名功能比较时改变含义。

## 逐项横向功能矩阵

为保证页面可读，浏览器方向与代理方向分表，均保留 AgentProxy 列。点击状态可跳到项目明细中对应维度的具体结论及来源。这个表不能按“原生”个数加总排名。

### 接入与产品形态

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| D01 原生 MCP tools | [原生](research/competitive/agentproxy.md#d01) | [原生](research/competitive/playwright-mcp.md#d01) | [原生](research/competitive/chrome-devtools-mcp.md#d01) | [可选](research/competitive/browser-use.md#d01) | [可选](research/competitive/stagehand.md#d01) | [可选](research/competitive/skyvern.md#d01) | [原生](research/competitive/agent-browser.md#d01) |
| D02 MCP resources / prompts | [可选](research/competitive/agentproxy.md#d02) | [未证实](research/competitive/playwright-mcp.md#d02) | [未证实](research/competitive/chrome-devtools-mcp.md#d02) | [未提供](research/competitive/browser-use.md#d02) | [未证实](research/competitive/stagehand.md#d02) | [可选](research/competitive/skyvern.md#d02) | [未提供](research/competitive/agent-browser.md#d02) |
| D03 stdio 接入 | [原生](research/competitive/agentproxy.md#d03) | [原生](research/competitive/playwright-mcp.md#d03) | [原生](research/competitive/chrome-devtools-mcp.md#d03) | [可选](research/competitive/browser-use.md#d03) | [可选](research/competitive/stagehand.md#d03) | [可选](research/competitive/skyvern.md#d03) | [原生](research/competitive/agent-browser.md#d03) |
| D04 HTTP 远程机器接口 | [原生](research/competitive/agentproxy.md#d04) | [原生](research/competitive/playwright-mcp.md#d04) | [部分](research/competitive/chrome-devtools-mcp.md#d04) | [云端](research/competitive/browser-use.md#d04) | [云端](research/competitive/stagehand.md#d04) | [原生](research/competitive/skyvern.md#d04) | [部分](research/competitive/agent-browser.md#d04) |
| D05 任务操作 CLI | [未提供](research/competitive/agentproxy.md#d05) | [部分](research/competitive/playwright-mcp.md#d05) | [原生](research/competitive/chrome-devtools-mcp.md#d05) | [原生](research/competitive/browser-use.md#d05) | [可选](research/competitive/stagehand.md#d05) | [可选](research/competitive/skyvern.md#d05) | [原生](research/competitive/agent-browser.md#d05) |
| D06 人工操作 UI | [未提供](research/competitive/agentproxy.md#d06) | [部分](research/competitive/playwright-mcp.md#d06) | [未提供](research/competitive/chrome-devtools-mcp.md#d06) | [云端](research/competitive/browser-use.md#d06) | [云端](research/competitive/stagehand.md#d06) | [原生](research/competitive/skyvern.md#d06) | [原生](research/competitive/agent-browser.md#d06) |
| D07 可编程 SDK / 插件 API | [部分](research/competitive/agentproxy.md#d07) | [原生](research/competitive/playwright-mcp.md#d07) | [可选](research/competitive/chrome-devtools-mcp.md#d07) | [原生](research/competitive/browser-use.md#d07) | [原生](research/competitive/stagehand.md#d07) | [原生](research/competitive/skyvern.md#d07) | [原生](research/competitive/agent-browser.md#d07) |
| D08 本地运行 | [原生](research/competitive/agentproxy.md#d08) | [原生](research/competitive/playwright-mcp.md#d08) | [原生](research/competitive/chrome-devtools-mcp.md#d08) | [原生](research/competitive/browser-use.md#d08) | [原生](research/competitive/stagehand.md#d08) | [原生](research/competitive/skyvern.md#d08) | [原生](research/competitive/agent-browser.md#d08) |
| D09 官方托管云 | [未提供](research/competitive/agentproxy.md#d09) | [未证实](research/competitive/playwright-mcp.md#d09) | [未证实](research/competitive/chrome-devtools-mcp.md#d09) | [云端](research/competitive/browser-use.md#d09) | [云端](research/competitive/stagehand.md#d09) | [云端](research/competitive/skyvern.md#d09) | [云端](research/competitive/agent-browser.md#d09) |
| D10 Docker / 容器交付 | [未提供](research/competitive/agentproxy.md#d10) | [原生](research/competitive/playwright-mcp.md#d10) | [未证实](research/competitive/chrome-devtools-mcp.md#d10) | [原生](research/competitive/browser-use.md#d10) | [未证实](research/competitive/stagehand.md#d10) | [原生](research/competitive/skyvern.md#d10) | [部分](research/competitive/agent-browser.md#d10) |
| D11 安装与运行诊断入口 | [部分](research/competitive/agentproxy.md#d11) | [部分](research/competitive/playwright-mcp.md#d11) | [原生](research/competitive/chrome-devtools-mcp.md#d11) | [原生](research/competitive/browser-use.md#d11) | [可选](research/competitive/stagehand.md#d11) | [可选](research/competitive/skyvern.md#d11) | [原生](research/competitive/agent-browser.md#d11) |
| D12 工具按能力分组启用 | [未提供](research/competitive/agentproxy.md#d12) | [原生](research/competitive/playwright-mcp.md#d12) | [原生](research/competitive/chrome-devtools-mcp.md#d12) | [原生](research/competitive/browser-use.md#d12) | [部分](research/competitive/stagehand.md#d12) | [原生](research/competitive/skyvern.md#d12) | [原生](research/competitive/agent-browser.md#d12) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| D01 原生 MCP tools | [原生](research/competitive/agentproxy.md#d01) | [未证实](research/competitive/mitmproxy.md#d01) | [未证实](research/competitive/whistle.md#d01) | [部分](research/competitive/http-toolkit.md#d01) | [可选](research/competitive/zap.md#d01) |
| D02 MCP resources / prompts | [可选](research/competitive/agentproxy.md#d02) | [未证实](research/competitive/mitmproxy.md#d02) | [未证实](research/competitive/whistle.md#d02) | [未提供](research/competitive/http-toolkit.md#d02) | [可选](research/competitive/zap.md#d02) |
| D03 stdio 接入 | [原生](research/competitive/agentproxy.md#d03) | [未证实](research/competitive/mitmproxy.md#d03) | [未证实](research/competitive/whistle.md#d03) | [原生](research/competitive/http-toolkit.md#d03) | [未证实](research/competitive/zap.md#d03) |
| D04 HTTP 远程机器接口 | [原生](research/competitive/agentproxy.md#d04) | [部分](research/competitive/mitmproxy.md#d04) | [部分](research/competitive/whistle.md#d04) | [部分](research/competitive/http-toolkit.md#d04) | [原生](research/competitive/zap.md#d04) |
| D05 任务操作 CLI | [未提供](research/competitive/agentproxy.md#d05) | [原生](research/competitive/mitmproxy.md#d05) | [原生](research/competitive/whistle.md#d05) | [原生](research/competitive/http-toolkit.md#d05) | [原生](research/competitive/zap.md#d05) |
| D06 人工操作 UI | [未提供](research/competitive/agentproxy.md#d06) | [原生](research/competitive/mitmproxy.md#d06) | [原生](research/competitive/whistle.md#d06) | [原生](research/competitive/http-toolkit.md#d06) | [原生](research/competitive/zap.md#d06) |
| D07 可编程 SDK / 插件 API | [部分](research/competitive/agentproxy.md#d07) | [原生](research/competitive/mitmproxy.md#d07) | [原生](research/competitive/whistle.md#d07) | [原生](research/competitive/http-toolkit.md#d07) | [原生](research/competitive/zap.md#d07) |
| D08 本地运行 | [原生](research/competitive/agentproxy.md#d08) | [原生](research/competitive/mitmproxy.md#d08) | [原生](research/competitive/whistle.md#d08) | [原生](research/competitive/http-toolkit.md#d08) | [原生](research/competitive/zap.md#d08) |
| D09 官方托管云 | [未提供](research/competitive/agentproxy.md#d09) | [未证实](research/competitive/mitmproxy.md#d09) | [未证实](research/competitive/whistle.md#d09) | [未证实](research/competitive/http-toolkit.md#d09) | [未证实](research/competitive/zap.md#d09) |
| D10 Docker / 容器交付 | [未提供](research/competitive/agentproxy.md#d10) | [原生](research/competitive/mitmproxy.md#d10) | [部分](research/competitive/whistle.md#d10) | [未证实](research/competitive/http-toolkit.md#d10) | [原生](research/competitive/zap.md#d10) |
| D11 安装与运行诊断入口 | [部分](research/competitive/agentproxy.md#d11) | [部分](research/competitive/mitmproxy.md#d11) | [原生](research/competitive/whistle.md#d11) | [原生](research/competitive/http-toolkit.md#d11) | [原生](research/competitive/zap.md#d11) |
| D12 工具按能力分组启用 | [未提供](research/competitive/agentproxy.md#d12) | [部分](research/competitive/mitmproxy.md#d12) | [部分](research/competitive/whistle.md#d12) | [部分](research/competitive/http-toolkit.md#d12) | [部分](research/competitive/zap.md#d12) |

本组口径：D01：项目正式提供 MCP server 或官方集成，不以第三方包装代替；D02：官方公开资源或提示模板接口；D03：通过 stdio 提供机器接口；D04：MCP HTTP、REST 或远程 SDK 接口，具体类型需说明；D05：CLI 可执行产品操作，而不只是启动服务；D06：独立桌面或 Web 操作界面，不把浏览器 headed 模式当工作台；D07：官方面向开发者的代码调用或插件接口；D08：核心能力可在本机运行，是否需要模型另述；D09：项目方正式提供托管服务，区分开源本体；D10：官方提供容器镜像或构建/运行路径；D11：专门的 doctor / status / health 或同类诊断，注明覆盖范围；D12：调用方可以按工具组缩小暴露面。

### 浏览器连接与交互

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| B01 启动受控浏览器 | [原生](research/competitive/agentproxy.md#b01) | [原生](research/competitive/playwright-mcp.md#b01) | [原生](research/competitive/chrome-devtools-mcp.md#b01) | [原生](research/competitive/browser-use.md#b01) | [原生](research/competitive/stagehand.md#b01) | [可选](research/competitive/skyvern.md#b01) | [原生](research/competitive/agent-browser.md#b01) |
| B02 连接已有浏览器 / CDP | [原生](research/competitive/agentproxy.md#b02) | [可选](research/competitive/playwright-mcp.md#b02) | [可选](research/competitive/chrome-devtools-mcp.md#b02) | [原生](research/competitive/browser-use.md#b02) | [原生](research/competitive/stagehand.md#b02) | [可选](research/competitive/skyvern.md#b02) | [原生](research/competitive/agent-browser.md#b02) |
| B03 多浏览器引擎 | [未提供](research/competitive/agentproxy.md#b03) | [原生](research/competitive/playwright-mcp.md#b03) | [未提供](research/competitive/chrome-devtools-mcp.md#b03) | [未提供](research/competitive/browser-use.md#b03) | [未提供](research/competitive/stagehand.md#b03) | [未提供](research/competitive/skyvern.md#b03) | [部分](research/competitive/agent-browser.md#b03) |
| B04 headless / headed | [原生](research/competitive/agentproxy.md#b04) | [原生](research/competitive/playwright-mcp.md#b04) | [原生](research/competitive/chrome-devtools-mcp.md#b04) | [原生](research/competitive/browser-use.md#b04) | [原生](research/competitive/stagehand.md#b04) | [可选](research/competitive/skyvern.md#b04) | [原生](research/competitive/agent-browser.md#b04) |
| B05 独立会话 / Context | [原生](research/competitive/agentproxy.md#b05) | [原生](research/competitive/playwright-mcp.md#b05) | [部分](research/competitive/chrome-devtools-mcp.md#b05) | [原生](research/competitive/browser-use.md#b05) | [原生](research/competitive/stagehand.md#b05) | [可选](research/competitive/skyvern.md#b05) | [原生](research/competitive/agent-browser.md#b05) |
| B06 持久用户目录 / 配置 | [部分](research/competitive/agentproxy.md#b06) | [原生](research/competitive/playwright-mcp.md#b06) | [原生](research/competitive/chrome-devtools-mcp.md#b06) | [原生](research/competitive/browser-use.md#b06) | [原生](research/competitive/stagehand.md#b06) | [可选](research/competitive/skyvern.md#b06) | [原生](research/competitive/agent-browser.md#b06) |
| B07 标签页与 popup | [原生](research/competitive/agentproxy.md#b07) | [原生](research/competitive/playwright-mcp.md#b07) | [原生](research/competitive/chrome-devtools-mcp.md#b07) | [原生](research/competitive/browser-use.md#b07) | [原生](research/competitive/stagehand.md#b07) | [原生](research/competitive/skyvern.md#b07) | [原生](research/competitive/agent-browser.md#b07) |
| B08 iframe 操作 | [原生](research/competitive/agentproxy.md#b08) | [原生](research/competitive/playwright-mcp.md#b08) | [部分](research/competitive/chrome-devtools-mcp.md#b08) | [部分](research/competitive/browser-use.md#b08) | [原生](research/competitive/stagehand.md#b08) | [原生](research/competitive/skyvern.md#b08) | [原生](research/competitive/agent-browser.md#b08) |
| B09 导航与历史 | [原生](research/competitive/agentproxy.md#b09) | [原生](research/competitive/playwright-mcp.md#b09) | [原生](research/competitive/chrome-devtools-mcp.md#b09) | [原生](research/competitive/browser-use.md#b09) | [原生](research/competitive/stagehand.md#b09) | [原生](research/competitive/skyvern.md#b09) | [原生](research/competitive/agent-browser.md#b09) |
| B10 点击与指针动作 | [原生](research/competitive/agentproxy.md#b10) | [原生](research/competitive/playwright-mcp.md#b10) | [原生](research/competitive/chrome-devtools-mcp.md#b10) | [原生](research/competitive/browser-use.md#b10) | [原生](research/competitive/stagehand.md#b10) | [原生](research/competitive/skyvern.md#b10) | [原生](research/competitive/agent-browser.md#b10) |
| B11 输入、键盘与表单 | [原生](research/competitive/agentproxy.md#b11) | [原生](research/competitive/playwright-mcp.md#b11) | [原生](research/competitive/chrome-devtools-mcp.md#b11) | [原生](research/competitive/browser-use.md#b11) | [原生](research/competitive/stagehand.md#b11) | [原生](research/competitive/skyvern.md#b11) | [原生](research/competitive/agent-browser.md#b11) |
| B12 拖拽与滚动 | [部分](research/competitive/agentproxy.md#b12) | [原生](research/competitive/playwright-mcp.md#b12) | [原生](research/competitive/chrome-devtools-mcp.md#b12) | [原生](research/competitive/browser-use.md#b12) | [原生](research/competitive/stagehand.md#b12) | [原生](research/competitive/skyvern.md#b12) | [原生](research/competitive/agent-browser.md#b12) |
| B13 原生对话框决策 | [原生](research/competitive/agentproxy.md#b13) | [原生](research/competitive/playwright-mcp.md#b13) | [原生](research/competitive/chrome-devtools-mcp.md#b13) | [未证实](research/competitive/browser-use.md#b13) | [未证实](research/competitive/stagehand.md#b13) | [部分](research/competitive/skyvern.md#b13) | [原生](research/competitive/agent-browser.md#b13) |
| B14 文件上传 | [原生](research/competitive/agentproxy.md#b14) | [原生](research/competitive/playwright-mcp.md#b14) | [原生](research/competitive/chrome-devtools-mcp.md#b14) | [原生](research/competitive/browser-use.md#b14) | [原生](research/competitive/stagehand.md#b14) | [原生](research/competitive/skyvern.md#b14) | [原生](research/competitive/agent-browser.md#b14) |
| B15 下载跟踪与保存 | [原生](research/competitive/agentproxy.md#b15) | [原生](research/competitive/playwright-mcp.md#b15) | [未提供](research/competitive/chrome-devtools-mcp.md#b15) | [原生](research/competitive/browser-use.md#b15) | [部分](research/competitive/stagehand.md#b15) | [原生](research/competitive/skyvern.md#b15) | [原生](research/competitive/agent-browser.md#b15) |
| B16 页面 JavaScript 执行 | [原生](research/competitive/agentproxy.md#b16) | [原生](research/competitive/playwright-mcp.md#b16) | [原生](research/competitive/chrome-devtools-mcp.md#b16) | [原生](research/competitive/browser-use.md#b16) | [原生](research/competitive/stagehand.md#b16) | [原生](research/competitive/skyvern.md#b16) | [原生](research/competitive/agent-browser.md#b16) |
| B17 条件等待 | [原生](research/competitive/agentproxy.md#b17) | [原生](research/competitive/playwright-mcp.md#b17) | [原生](research/competitive/chrome-devtools-mcp.md#b17) | [原生](research/competitive/browser-use.md#b17) | [原生](research/competitive/stagehand.md#b17) | [原生](research/competitive/skyvern.md#b17) | [原生](research/competitive/agent-browser.md#b17) |
| B18 Cookie 管理 | [原生](research/competitive/agentproxy.md#b18) | [可选](research/competitive/playwright-mcp.md#b18) | [未提供](research/competitive/chrome-devtools-mcp.md#b18) | [原生](research/competitive/browser-use.md#b18) | [原生](research/competitive/stagehand.md#b18) | [部分](research/competitive/skyvern.md#b18) | [原生](research/competitive/agent-browser.md#b18) |
| B19 浏览器存储状态导入导出 | [原生](research/competitive/agentproxy.md#b19) | [可选](research/competitive/playwright-mcp.md#b19) | [未提供](research/competitive/chrome-devtools-mcp.md#b19) | [原生](research/competitive/browser-use.md#b19) | [部分](research/competitive/stagehand.md#b19) | [部分](research/competitive/skyvern.md#b19) | [原生](research/competitive/agent-browser.md#b19) |
| B20 设备与环境模拟 | [未提供](research/competitive/agentproxy.md#b20) | [原生](research/competitive/playwright-mcp.md#b20) | [原生](research/competitive/chrome-devtools-mcp.md#b20) | [原生](research/competitive/browser-use.md#b20) | [原生](research/competitive/stagehand.md#b20) | [原生](research/competitive/skyvern.md#b20) | [原生](research/competitive/agent-browser.md#b20) |
| B21 网络离线 / 节流 | [部分](research/competitive/agentproxy.md#b21) | [可选](research/competitive/playwright-mcp.md#b21) | [原生](research/competitive/chrome-devtools-mcp.md#b21) | [未证实](research/competitive/browser-use.md#b21) | [未证实](research/competitive/stagehand.md#b21) | [未证实](research/competitive/skyvern.md#b21) | [部分](research/competitive/agent-browser.md#b21) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| B01 启动受控浏览器 | [原生](research/competitive/agentproxy.md#b01) | [不适用](research/competitive/mitmproxy.md#b01) | [不适用](research/competitive/whistle.md#b01) | [部分](research/competitive/http-toolkit.md#b01) | [可选](research/competitive/zap.md#b01) |
| B02 连接已有浏览器 / CDP | [原生](research/competitive/agentproxy.md#b02) | [不适用](research/competitive/mitmproxy.md#b02) | [不适用](research/competitive/whistle.md#b02) | [部分](research/competitive/http-toolkit.md#b02) | [部分](research/competitive/zap.md#b02) |
| B03 多浏览器引擎 | [未提供](research/competitive/agentproxy.md#b03) | [不适用](research/competitive/mitmproxy.md#b03) | [不适用](research/competitive/whistle.md#b03) | [部分](research/competitive/http-toolkit.md#b03) | [可选](research/competitive/zap.md#b03) |
| B04 headless / headed | [原生](research/competitive/agentproxy.md#b04) | [不适用](research/competitive/mitmproxy.md#b04) | [不适用](research/competitive/whistle.md#b04) | [不适用](research/competitive/http-toolkit.md#b04) | [可选](research/competitive/zap.md#b04) |
| B05 独立会话 / Context | [原生](research/competitive/agentproxy.md#b05) | [不适用](research/competitive/mitmproxy.md#b05) | [不适用](research/competitive/whistle.md#b05) | [部分](research/competitive/http-toolkit.md#b05) | [部分](research/competitive/zap.md#b05) |
| B06 持久用户目录 / 配置 | [部分](research/competitive/agentproxy.md#b06) | [不适用](research/competitive/mitmproxy.md#b06) | [不适用](research/competitive/whistle.md#b06) | [部分](research/competitive/http-toolkit.md#b06) | [部分](research/competitive/zap.md#b06) |
| B07 标签页与 popup | [原生](research/competitive/agentproxy.md#b07) | [不适用](research/competitive/mitmproxy.md#b07) | [不适用](research/competitive/whistle.md#b07) | [不适用](research/competitive/http-toolkit.md#b07) | [未证实](research/competitive/zap.md#b07) |
| B08 iframe 操作 | [原生](research/competitive/agentproxy.md#b08) | [不适用](research/competitive/mitmproxy.md#b08) | [不适用](research/competitive/whistle.md#b08) | [不适用](research/competitive/http-toolkit.md#b08) | [未证实](research/competitive/zap.md#b08) |
| B09 导航与历史 | [原生](research/competitive/agentproxy.md#b09) | [不适用](research/competitive/mitmproxy.md#b09) | [不适用](research/competitive/whistle.md#b09) | [不适用](research/competitive/http-toolkit.md#b09) | [可选](research/competitive/zap.md#b09) |
| B10 点击与指针动作 | [原生](research/competitive/agentproxy.md#b10) | [不适用](research/competitive/mitmproxy.md#b10) | [不适用](research/competitive/whistle.md#b10) | [不适用](research/competitive/http-toolkit.md#b10) | [可选](research/competitive/zap.md#b10) |
| B11 输入、键盘与表单 | [原生](research/competitive/agentproxy.md#b11) | [不适用](research/competitive/mitmproxy.md#b11) | [不适用](research/competitive/whistle.md#b11) | [不适用](research/competitive/http-toolkit.md#b11) | [可选](research/competitive/zap.md#b11) |
| B12 拖拽与滚动 | [部分](research/competitive/agentproxy.md#b12) | [不适用](research/competitive/mitmproxy.md#b12) | [不适用](research/competitive/whistle.md#b12) | [不适用](research/competitive/http-toolkit.md#b12) | [未证实](research/competitive/zap.md#b12) |
| B13 原生对话框决策 | [原生](research/competitive/agentproxy.md#b13) | [不适用](research/competitive/mitmproxy.md#b13) | [不适用](research/competitive/whistle.md#b13) | [不适用](research/competitive/http-toolkit.md#b13) | [未证实](research/competitive/zap.md#b13) |
| B14 文件上传 | [原生](research/competitive/agentproxy.md#b14) | [不适用](research/competitive/mitmproxy.md#b14) | [不适用](research/competitive/whistle.md#b14) | [不适用](research/competitive/http-toolkit.md#b14) | [未证实](research/competitive/zap.md#b14) |
| B15 下载跟踪与保存 | [原生](research/competitive/agentproxy.md#b15) | [不适用](research/competitive/mitmproxy.md#b15) | [不适用](research/competitive/whistle.md#b15) | [不适用](research/competitive/http-toolkit.md#b15) | [未证实](research/competitive/zap.md#b15) |
| B16 页面 JavaScript 执行 | [原生](research/competitive/agentproxy.md#b16) | [不适用](research/competitive/mitmproxy.md#b16) | [部分](research/competitive/whistle.md#b16) | [不适用](research/competitive/http-toolkit.md#b16) | [可选](research/competitive/zap.md#b16) |
| B17 条件等待 | [原生](research/competitive/agentproxy.md#b17) | [不适用](research/competitive/mitmproxy.md#b17) | [不适用](research/competitive/whistle.md#b17) | [不适用](research/competitive/http-toolkit.md#b17) | [部分](research/competitive/zap.md#b17) |
| B18 Cookie 管理 | [原生](research/competitive/agentproxy.md#b18) | [不适用](research/competitive/mitmproxy.md#b18) | [不适用](research/competitive/whistle.md#b18) | [不适用](research/competitive/http-toolkit.md#b18) | [部分](research/competitive/zap.md#b18) |
| B19 浏览器存储状态导入导出 | [原生](research/competitive/agentproxy.md#b19) | [不适用](research/competitive/mitmproxy.md#b19) | [不适用](research/competitive/whistle.md#b19) | [不适用](research/competitive/http-toolkit.md#b19) | [未证实](research/competitive/zap.md#b19) |
| B20 设备与环境模拟 | [未提供](research/competitive/agentproxy.md#b20) | [不适用](research/competitive/mitmproxy.md#b20) | [不适用](research/competitive/whistle.md#b20) | [不适用](research/competitive/http-toolkit.md#b20) | [未证实](research/competitive/zap.md#b20) |
| B21 网络离线 / 节流 | [部分](research/competitive/agentproxy.md#b21) | [部分](research/competitive/mitmproxy.md#b21) | [原生](research/competitive/whistle.md#b21) | [付费](research/competitive/http-toolkit.md#b21) | [部分](research/competitive/zap.md#b21) |

本组口径：B01：正式入口可创建并控制浏览器；B02：连接已运行浏览器并保留其状态；B03：公开支持 Chromium 之外的引擎；Chrome渠道不算独立引擎；B04：控制浏览器有头和无头模式；B05：隔离多个浏览器会话或上下文；B06：复用用户数据目录或显式持久配置；B07：列出、选择、创建或关闭标签页并处理新窗口；B08：公开 frame 选择、引用或等效交互能力；B09：URL 导航、前后退或刷新；B10：点击、双击、hover 或坐标指针能力，细节在项目清单；B11：填写、逐字输入、按键、下拉选择等；B12：正式入口提供拖拽或页面/元素滚动；B13：alert/confirm/prompt 等显式处理；B14：公开文件选择/上传动作，不用任意JS推测；B15：下载等待、状态、保存路径等正式能力；B16：公开 evaluate / execute_js 等页面执行入口；B17：等待元素、文本、页面状态或条件；B18：读取、设置或清理浏览器 Cookie；B19：storageState、cookie/storage/session 等明确持久接口；B20：viewport、设备、地理位置、权限、颜色或时区等正式配置；B21：浏览器或网络层模拟离线、延迟和速率，范围另述。

### 页面观察与定位

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| O01 ARIA / 无障碍快照 | [原生](research/competitive/agentproxy.md#o01) | [原生](research/competitive/playwright-mcp.md#o01) | [原生](research/competitive/chrome-devtools-mcp.md#o01) | [可选](research/competitive/browser-use.md#o01) | [原生](research/competitive/stagehand.md#o01) | [部分](research/competitive/skyvern.md#o01) | [原生](research/competitive/agent-browser.md#o01) |
| O02 元素引用 refs | [原生](research/competitive/agentproxy.md#o02) | [原生](research/competitive/playwright-mcp.md#o02) | [原生](research/competitive/chrome-devtools-mcp.md#o02) | [原生](research/competitive/browser-use.md#o02) | [原生](research/competitive/stagehand.md#o02) | [原生](research/competitive/skyvern.md#o02) | [原生](research/competitive/agent-browser.md#o02) |
| O03 增量快照 / 差异输出 | [原生](research/competitive/agentproxy.md#o03) | [未提供](research/competitive/playwright-mcp.md#o03) | [未提供](research/competitive/chrome-devtools-mcp.md#o03) | [未证实](research/competitive/browser-use.md#o03) | [未提供](research/competitive/stagehand.md#o03) | [未证实](research/competitive/skyvern.md#o03) | [原生](research/competitive/agent-browser.md#o03) |
| O04 快照搜索、裁剪或过滤 | [部分](research/competitive/agentproxy.md#o04) | [原生](research/competitive/playwright-mcp.md#o04) | [部分](research/competitive/chrome-devtools-mcp.md#o04) | [原生](research/competitive/browser-use.md#o04) | [原生](research/competitive/stagehand.md#o04) | [原生](research/competitive/skyvern.md#o04) | [原生](research/competitive/agent-browser.md#o04) |
| O05 过期引用合同 | [原生](research/competitive/agentproxy.md#o05) | [原生](research/competitive/playwright-mcp.md#o05) | [部分](research/competitive/chrome-devtools-mcp.md#o05) | [可选](research/competitive/browser-use.md#o05) | [部分](research/competitive/stagehand.md#o05) | [原生](research/competitive/skyvern.md#o05) | [原生](research/competitive/agent-browser.md#o05) |
| O06 页面 / 元素截图 | [部分](research/competitive/agentproxy.md#o06) | [原生](research/competitive/playwright-mcp.md#o06) | [原生](research/competitive/chrome-devtools-mcp.md#o06) | [原生](research/competitive/browser-use.md#o06) | [原生](research/competitive/stagehand.md#o06) | [原生](research/competitive/skyvern.md#o06) | [原生](research/competitive/agent-browser.md#o06) |
| O07 标注截图 / 视觉定位 | [未提供](research/competitive/agentproxy.md#o07) | [可选](research/competitive/playwright-mcp.md#o07) | [可选](research/competitive/chrome-devtools-mcp.md#o07) | [原生](research/competitive/browser-use.md#o07) | [原生](research/competitive/stagehand.md#o07) | [原生](research/competitive/skyvern.md#o07) | [原生](research/competitive/agent-browser.md#o07) |
| O08 HTML / DOM / 文本读取 | [原生](research/competitive/agentproxy.md#o08) | [部分](research/competitive/playwright-mcp.md#o08) | [部分](research/competitive/chrome-devtools-mcp.md#o08) | [原生](research/competitive/browser-use.md#o08) | [原生](research/competitive/stagehand.md#o08) | [原生](research/competitive/skyvern.md#o08) | [原生](research/competitive/agent-browser.md#o08) |
| O09 Schema 约束结构化提取 | [部分](research/competitive/agentproxy.md#o09) | [未提供](research/competitive/playwright-mcp.md#o09) | [未提供](research/competitive/chrome-devtools-mcp.md#o09) | [原生](research/competitive/browser-use.md#o09) | [原生](research/competitive/stagehand.md#o09) | [原生](research/competitive/skyvern.md#o09) | [未提供](research/competitive/agent-browser.md#o09) |
| O10 自然语言定位 / act | [未提供](research/competitive/agentproxy.md#o10) | [未提供](research/competitive/playwright-mcp.md#o10) | [未提供](research/competitive/chrome-devtools-mcp.md#o10) | [原生](research/competitive/browser-use.md#o10) | [原生](research/competitive/stagehand.md#o10) | [原生](research/competitive/skyvern.md#o10) | [云端](research/competitive/agent-browser.md#o10) |
| O11 定位自适应 / 恢复 | [未提供](research/competitive/agentproxy.md#o11) | [未提供](research/competitive/playwright-mcp.md#o11) | [未提供](research/competitive/chrome-devtools-mcp.md#o11) | [原生](research/competitive/browser-use.md#o11) | [原生](research/competitive/stagehand.md#o11) | [原生](research/competitive/skyvern.md#o11) | [部分](research/competitive/agent-browser.md#o11) |
| O12 页面 PDF 导出 | [未提供](research/competitive/agentproxy.md#o12) | [可选](research/competitive/playwright-mcp.md#o12) | [未提供](research/competitive/chrome-devtools-mcp.md#o12) | [原生](research/competitive/browser-use.md#o12) | [原生](research/competitive/stagehand.md#o12) | [原生](research/competitive/skyvern.md#o12) | [原生](research/competitive/agent-browser.md#o12) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| O01 ARIA / 无障碍快照 | [原生](research/competitive/agentproxy.md#o01) | [不适用](research/competitive/mitmproxy.md#o01) | [不适用](research/competitive/whistle.md#o01) | [不适用](research/competitive/http-toolkit.md#o01) | [不适用](research/competitive/zap.md#o01) |
| O02 元素引用 refs | [原生](research/competitive/agentproxy.md#o02) | [不适用](research/competitive/mitmproxy.md#o02) | [不适用](research/competitive/whistle.md#o02) | [不适用](research/competitive/http-toolkit.md#o02) | [不适用](research/competitive/zap.md#o02) |
| O03 增量快照 / 差异输出 | [原生](research/competitive/agentproxy.md#o03) | [不适用](research/competitive/mitmproxy.md#o03) | [不适用](research/competitive/whistle.md#o03) | [不适用](research/competitive/http-toolkit.md#o03) | [部分](research/competitive/zap.md#o03) |
| O04 快照搜索、裁剪或过滤 | [部分](research/competitive/agentproxy.md#o04) | [不适用](research/competitive/mitmproxy.md#o04) | [不适用](research/competitive/whistle.md#o04) | [不适用](research/competitive/http-toolkit.md#o04) | [未证实](research/competitive/zap.md#o04) |
| O05 过期引用合同 | [原生](research/competitive/agentproxy.md#o05) | [不适用](research/competitive/mitmproxy.md#o05) | [不适用](research/competitive/whistle.md#o05) | [不适用](research/competitive/http-toolkit.md#o05) | [不适用](research/competitive/zap.md#o05) |
| O06 页面 / 元素截图 | [部分](research/competitive/agentproxy.md#o06) | [不适用](research/competitive/mitmproxy.md#o06) | [不适用](research/competitive/whistle.md#o06) | [不适用](research/competitive/http-toolkit.md#o06) | [未证实](research/competitive/zap.md#o06) |
| O07 标注截图 / 视觉定位 | [未提供](research/competitive/agentproxy.md#o07) | [不适用](research/competitive/mitmproxy.md#o07) | [不适用](research/competitive/whistle.md#o07) | [不适用](research/competitive/http-toolkit.md#o07) | [未证实](research/competitive/zap.md#o07) |
| O08 HTML / DOM / 文本读取 | [原生](research/competitive/agentproxy.md#o08) | [不适用](research/competitive/mitmproxy.md#o08) | [部分](research/competitive/whistle.md#o08) | [部分](research/competitive/http-toolkit.md#o08) | [可选](research/competitive/zap.md#o08) |
| O09 Schema 约束结构化提取 | [部分](research/competitive/agentproxy.md#o09) | [不适用](research/competitive/mitmproxy.md#o09) | [不适用](research/competitive/whistle.md#o09) | [不适用](research/competitive/http-toolkit.md#o09) | [未证实](research/competitive/zap.md#o09) |
| O10 自然语言定位 / act | [未提供](research/competitive/agentproxy.md#o10) | [不适用](research/competitive/mitmproxy.md#o10) | [不适用](research/competitive/whistle.md#o10) | [不适用](research/competitive/http-toolkit.md#o10) | [部分](research/competitive/zap.md#o10) |
| O11 定位自适应 / 恢复 | [未提供](research/competitive/agentproxy.md#o11) | [不适用](research/competitive/mitmproxy.md#o11) | [不适用](research/competitive/whistle.md#o11) | [不适用](research/competitive/http-toolkit.md#o11) | [未证实](research/competitive/zap.md#o11) |
| O12 页面 PDF 导出 | [未提供](research/competitive/agentproxy.md#o12) | [不适用](research/competitive/mitmproxy.md#o12) | [不适用](research/competitive/whistle.md#o12) | [不适用](research/competitive/http-toolkit.md#o12) | [不适用](research/competitive/zap.md#o12) |

本组口径：O01：结构化可访问性页面表示；O02：观察后用元素标识精确操作；O03：对上一基线提供页面增量，而非只有全量快照；O04：按查询、子树、深度或交互性缩小观察结果；O05：明确拒绝、更新或按已公开规则恢复旧元素引用；O06：可获取页面或元素图像；O07：标注元素或直接基于视觉/坐标理解和操作；O08：正式读取页面结构、HTML或文本；O09：依据 schema 输出页面数据；普通JSONPath提取需注明不同范围；O10：产品自身把自然语言映射到页面动作，不依赖外部Agent自行规划；O11：元素变化后有已公开的语义或视觉定位恢复机制；O12：把页面打印或导出为PDF，区别于捕获下载附件。

### 代理与网络捕获

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| N01 独立代理捕获外部客户端 | [原生](research/competitive/agentproxy.md#n01) | [不适用](research/competitive/playwright-mcp.md#n01) | [不适用](research/competitive/chrome-devtools-mcp.md#n01) | [不适用](research/competitive/browser-use.md#n01) | [不适用](research/competitive/stagehand.md#n01) | [不适用](research/competitive/skyvern.md#n01) | [不适用](research/competitive/agent-browser.md#n01) |
| N02 HTTPS 解密与 CA | [原生](research/competitive/agentproxy.md#n02) | [不适用](research/competitive/playwright-mcp.md#n02) | [不适用](research/competitive/chrome-devtools-mcp.md#n02) | [不适用](research/competitive/browser-use.md#n02) | [不适用](research/competitive/stagehand.md#n02) | [不适用](research/competitive/skyvern.md#n02) | [不适用](research/competitive/agent-browser.md#n02) |
| N03 HTTP/2 支持 | [部分](research/competitive/agentproxy.md#n03) | [未证实](research/competitive/playwright-mcp.md#n03) | [未证实](research/competitive/chrome-devtools-mcp.md#n03) | [部分](research/competitive/browser-use.md#n03) | [部分](research/competitive/stagehand.md#n03) | [部分](research/competitive/skyvern.md#n03) | [未证实](research/competitive/agent-browser.md#n03) |
| N04 HTTP/3 / QUIC 支持 | [未提供](research/competitive/agentproxy.md#n04) | [未证实](research/competitive/playwright-mcp.md#n04) | [未证实](research/competitive/chrome-devtools-mcp.md#n04) | [不适用](research/competitive/browser-use.md#n04) | [不适用](research/competitive/stagehand.md#n04) | [不适用](research/competitive/skyvern.md#n04) | [未证实](research/competitive/agent-browser.md#n04) |
| N05 TCP / UDP 非 HTTP 流量 | [未提供](research/competitive/agentproxy.md#n05) | [不适用](research/competitive/playwright-mcp.md#n05) | [不适用](research/competitive/chrome-devtools-mcp.md#n05) | [不适用](research/competitive/browser-use.md#n05) | [不适用](research/competitive/stagehand.md#n05) | [不适用](research/competitive/skyvern.md#n05) | [不适用](research/competitive/agent-browser.md#n05) |
| N06 代理模式与上游链路 | [部分](research/competitive/agentproxy.md#n06) | [部分](research/competitive/playwright-mcp.md#n06) | [部分](research/competitive/chrome-devtools-mcp.md#n06) | [不适用](research/competitive/browser-use.md#n06) | [不适用](research/competitive/stagehand.md#n06) | [不适用](research/competitive/skyvern.md#n06) | [部分](research/competitive/agent-browser.md#n06) |
| N07 请求 / 响应详情 | [原生](research/competitive/agentproxy.md#n07) | [原生](research/competitive/playwright-mcp.md#n07) | [原生](research/competitive/chrome-devtools-mcp.md#n07) | [部分](research/competitive/browser-use.md#n07) | [部分](research/competitive/stagehand.md#n07) | [部分](research/competitive/skyvern.md#n07) | [原生](research/competitive/agent-browser.md#n07) |
| N08 搜索、过滤与范围 | [原生](research/competitive/agentproxy.md#n08) | [原生](research/competitive/playwright-mcp.md#n08) | [原生](research/competitive/chrome-devtools-mcp.md#n08) | [部分](research/competitive/browser-use.md#n08) | [部分](research/competitive/stagehand.md#n08) | [部分](research/competitive/skyvern.md#n08) | [原生](research/competitive/agent-browser.md#n08) |
| N09 多值 / 有序响应头 | [原生](research/competitive/agentproxy.md#n09) | [未证实](research/competitive/playwright-mcp.md#n09) | [未证实](research/competitive/chrome-devtools-mcp.md#n09) | [未证实](research/competitive/browser-use.md#n09) | [部分](research/competitive/stagehand.md#n09) | [未证实](research/competitive/skyvern.md#n09) | [部分](research/competitive/agent-browser.md#n09) |
| N10 正文解码与格式展示 | [原生](research/competitive/agentproxy.md#n10) | [部分](research/competitive/playwright-mcp.md#n10) | [部分](research/competitive/chrome-devtools-mcp.md#n10) | [未证实](research/competitive/browser-use.md#n10) | [部分](research/competitive/stagehand.md#n10) | [部分](research/competitive/skyvern.md#n10) | [部分](research/competitive/agent-browser.md#n10) |
| N11 请求 / 响应修改与 mock | [部分](research/competitive/agentproxy.md#n11) | [可选](research/competitive/playwright-mcp.md#n11) | [未提供](research/competitive/chrome-devtools-mcp.md#n11) | [未证实](research/competitive/browser-use.md#n11) | [未证实](research/competitive/stagehand.md#n11) | [部分](research/competitive/skyvern.md#n11) | [原生](research/competitive/agent-browser.md#n11) |
| N12 断点与手动继续 | [未提供](research/competitive/agentproxy.md#n12) | [未提供](research/competitive/playwright-mcp.md#n12) | [未提供](research/competitive/chrome-devtools-mcp.md#n12) | [未证实](research/competitive/browser-use.md#n12) | [未证实](research/competitive/stagehand.md#n12) | [未证实](research/competitive/skyvern.md#n12) | [未提供](research/competitive/agent-browser.md#n12) |
| N13 请求编辑与重发 | [原生](research/competitive/agentproxy.md#n13) | [未提供](research/competitive/playwright-mcp.md#n13) | [未提供](research/competitive/chrome-devtools-mcp.md#n13) | [未证实](research/competitive/browser-use.md#n13) | [未证实](research/competitive/stagehand.md#n13) | [未证实](research/competitive/skyvern.md#n13) | [未提供](research/competitive/agent-browser.md#n13) |
| N14 浏览器网络路由 / mock | [未提供](research/competitive/agentproxy.md#n14) | [可选](research/competitive/playwright-mcp.md#n14) | [未提供](research/competitive/chrome-devtools-mcp.md#n14) | [未证实](research/competitive/browser-use.md#n14) | [未证实](research/competitive/stagehand.md#n14) | [部分](research/competitive/skyvern.md#n14) | [原生](research/competitive/agent-browser.md#n14) |
| N15 HAR 导入 / 导出 | [未提供](research/competitive/agentproxy.md#n15) | [未提供](research/competitive/playwright-mcp.md#n15) | [未提供](research/competitive/chrome-devtools-mcp.md#n15) | [部分](research/competitive/browser-use.md#n15) | [未证实](research/competitive/stagehand.md#n15) | [部分](research/competitive/skyvern.md#n15) | [部分](research/competitive/agent-browser.md#n15) |
| N16 cURL / 客户端代码导出 | [原生](research/competitive/agentproxy.md#n16) | [未提供](research/competitive/playwright-mcp.md#n16) | [未提供](research/competitive/chrome-devtools-mcp.md#n16) | [未证实](research/competitive/browser-use.md#n16) | [未证实](research/competitive/stagehand.md#n16) | [未证实](research/competitive/skyvern.md#n16) | [部分](research/competitive/agent-browser.md#n16) |
| N17 API 结构 / OpenAPI | [部分](research/competitive/agentproxy.md#n17) | [未提供](research/competitive/playwright-mcp.md#n17) | [未提供](research/competitive/chrome-devtools-mcp.md#n17) | [未证实](research/competitive/browser-use.md#n17) | [未证实](research/competitive/stagehand.md#n17) | [未证实](research/competitive/skyvern.md#n17) | [未提供](research/competitive/agent-browser.md#n17) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| N01 独立代理捕获外部客户端 | [原生](research/competitive/agentproxy.md#n01) | [原生](research/competitive/mitmproxy.md#n01) | [原生](research/competitive/whistle.md#n01) | [原生](research/competitive/http-toolkit.md#n01) | [原生](research/competitive/zap.md#n01) |
| N02 HTTPS 解密与 CA | [原生](research/competitive/agentproxy.md#n02) | [原生](research/competitive/mitmproxy.md#n02) | [原生](research/competitive/whistle.md#n02) | [原生](research/competitive/http-toolkit.md#n02) | [原生](research/competitive/zap.md#n02) |
| N03 HTTP/2 支持 | [部分](research/competitive/agentproxy.md#n03) | [部分](research/competitive/mitmproxy.md#n03) | [原生](research/competitive/whistle.md#n03) | [原生](research/competitive/http-toolkit.md#n03) | [原生](research/competitive/zap.md#n03) |
| N04 HTTP/3 / QUIC 支持 | [未提供](research/competitive/agentproxy.md#n04) | [部分](research/competitive/mitmproxy.md#n04) | [未证实](research/competitive/whistle.md#n04) | [未证实](research/competitive/http-toolkit.md#n04) | [未证实](research/competitive/zap.md#n04) |
| N05 TCP / UDP 非 HTTP 流量 | [未提供](research/competitive/agentproxy.md#n05) | [部分](research/competitive/mitmproxy.md#n05) | [部分](research/competitive/whistle.md#n05) | [未证实](research/competitive/http-toolkit.md#n05) | [未证实](research/competitive/zap.md#n05) |
| N06 代理模式与上游链路 | [部分](research/competitive/agentproxy.md#n06) | [原生](research/competitive/mitmproxy.md#n06) | [原生](research/competitive/whistle.md#n06) | [部分](research/competitive/http-toolkit.md#n06) | [原生](research/competitive/zap.md#n06) |
| N07 请求 / 响应详情 | [原生](research/competitive/agentproxy.md#n07) | [原生](research/competitive/mitmproxy.md#n07) | [原生](research/competitive/whistle.md#n07) | [原生](research/competitive/http-toolkit.md#n07) | [原生](research/competitive/zap.md#n07) |
| N08 搜索、过滤与范围 | [原生](research/competitive/agentproxy.md#n08) | [原生](research/competitive/mitmproxy.md#n08) | [原生](research/competitive/whistle.md#n08) | [原生](research/competitive/http-toolkit.md#n08) | [原生](research/competitive/zap.md#n08) |
| N09 多值 / 有序响应头 | [原生](research/competitive/agentproxy.md#n09) | [原生](research/competitive/mitmproxy.md#n09) | [未证实](research/competitive/whistle.md#n09) | [未证实](research/competitive/http-toolkit.md#n09) | [未证实](research/competitive/zap.md#n09) |
| N10 正文解码与格式展示 | [原生](research/competitive/agentproxy.md#n10) | [原生](research/competitive/mitmproxy.md#n10) | [部分](research/competitive/whistle.md#n10) | [原生](research/competitive/http-toolkit.md#n10) | [部分](research/competitive/zap.md#n10) |
| N11 请求 / 响应修改与 mock | [部分](research/competitive/agentproxy.md#n11) | [原生](research/competitive/mitmproxy.md#n11) | [原生](research/competitive/whistle.md#n11) | [部分](research/competitive/http-toolkit.md#n11) | [可选](research/competitive/zap.md#n11) |
| N12 断点与手动继续 | [未提供](research/competitive/agentproxy.md#n12) | [原生](research/competitive/mitmproxy.md#n12) | [部分](research/competitive/whistle.md#n12) | [原生](research/competitive/http-toolkit.md#n12) | [原生](research/competitive/zap.md#n12) |
| N13 请求编辑与重发 | [原生](research/competitive/agentproxy.md#n13) | [原生](research/competitive/mitmproxy.md#n13) | [原生](research/competitive/whistle.md#n13) | [部分](research/competitive/http-toolkit.md#n13) | [原生](research/competitive/zap.md#n13) |
| N14 浏览器网络路由 / mock | [未提供](research/competitive/agentproxy.md#n14) | [不适用](research/competitive/mitmproxy.md#n14) | [不适用](research/competitive/whistle.md#n14) | [不适用](research/competitive/http-toolkit.md#n14) | [不适用](research/competitive/zap.md#n14) |
| N15 HAR 导入 / 导出 | [未提供](research/competitive/agentproxy.md#n15) | [部分](research/competitive/mitmproxy.md#n15) | [未证实](research/competitive/whistle.md#n15) | [付费](research/competitive/http-toolkit.md#n15) | [可选](research/competitive/zap.md#n15) |
| N16 cURL / 客户端代码导出 | [原生](research/competitive/agentproxy.md#n16) | [原生](research/competitive/mitmproxy.md#n16) | [原生](research/competitive/whistle.md#n16) | [付费](research/competitive/http-toolkit.md#n16) | [未证实](research/competitive/zap.md#n16) |
| N17 API 结构 / OpenAPI | [部分](research/competitive/agentproxy.md#n17) | [未证实](research/competitive/mitmproxy.md#n17) | [未证实](research/competitive/whistle.md#n17) | [付费](research/competitive/http-toolkit.md#n17) | [可选](research/competitive/zap.md#n17) |

本组口径：N01：无需受控浏览器即可捕获客户端流量；N02：正式MITM证书及HTTPS解密能力；N03：注明原生代理、浏览器后端继承或限制；N04：实际公开运行模式支持，不能只从底层库推断；N05：公开支持非HTTP数据流；N06：regular/reverse/transparent/SOCKS/tunnel/upstream等模式；N07：头、状态、正文等按请求读取；N08：按URL/域名/方法/正文等筛选，范围需说明；N09：公开保存或访问重复头的语义；N10：压缩、字符集、JSON/二进制等可读展示；N11：规则或API修改已捕获请求响应、构造本地回应；N12：暂停流量，人工或API决定继续；N13：显式发送、编辑或重放单个请求；N14：浏览器层route等接口，区别于独立代理规则；N15：注明读写方向与付费边界；N16：捕获请求转换为可复用客户端表示；N17：API模式聚合、OpenAPI导入导出或识别，方向需注明。

### 实时消息

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| M01 WebSocket 消息查看 | [原生](research/competitive/agentproxy.md#m01) | [未证实](research/competitive/playwright-mcp.md#m01) | [未证实](research/competitive/chrome-devtools-mcp.md#m01) | [未证实](research/competitive/browser-use.md#m01) | [未证实](research/competitive/stagehand.md#m01) | [未证实](research/competitive/skyvern.md#m01) | [未证实](research/competitive/agent-browser.md#m01) |
| M02 WebSocket 双向 / 二进制 | [原生](research/competitive/agentproxy.md#m02) | [未证实](research/competitive/playwright-mcp.md#m02) | [未证实](research/competitive/chrome-devtools-mcp.md#m02) | [未证实](research/competitive/browser-use.md#m02) | [未证实](research/competitive/stagehand.md#m02) | [未证实](research/competitive/skyvern.md#m02) | [未证实](research/competitive/agent-browser.md#m02) |
| M03 WebSocket 修改 / 注入 | [未提供](research/competitive/agentproxy.md#m03) | [未证实](research/competitive/playwright-mcp.md#m03) | [未证实](research/competitive/chrome-devtools-mcp.md#m03) | [未证实](research/competitive/browser-use.md#m03) | [未证实](research/competitive/stagehand.md#m03) | [未证实](research/competitive/skyvern.md#m03) | [未证实](research/competitive/agent-browser.md#m03) |
| M04 SSE 事件级解析 | [原生](research/competitive/agentproxy.md#m04) | [未证实](research/competitive/playwright-mcp.md#m04) | [未证实](research/competitive/chrome-devtools-mcp.md#m04) | [未证实](research/competitive/browser-use.md#m04) | [未证实](research/competitive/stagehand.md#m04) | [未证实](research/competitive/skyvern.md#m04) | [未证实](research/competitive/agent-browser.md#m04) |
| M05 压缩 SSE 增量解析 | [原生](research/competitive/agentproxy.md#m05) | [未证实](research/competitive/playwright-mcp.md#m05) | [未证实](research/competitive/chrome-devtools-mcp.md#m05) | [未证实](research/competitive/browser-use.md#m05) | [未证实](research/competitive/stagehand.md#m05) | [未证实](research/competitive/skyvern.md#m05) | [未证实](research/competitive/agent-browser.md#m05) |
| M06 开放连接期间查询消息 | [原生](research/competitive/agentproxy.md#m06) | [未证实](research/competitive/playwright-mcp.md#m06) | [未证实](research/competitive/chrome-devtools-mcp.md#m06) | [未证实](research/competitive/browser-use.md#m06) | [未证实](research/competitive/stagehand.md#m06) | [未证实](research/competitive/skyvern.md#m06) | [未证实](research/competitive/agent-browser.md#m06) |
| M07 消息持久化与增量游标 | [原生](research/competitive/agentproxy.md#m07) | [未证实](research/competitive/playwright-mcp.md#m07) | [未证实](research/competitive/chrome-devtools-mcp.md#m07) | [未证实](research/competitive/browser-use.md#m07) | [未证实](research/competitive/stagehand.md#m07) | [未证实](research/competitive/skyvern.md#m07) | [未证实](research/competitive/agent-browser.md#m07) |
| M08 消息完整性 / 截断标记 | [原生](research/competitive/agentproxy.md#m08) | [未证实](research/competitive/playwright-mcp.md#m08) | [未证实](research/competitive/chrome-devtools-mcp.md#m08) | [未证实](research/competitive/browser-use.md#m08) | [未证实](research/competitive/stagehand.md#m08) | [未证实](research/competitive/skyvern.md#m08) | [未证实](research/competitive/agent-browser.md#m08) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| M01 WebSocket 消息查看 | [原生](research/competitive/agentproxy.md#m01) | [原生](research/competitive/mitmproxy.md#m01) | [原生](research/competitive/whistle.md#m01) | [原生](research/competitive/http-toolkit.md#m01) | [可选](research/competitive/zap.md#m01) |
| M02 WebSocket 双向 / 二进制 | [原生](research/competitive/agentproxy.md#m02) | [原生](research/competitive/mitmproxy.md#m02) | [原生](research/competitive/whistle.md#m02) | [原生](research/competitive/http-toolkit.md#m02) | [可选](research/competitive/zap.md#m02) |
| M03 WebSocket 修改 / 注入 | [未提供](research/competitive/agentproxy.md#m03) | [原生](research/competitive/mitmproxy.md#m03) | [原生](research/competitive/whistle.md#m03) | [部分](research/competitive/http-toolkit.md#m03) | [可选](research/competitive/zap.md#m03) |
| M04 SSE 事件级解析 | [原生](research/competitive/agentproxy.md#m04) | [未证实](research/competitive/mitmproxy.md#m04) | [未证实](research/competitive/whistle.md#m04) | [部分](research/competitive/http-toolkit.md#m04) | [可选](research/competitive/zap.md#m04) |
| M05 压缩 SSE 增量解析 | [原生](research/competitive/agentproxy.md#m05) | [未证实](research/competitive/mitmproxy.md#m05) | [未证实](research/competitive/whistle.md#m05) | [未提供](research/competitive/http-toolkit.md#m05) | [未证实](research/competitive/zap.md#m05) |
| M06 开放连接期间查询消息 | [原生](research/competitive/agentproxy.md#m06) | [原生](research/competitive/mitmproxy.md#m06) | [原生](research/competitive/whistle.md#m06) | [原生](research/competitive/http-toolkit.md#m06) | [可选](research/competitive/zap.md#m06) |
| M07 消息持久化与增量游标 | [原生](research/competitive/agentproxy.md#m07) | [部分](research/competitive/mitmproxy.md#m07) | [部分](research/competitive/whistle.md#m07) | [部分](research/competitive/http-toolkit.md#m07) | [部分](research/competitive/zap.md#m07) |
| M08 消息完整性 / 截断标记 | [原生](research/competitive/agentproxy.md#m08) | [部分](research/competitive/mitmproxy.md#m08) | [未证实](research/competitive/whistle.md#m08) | [部分](research/competitive/http-toolkit.md#m08) | [部分](research/competitive/zap.md#m08) |

本组口径：M01：查看应用消息，不只HTTP握手；M02：方向与二进制消息有明确表达；M03：产品已公开消息修改/发送能力，仅比较存在性；M04：按事件解析id/event/data，不以网络chunk代替；M05：明确可在连接开放时解压并解析事件；M06：未关闭连接即能读取已到达应用消息；M07：持久消息记录和可续读标识，两者范围需说明；M08：对截断、解码失败或不完整尾部有可查询元数据。

### Agent 与多步任务

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| W01 内置模型驱动执行循环 | [未提供](research/competitive/agentproxy.md#w01) | [未提供](research/competitive/playwright-mcp.md#w01) | [未提供](research/competitive/chrome-devtools-mcp.md#w01) | [原生](research/competitive/browser-use.md#w01) | [未提供](research/competitive/stagehand.md#w01) | [原生](research/competitive/skyvern.md#w01) | [云端](research/competitive/agent-browser.md#w01) |
| W02 多模型 / 自定义模型 | [不适用](research/competitive/agentproxy.md#w02) | [不适用](research/competitive/playwright-mcp.md#w02) | [不适用](research/competitive/chrome-devtools-mcp.md#w02) | [原生](research/competitive/browser-use.md#w02) | [原生](research/competitive/stagehand.md#w02) | [原生](research/competitive/skyvern.md#w02) | [云端](research/competitive/agent-browser.md#w02) |
| W03 用户自定义工具 / 动作 | [部分](research/competitive/agentproxy.md#w03) | [部分](research/competitive/playwright-mcp.md#w03) | [可选](research/competitive/chrome-devtools-mcp.md#w03) | [原生](research/competitive/browser-use.md#w03) | [部分](research/competitive/stagehand.md#w03) | [部分](research/competitive/skyvern.md#w03) | [可选](research/competitive/agent-browser.md#w03) |
| W04 多步骤工作流定义 | [部分](research/competitive/agentproxy.md#w04) | [未证实](research/competitive/playwright-mcp.md#w04) | [未证实](research/competitive/chrome-devtools-mcp.md#w04) | [部分](research/competitive/browser-use.md#w04) | [部分](research/competitive/stagehand.md#w04) | [原生](research/competitive/skyvern.md#w04) | [原生](research/competitive/agent-browser.md#w04) |
| W05 条件、循环与并行 | [未提供](research/competitive/agentproxy.md#w05) | [未证实](research/competitive/playwright-mcp.md#w05) | [未证实](research/competitive/chrome-devtools-mcp.md#w05) | [未提供](research/competitive/browser-use.md#w05) | [未提供](research/competitive/stagehand.md#w05) | [部分](research/competitive/skyvern.md#w05) | [未提供](research/competitive/agent-browser.md#w05) |
| W06 人工接管 / 审批节点 | [部分](research/competitive/agentproxy.md#w06) | [可选](research/competitive/playwright-mcp.md#w06) | [部分](research/competitive/chrome-devtools-mcp.md#w06) | [部分](research/competitive/browser-use.md#w06) | [部分](research/competitive/stagehand.md#w06) | [原生](research/competitive/skyvern.md#w06) | [原生](research/competitive/agent-browser.md#w06) |
| W07 任务结果验证 | [未提供](research/competitive/agentproxy.md#w07) | [部分](research/competitive/playwright-mcp.md#w07) | [部分](research/competitive/chrome-devtools-mcp.md#w07) | [原生](research/competitive/browser-use.md#w07) | [部分](research/competitive/stagehand.md#w07) | [原生](research/competitive/skyvern.md#w07) | [部分](research/competitive/agent-browser.md#w07) |
| W08 步骤历史 / 动作回执 | [部分](research/competitive/agentproxy.md#w08) | [部分](research/competitive/playwright-mcp.md#w08) | [部分](research/competitive/chrome-devtools-mcp.md#w08) | [原生](research/competitive/browser-use.md#w08) | [部分](research/competitive/stagehand.md#w08) | [原生](research/competitive/skyvern.md#w08) | [原生](research/competitive/agent-browser.md#w08) |
| W09 自动步骤检查点 | [部分](research/competitive/agentproxy.md#w09) | [未证实](research/competitive/playwright-mcp.md#w09) | [未证实](research/competitive/chrome-devtools-mcp.md#w09) | [未证实](research/competitive/browser-use.md#w09) | [未证实](research/competitive/stagehand.md#w09) | [部分](research/competitive/skyvern.md#w09) | [部分](research/competitive/agent-browser.md#w09) |
| W10 跨进程恢复 / 状态重绑 | [部分](research/competitive/agentproxy.md#w10) | [部分](research/competitive/playwright-mcp.md#w10) | [部分](research/competitive/chrome-devtools-mcp.md#w10) | [部分](research/competitive/browser-use.md#w10) | [部分](research/competitive/stagehand.md#w10) | [部分](research/competitive/skyvern.md#w10) | [原生](research/competitive/agent-browser.md#w10) |
| W11 未知结果处理 / 防重复执行 | [部分](research/competitive/agentproxy.md#w11) | [未证实](research/competitive/playwright-mcp.md#w11) | [未证实](research/competitive/chrome-devtools-mcp.md#w11) | [部分](research/competitive/browser-use.md#w11) | [部分](research/competitive/stagehand.md#w11) | [部分](research/competitive/skyvern.md#w11) | [原生](research/competitive/agent-browser.md#w11) |
| W12 历史重放 / 动作缓存 | [未提供](research/competitive/agentproxy.md#w12) | [部分](research/competitive/playwright-mcp.md#w12) | [未证实](research/competitive/chrome-devtools-mcp.md#w12) | [原生](research/competitive/browser-use.md#w12) | [云端](research/competitive/stagehand.md#w12) | [原生](research/competitive/skyvern.md#w12) | [部分](research/competitive/agent-browser.md#w12) |
| W13 凭据 / 登录辅助 | [部分](research/competitive/agentproxy.md#w13) | [原生](research/competitive/playwright-mcp.md#w13) | [部分](research/competitive/chrome-devtools-mcp.md#w13) | [原生](research/competitive/browser-use.md#w13) | [部分](research/competitive/stagehand.md#w13) | [原生](research/competitive/skyvern.md#w13) | [可选](research/competitive/agent-browser.md#w13) |
| W14 文件解析 / 文档数据处理 | [未提供](research/competitive/agentproxy.md#w14) | [未证实](research/competitive/playwright-mcp.md#w14) | [未证实](research/competitive/chrome-devtools-mcp.md#w14) | [原生](research/competitive/browser-use.md#w14) | [未证实](research/competitive/stagehand.md#w14) | [原生](research/competitive/skyvern.md#w14) | [部分](research/competitive/agent-browser.md#w14) |
| W15 任务调度 / webhook | [未提供](research/competitive/agentproxy.md#w15) | [未证实](research/competitive/playwright-mcp.md#w15) | [未证实](research/competitive/chrome-devtools-mcp.md#w15) | [云端](research/competitive/browser-use.md#w15) | [云端](research/competitive/stagehand.md#w15) | [原生](research/competitive/skyvern.md#w15) | [部分](research/competitive/agent-browser.md#w15) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| W01 内置模型驱动执行循环 | [未提供](research/competitive/agentproxy.md#w01) | [不适用](research/competitive/mitmproxy.md#w01) | [不适用](research/competitive/whistle.md#w01) | [不适用](research/competitive/http-toolkit.md#w01) | [可选](research/competitive/zap.md#w01) |
| W02 多模型 / 自定义模型 | [不适用](research/competitive/agentproxy.md#w02) | [不适用](research/competitive/mitmproxy.md#w02) | [不适用](research/competitive/whistle.md#w02) | [不适用](research/competitive/http-toolkit.md#w02) | [可选](research/competitive/zap.md#w02) |
| W03 用户自定义工具 / 动作 | [部分](research/competitive/agentproxy.md#w03) | [部分](research/competitive/mitmproxy.md#w03) | [部分](research/competitive/whistle.md#w03) | [部分](research/competitive/http-toolkit.md#w03) | [可选](research/competitive/zap.md#w03) |
| W04 多步骤工作流定义 | [部分](research/competitive/agentproxy.md#w04) | [不适用](research/competitive/mitmproxy.md#w04) | [不适用](research/competitive/whistle.md#w04) | [不适用](research/competitive/http-toolkit.md#w04) | [可选](research/competitive/zap.md#w04) |
| W05 条件、循环与并行 | [未提供](research/competitive/agentproxy.md#w05) | [不适用](research/competitive/mitmproxy.md#w05) | [不适用](research/competitive/whistle.md#w05) | [不适用](research/competitive/http-toolkit.md#w05) | [部分](research/competitive/zap.md#w05) |
| W06 人工接管 / 审批节点 | [部分](research/competitive/agentproxy.md#w06) | [部分](research/competitive/mitmproxy.md#w06) | [部分](research/competitive/whistle.md#w06) | [部分](research/competitive/http-toolkit.md#w06) | [部分](research/competitive/zap.md#w06) |
| W07 任务结果验证 | [未提供](research/competitive/agentproxy.md#w07) | [不适用](research/competitive/mitmproxy.md#w07) | [不适用](research/competitive/whistle.md#w07) | [不适用](research/competitive/http-toolkit.md#w07) | [可选](research/competitive/zap.md#w07) |
| W08 步骤历史 / 动作回执 | [部分](research/competitive/agentproxy.md#w08) | [不适用](research/competitive/mitmproxy.md#w08) | [不适用](research/competitive/whistle.md#w08) | [不适用](research/competitive/http-toolkit.md#w08) | [部分](research/competitive/zap.md#w08) |
| W09 自动步骤检查点 | [部分](research/competitive/agentproxy.md#w09) | [不适用](research/competitive/mitmproxy.md#w09) | [不适用](research/competitive/whistle.md#w09) | [不适用](research/competitive/http-toolkit.md#w09) | [未证实](research/competitive/zap.md#w09) |
| W10 跨进程恢复 / 状态重绑 | [部分](research/competitive/agentproxy.md#w10) | [不适用](research/competitive/mitmproxy.md#w10) | [不适用](research/competitive/whistle.md#w10) | [不适用](research/competitive/http-toolkit.md#w10) | [部分](research/competitive/zap.md#w10) |
| W11 未知结果处理 / 防重复执行 | [部分](research/competitive/agentproxy.md#w11) | [不适用](research/competitive/mitmproxy.md#w11) | [不适用](research/competitive/whistle.md#w11) | [不适用](research/competitive/http-toolkit.md#w11) | [未证实](research/competitive/zap.md#w11) |
| W12 历史重放 / 动作缓存 | [未提供](research/competitive/agentproxy.md#w12) | [部分](research/competitive/mitmproxy.md#w12) | [部分](research/competitive/whistle.md#w12) | [部分](research/competitive/http-toolkit.md#w12) | [可选](research/competitive/zap.md#w12) |
| W13 凭据 / 登录辅助 | [部分](research/competitive/agentproxy.md#w13) | [部分](research/competitive/mitmproxy.md#w13) | [部分](research/competitive/whistle.md#w13) | [部分](research/competitive/http-toolkit.md#w13) | [可选](research/competitive/zap.md#w13) |
| W14 文件解析 / 文档数据处理 | [未提供](research/competitive/agentproxy.md#w14) | [不适用](research/competitive/mitmproxy.md#w14) | [不适用](research/competitive/whistle.md#w14) | [部分](research/competitive/http-toolkit.md#w14) | [部分](research/competitive/zap.md#w14) |
| W15 任务调度 / webhook | [未提供](research/competitive/agentproxy.md#w15) | [不适用](research/competitive/mitmproxy.md#w15) | [不适用](research/competitive/whistle.md#w15) | [部分](research/competitive/http-toolkit.md#w15) | [部分](research/competitive/zap.md#w15) |

本组口径：W01：产品自身接收目标并调用模型推进任务；W02：产品自身模型配置；外部Agent调用工具不算；W03：扩展Agent动作或工具，区别于只更改配置；W04：显式流程定义或动作序列，复杂度需说明；W05：工作流正式提供控制流，任意写代码不直接等价；W06：明确的暂停、接管或人工输入合同；W07：用户可指定业务成功条件并读取验证结果；W08：任务步骤和动作结果有正式记录；W09：动作前后自动保存待续状态；W10：注明恢复对象、前提和边界；W11：正式区分未开始、已完成和结果未知；W12：正式重放任务历史或缓存观察/动作，注明区别；W13：凭据集成、保存会话或人工登录辅助，不推断授权突破；W14：读取文件内容并参与任务，捕获附件字节不算解析；W15：公开任务异步状态、定时运行或完成通知入口。

### 调试与分析

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| T01 浏览器 Console / 异常 | [部分](research/competitive/agentproxy.md#t01) | [原生](research/competitive/playwright-mcp.md#t01) | [原生](research/competitive/chrome-devtools-mcp.md#t01) | [可选](research/competitive/browser-use.md#t01) | [部分](research/competitive/stagehand.md#t01) | [可选](research/competitive/skyvern.md#t01) | [原生](research/competitive/agent-browser.md#t01) |
| T02 性能 trace / 性能分析 | [未提供](research/competitive/agentproxy.md#t02) | [部分](research/competitive/playwright-mcp.md#t02) | [原生](research/competitive/chrome-devtools-mcp.md#t02) | [可选](research/competitive/browser-use.md#t02) | [部分](research/competitive/stagehand.md#t02) | [部分](research/competitive/skyvern.md#t02) | [原生](research/competitive/agent-browser.md#t02) |
| T03 Heap / 内存诊断 | [未提供](research/competitive/agentproxy.md#t03) | [未提供](research/competitive/playwright-mcp.md#t03) | [部分](research/competitive/chrome-devtools-mcp.md#t03) | [不适用](research/competitive/browser-use.md#t03) | [不适用](research/competitive/stagehand.md#t03) | [不适用](research/competitive/skyvern.md#t03) | [未提供](research/competitive/agent-browser.md#t03) |
| T04 视频 / 执行 trace | [未提供](research/competitive/agentproxy.md#t04) | [可选](research/competitive/playwright-mcp.md#t04) | [原生](research/competitive/chrome-devtools-mcp.md#t04) | [可选](research/competitive/browser-use.md#t04) | [部分](research/competitive/stagehand.md#t04) | [部分](research/competitive/skyvern.md#t04) | [部分](research/competitive/agent-browser.md#t04) |
| T05 动作与网络关联视图 | [部分](research/competitive/agentproxy.md#t05) | [部分](research/competitive/playwright-mcp.md#t05) | [未证实](research/competitive/chrome-devtools-mcp.md#t05) | [部分](research/competitive/browser-use.md#t05) | [部分](research/competitive/stagehand.md#t05) | [部分](research/competitive/skyvern.md#t05) | [部分](research/competitive/agent-browser.md#t05) |
| T06 被动检查 / 诊断信号 | [原生](research/competitive/agentproxy.md#t06) | [未证实](research/competitive/playwright-mcp.md#t06) | [原生](research/competitive/chrome-devtools-mcp.md#t06) | [未证实](research/competitive/browser-use.md#t06) | [未证实](research/competitive/stagehand.md#t06) | [部分](research/competitive/skyvern.md#t06) | [原生](research/competitive/agent-browser.md#t06) |
| T07 扩展安全测试模块 | [原生](research/competitive/agentproxy.md#t07) | [未证实](research/competitive/playwright-mcp.md#t07) | [未证实](research/competitive/chrome-devtools-mcp.md#t07) | [不适用](research/competitive/browser-use.md#t07) | [不适用](research/competitive/stagehand.md#t07) | [不适用](research/competitive/skyvern.md#t07) | [未证实](research/competitive/agent-browser.md#t07) |
| T08 差异比较 / 报告 | [原生](research/competitive/agentproxy.md#t08) | [部分](research/competitive/playwright-mcp.md#t08) | [原生](research/competitive/chrome-devtools-mcp.md#t08) | [未证实](research/competitive/browser-use.md#t08) | [未证实](research/competitive/stagehand.md#t08) | [部分](research/competitive/skyvern.md#t08) | [原生](research/competitive/agent-browser.md#t08) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| T01 浏览器 Console / 异常 | [部分](research/competitive/agentproxy.md#t01) | [未证实](research/competitive/mitmproxy.md#t01) | [原生](research/competitive/whistle.md#t01) | [未证实](research/competitive/http-toolkit.md#t01) | [部分](research/competitive/zap.md#t01) |
| T02 性能 trace / 性能分析 | [未提供](research/competitive/agentproxy.md#t02) | [部分](research/competitive/mitmproxy.md#t02) | [部分](research/competitive/whistle.md#t02) | [部分](research/competitive/http-toolkit.md#t02) | [部分](research/competitive/zap.md#t02) |
| T03 Heap / 内存诊断 | [未提供](research/competitive/agentproxy.md#t03) | [未证实](research/competitive/mitmproxy.md#t03) | [未证实](research/competitive/whistle.md#t03) | [未证实](research/competitive/http-toolkit.md#t03) | [未证实](research/competitive/zap.md#t03) |
| T04 视频 / 执行 trace | [未提供](research/competitive/agentproxy.md#t04) | [未证实](research/competitive/mitmproxy.md#t04) | [未证实](research/competitive/whistle.md#t04) | [未证实](research/competitive/http-toolkit.md#t04) | [部分](research/competitive/zap.md#t04) |
| T05 动作与网络关联视图 | [部分](research/competitive/agentproxy.md#t05) | [不适用](research/competitive/mitmproxy.md#t05) | [部分](research/competitive/whistle.md#t05) | [部分](research/competitive/http-toolkit.md#t05) | [部分](research/competitive/zap.md#t05) |
| T06 被动检查 / 诊断信号 | [原生](research/competitive/agentproxy.md#t06) | [部分](research/competitive/mitmproxy.md#t06) | [部分](research/competitive/whistle.md#t06) | [部分](research/competitive/http-toolkit.md#t06) | [可选](research/competitive/zap.md#t06) |
| T07 扩展安全测试模块 | [原生](research/competitive/agentproxy.md#t07) | [未证实](research/competitive/mitmproxy.md#t07) | [未证实](research/competitive/whistle.md#t07) | [未证实](research/competitive/http-toolkit.md#t07) | [可选](research/competitive/zap.md#t07) |
| T08 差异比较 / 报告 | [原生](research/competitive/agentproxy.md#t08) | [未证实](research/competitive/mitmproxy.md#t08) | [未证实](research/competitive/whistle.md#t08) | [部分](research/competitive/http-toolkit.md#t08) | [可选](research/competitive/zap.md#t08) |

本组口径：T01：正式查看浏览器日志或JS异常；T02：录制并读取浏览器性能或网络时序分析；T03：堆快照或内存分析正式接口；T04：保存执行过程视频或可回看追踪产物；T05：正式把动作和网络记录放在一起；注明时间关联还是因果；T06：根据已观测流量或页面输出诊断，不主动发攻击请求；T07：仅记录已有扫描/测试模块及可选性，不给操作流程；T08：请求响应差异或正式报告产物。

### 存储与证据

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| S01 持久流量存储与重开 | [原生](research/competitive/agentproxy.md#s01) | [部分](research/competitive/playwright-mcp.md#s01) | [部分](research/competitive/chrome-devtools-mcp.md#s01) | [部分](research/competitive/browser-use.md#s01) | [部分](research/competitive/stagehand.md#s01) | [部分](research/competitive/skyvern.md#s01) | [部分](research/competitive/agent-browser.md#s01) |
| S02 记录标签、备注与链接 | [原生](research/competitive/agentproxy.md#s02) | [未证实](research/competitive/playwright-mcp.md#s02) | [未证实](research/competitive/chrome-devtools-mcp.md#s02) | [未证实](research/competitive/browser-use.md#s02) | [云端](research/competitive/stagehand.md#s02) | [原生](research/competitive/skyvern.md#s02) | [部分](research/competitive/agent-browser.md#s02) |
| S03 二进制附件保存 | [原生](research/competitive/agentproxy.md#s03) | [原生](research/competitive/playwright-mcp.md#s03) | [部分](research/competitive/chrome-devtools-mcp.md#s03) | [原生](research/competitive/browser-use.md#s03) | [部分](research/competitive/stagehand.md#s03) | [原生](research/competitive/skyvern.md#s03) | [原生](research/competitive/agent-browser.md#s03) |
| S04 文件哈希与大小证据 | [原生](research/competitive/agentproxy.md#s04) | [未证实](research/competitive/playwright-mcp.md#s04) | [未证实](research/competitive/chrome-devtools-mcp.md#s04) | [未证实](research/competitive/browser-use.md#s04) | [未证实](research/competitive/stagehand.md#s04) | [部分](research/competitive/skyvern.md#s04) | [未证实](research/competitive/agent-browser.md#s04) |
| S05 队列 / 丢弃 / 写入状态 | [原生](research/competitive/agentproxy.md#s05) | [未证实](research/competitive/playwright-mcp.md#s05) | [未证实](research/competitive/chrome-devtools-mcp.md#s05) | [未证实](research/competitive/browser-use.md#s05) | [未证实](research/competitive/stagehand.md#s05) | [部分](research/competitive/skyvern.md#s05) | [部分](research/competitive/agent-browser.md#s05) |
| S06 保留预算与清理范围 | [部分](research/competitive/agentproxy.md#s06) | [原生](research/competitive/playwright-mcp.md#s06) | [部分](research/competitive/chrome-devtools-mcp.md#s06) | [部分](research/competitive/browser-use.md#s06) | [部分](research/competitive/stagehand.md#s06) | [原生](research/competitive/skyvern.md#s06) | [部分](research/competitive/agent-browser.md#s06) |
| S07 证据打包 / 导出 | [部分](research/competitive/agentproxy.md#s07) | [原生](research/competitive/playwright-mcp.md#s07) | [原生](research/competitive/chrome-devtools-mcp.md#s07) | [部分](research/competitive/browser-use.md#s07) | [部分](research/competitive/stagehand.md#s07) | [部分](research/competitive/skyvern.md#s07) | [原生](research/competitive/agent-browser.md#s07) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| S01 持久流量存储与重开 | [原生](research/competitive/agentproxy.md#s01) | [原生](research/competitive/mitmproxy.md#s01) | [原生](research/competitive/whistle.md#s01) | [付费](research/competitive/http-toolkit.md#s01) | [原生](research/competitive/zap.md#s01) |
| S02 记录标签、备注与链接 | [原生](research/competitive/agentproxy.md#s02) | [部分](research/competitive/mitmproxy.md#s02) | [部分](research/competitive/whistle.md#s02) | [部分](research/competitive/http-toolkit.md#s02) | [原生](research/competitive/zap.md#s02) |
| S03 二进制附件保存 | [原生](research/competitive/agentproxy.md#s03) | [原生](research/competitive/mitmproxy.md#s03) | [原生](research/competitive/whistle.md#s03) | [付费](research/competitive/http-toolkit.md#s03) | [可选](research/competitive/zap.md#s03) |
| S04 文件哈希与大小证据 | [原生](research/competitive/agentproxy.md#s04) | [未证实](research/competitive/mitmproxy.md#s04) | [未证实](research/competitive/whistle.md#s04) | [部分](research/competitive/http-toolkit.md#s04) | [未证实](research/competitive/zap.md#s04) |
| S05 队列 / 丢弃 / 写入状态 | [原生](research/competitive/agentproxy.md#s05) | [未证实](research/competitive/mitmproxy.md#s05) | [未证实](research/competitive/whistle.md#s05) | [未证实](research/competitive/http-toolkit.md#s05) | [部分](research/competitive/zap.md#s05) |
| S06 保留预算与清理范围 | [部分](research/competitive/agentproxy.md#s06) | [部分](research/competitive/mitmproxy.md#s06) | [部分](research/competitive/whistle.md#s06) | [部分](research/competitive/http-toolkit.md#s06) | [原生](research/competitive/zap.md#s06) |
| S07 证据打包 / 导出 | [部分](research/competitive/agentproxy.md#s07) | [原生](research/competitive/mitmproxy.md#s07) | [原生](research/competitive/whistle.md#s07) | [付费](research/competitive/http-toolkit.md#s07) | [可选](research/competitive/zap.md#s07) |

本组口径：S01：长期保存捕获记录，并可重开查询；S02：对请求/任务记录结构化注释或关系；S03：保留下载/响应附件字节；S04：文件SHA等完整性信息及大小；S05：显示异步写入完成、丢弃、错误等可用性状态；S06：公开大小/条数预算和明确清理操作；S07：导出分析产物或可移交记录，格式需说明。

### 扩展与运行边界

**浏览器与 Agent 方向**

| ID / 维度 | AgentProxy | Playwright MCP | Chrome DevTools MCP | Browser Use | Stagehand | Skyvern | agent-browser |
|---|---|---|---|---|---|---|---|
| X01 配置文件 / 运行时配置 | [原生](research/competitive/agentproxy.md#x01) | [原生](research/competitive/playwright-mcp.md#x01) | [原生](research/competitive/chrome-devtools-mcp.md#x01) | [原生](research/competitive/browser-use.md#x01) | [原生](research/competitive/stagehand.md#x01) | [原生](research/competitive/skyvern.md#x01) | [原生](research/competitive/agent-browser.md#x01) |
| X02 插件 / addon 生态 | [部分](research/competitive/agentproxy.md#x02) | [部分](research/competitive/playwright-mcp.md#x02) | [可选](research/competitive/chrome-devtools-mcp.md#x02) | [可选](research/competitive/browser-use.md#x02) | [可选](research/competitive/stagehand.md#x02) | [部分](research/competitive/skyvern.md#x02) | [可选](research/competitive/agent-browser.md#x02) |
| X03 MCP 权限 / 只读提示 | [部分](research/competitive/agentproxy.md#x03) | [部分](research/competitive/playwright-mcp.md#x03) | [部分](research/competitive/chrome-devtools-mcp.md#x03) | [部分](research/competitive/browser-use.md#x03) | [部分](research/competitive/stagehand.md#x03) | [原生](research/competitive/skyvern.md#x03) | [原生](research/competitive/agent-browser.md#x03) |
| X04 网络服务认证与访问控制 | [未提供](research/competitive/agentproxy.md#x04) | [部分](research/competitive/playwright-mcp.md#x04) | [未证实](research/competitive/chrome-devtools-mcp.md#x04) | [云端](research/competitive/browser-use.md#x04) | [云端](research/competitive/stagehand.md#x04) | [原生](research/competitive/skyvern.md#x04) | [部分](research/competitive/agent-browser.md#x04) |
| X05 进程资源清理与所有权 | [原生](research/competitive/agentproxy.md#x05) | [原生](research/competitive/playwright-mcp.md#x05) | [原生](research/competitive/chrome-devtools-mcp.md#x05) | [部分](research/competitive/browser-use.md#x05) | [原生](research/competitive/stagehand.md#x05) | [原生](research/competitive/skyvern.md#x05) | [原生](research/competitive/agent-browser.md#x05) |
| X06 结构化日志与运行状态 | [原生](research/competitive/agentproxy.md#x06) | [部分](research/competitive/playwright-mcp.md#x06) | [原生](research/competitive/chrome-devtools-mcp.md#x06) | [原生](research/competitive/browser-use.md#x06) | [原生](research/competitive/stagehand.md#x06) | [原生](research/competitive/skyvern.md#x06) | [原生](research/competitive/agent-browser.md#x06) |

**代理与调试方向**

| ID / 维度 | AgentProxy | mitmproxy | Whistle | HTTP Toolkit | ZAP |
|---|---|---|---|---|---|
| X01 配置文件 / 运行时配置 | [原生](research/competitive/agentproxy.md#x01) | [原生](research/competitive/mitmproxy.md#x01) | [原生](research/competitive/whistle.md#x01) | [部分](research/competitive/http-toolkit.md#x01) | [原生](research/competitive/zap.md#x01) |
| X02 插件 / addon 生态 | [部分](research/competitive/agentproxy.md#x02) | [原生](research/competitive/mitmproxy.md#x02) | [原生](research/competitive/whistle.md#x02) | [部分](research/competitive/http-toolkit.md#x02) | [原生](research/competitive/zap.md#x02) |
| X03 MCP 权限 / 只读提示 | [部分](research/competitive/agentproxy.md#x03) | [不适用](research/competitive/mitmproxy.md#x03) | [不适用](research/competitive/whistle.md#x03) | [原生](research/competitive/http-toolkit.md#x03) | [部分](research/competitive/zap.md#x03) |
| X04 网络服务认证与访问控制 | [未提供](research/competitive/agentproxy.md#x04) | [部分](research/competitive/mitmproxy.md#x04) | [部分](research/competitive/whistle.md#x04) | [原生](research/competitive/http-toolkit.md#x04) | [部分](research/competitive/zap.md#x04) |
| X05 进程资源清理与所有权 | [原生](research/competitive/agentproxy.md#x05) | [部分](research/competitive/mitmproxy.md#x05) | [部分](research/competitive/whistle.md#x05) | [部分](research/competitive/http-toolkit.md#x05) | [部分](research/competitive/zap.md#x05) |
| X06 结构化日志与运行状态 | [原生](research/competitive/agentproxy.md#x06) | [原生](research/competitive/mitmproxy.md#x06) | [原生](research/competitive/whistle.md#x06) | [原生](research/competitive/http-toolkit.md#x06) | [原生](research/competitive/zap.md#x06) |

本组口径：X01：正式配置入口及热更新边界；X02：官方扩展机制和发布入口；X03：工具注解、策略或明确权限范围；不能把提示当强制执行；X04：内建远程接口身份校验或访问控制，具体保护面需说明；X05：明确关闭自己资源、借用资源保护等生命周期合同；X06：正式日志、状态或健康观察接口。

## 本轮深入核对纠正的关键事实

以下条目用于防止按旧印象读矩阵；每项的定义、版本和证据均可在对应项目明细复核。

1. **浏览器工具已有大量相同基础能力。** Playwright MCP、Chrome DevTools MCP 和 agent-browser 的工具面都需按当前目录比较。ARIA refs、iframe、增量快照不能单独当作 AgentProxy 的独有能力。参见 [Playwright MCP](research/competitive/playwright-mcp.md) 与 [agent-browser](research/competitive/agent-browser.md)。
2. **Stagehand v4 与旧版 Agent 循环分离。** 当前 v4 迁移文档明确移除了 `agent()`，继续提供离散浏览器/语义 API；同仓 v3 文档中的接口不能混入当前清单。参见 [Stagehand](research/competitive/stagehand.md)。
3. **恢复不是单一开关。** 存储登录态、重绑现有标签页、保存任务检查点、恢复未知执行结果和重放历史是不同合同。agent-browser 也有 `outcome_unknown` 处理，不能据 AgentProxy 的相似能力宣称唯一性。参见 [agent-browser](research/competitive/agent-browser.md#w11)、[AgentProxy](research/competitive/agentproxy.md#w11)。
4. **传统调试产品也在接入 Agent。** Whistle 已有官方 Local Agent API；HTTP Toolkit 当前已有官方 MCP 及 SSE 解析相关实现；ZAP 有官方 MCP、SSE、WebSocket 和可选 LLM 插件。不能沿用“这些项目没有 Agent 接口或看不到实时消息”的判断。参见 [Whistle](research/competitive/whistle.md)、[HTTP Toolkit](research/competitive/http-toolkit.md)、[ZAP](research/competitive/zap.md)。
5. **协议、消息和存储要分别比较。** 支持 WebSocket/HTTP streaming，不必然表示提供持久应用消息、开放连接期间查询、增量游标和完整性诊断。反过来，mitmproxy 已有的协议能力也不能全部计为 AgentProxy 公开能力。参见矩阵 N/M/S 三组及各项目依据。
6. **云端与开源本体分别计入。** Browser Use、Browserbase/Stagehand、Skyvern 的托管能力，以及 HTTP Toolkit 的 Pro 能力，都在明细保留适用边界；SDK 支持某个后端，不等于开源库附带完整托管平台。

7. **连接协议与观察对象分开。** MCP 使用 SSE/HTTP 传输，不等于能解析网站的 SSE；CDP 或页面预览使用 WebSocket，也不等于能捕获网站的 WebSocket 应用消息。矩阵 D04 与 M01–M08 分开核对。

8. **提取与文件保存分开。** 对已捕获响应做 JSONPath/regex 提取，不等于页面 Schema 约束提取；保存 PDF 附件字节，不等于解析 PDF 内容或填写 PDF 表单。矩阵 O09、O12、W14、S03 保留这些差异。

## 对 AgentProxy 当前实现的具体判断

它已经把受控浏览器、独立 MITM、SQLite 流量/实时消息、增量引用和本地步骤状态接在一起。这个组合有明确用途：外部 Agent 操作页面时，可以查询已持久保存的请求和消息，并知道上一步是否完成或结果未知。详细实现边界见 [AgentProxy 全量清单](research/competitive/agentproxy.md)。

从功能对照可直接看出的差距包括：页面 Schema 提取与语义定位、专门性能/内存诊断、人工调试工作台、工具组与综合安装诊断、完整归档导出和存储生命周期管理。复杂业务平台还多出流程控制、可声明结果验证、调度和人工介入等产品层。它们不应通过堆接口名或把底层库潜力算成现有能力来补齐。

本地复核还确认了一处覆盖差距：自动步骤检查点及回执覆盖统一导航/动作链路，历史前进后退、刷新、任意 JS 等旧入口尚未全部接入。因此矩阵 W08/W09/W11 标为部分，不能把“已有检查点”写成“所有浏览器操作都有一致恢复合同”。

AgentProxy 的 `completed` 是浏览器原语完成，已接入的检查点不重放未知步骤，流量窗口只表示时间相关；这些边界继续保留。具体哪些能力值得新增，需要结合实际使用场景决定，本报告先把事实清单和差异记录完整。
