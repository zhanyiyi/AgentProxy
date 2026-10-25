# ZAP：完整公开功能与接口清单

核对日期：2026-10-25。本文按下述源码和官方文档快照整理；不是运行成功率或性能测试。

- 仓库：[https://github.com/zaproxy/zaproxy](https://github.com/zaproxy/zaproxy)
- 固定源码：`1228a82745c5bb22d9e33e0eeb826c533c359443`
- 版本边界：2.17.0（最新正式 core release，2025-12-15）；比较 main HEAD 与当日独立更新的插件。
- 授权边界：Apache-2.0（core）；独立插件和第三方组件各自核对。
- 清单规模：36 个功能分组、137 个具名接口/配置/协议条目、106 个统一维度。条目粒度不同，不用数量排名。
- [返回横向总表](../../COMPETITIVE_ANALYSIS.md)；[机器可读原始记录](zap.json)。

## 阅读边界

- 只读核验：2026-10-25（Asia/Shanghai）。默认分支main；core SHA不代表所有插件源码版本。文档是当日可见的浮动页面。
- 可选表示通过官方插件提供或需安装配置，不等于发行包必然未安装。Network是随产品提供的关键插件；MCP/LLM/报告/浏览器等有独立版本。
- Marketplace当前列MCP Integration 0.4.0 alpha、LLM Support 0.1.0 alpha。存在性和成熟度须一起表述，外部模型可能另有费用。
- 列一等核心能力、49个HTTP API组、17个MCP工具/10类资源/2提示，以及官方具名插件类别；不逐条穷举扫描规则、payload字典或内部参数。
- 安全功能仅列已有模块和可选性，不提供攻击流程或自主攻防建议。
- Selenium/Zest/Client Side Integration已有真实浏览器操作、客户端观察和多步录制；不能把ZAP简化成只看HTTP的代理。这些仍不等同版本化ARIA/ref合同。
- LLM+MCP聊天可以调用工具；未实测通用业务目标执行效果。数据库重开和Zest回放不自动证明未知业务动作防重复执行。
- 当前插件文档不代表2.17.0原始安装包全都默认包含。AJAX Spider等旧模块在新nightly/weekly交付有退役变化，目录保留历史兼容定位，优先关注Client Spider。

## 功能分组、交付范围与边界

| ID | 分类 | 功能 | 状态 | 具体范围与限制 | 具名接口 | 证据 |
|---|---|---|---|---|---|---|
| zap-http | 协议 | HTTP(S) 与 HTTP/2 | 原生 | Network独立更新；HTTP2自2.13正式支持。 | Network | [zap-network](https://www.zaproxy.org/docs/desktop/addons/network/)、[zap-http2](https://www.zaproxy.org/docs/desktop/releases/2.13.0/) |
| zap-modes | 接入 | 多监听与透明代理 | 原生 | 可分别启用proxy/API、额外监听、SNI透明HTTPS和TLS透传。 | Network | [zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| zap-upstream | 接入 | HTTP/SOCKS上游、DNS和TLS | 原生 | 上游凭据/例外、超时/TLS版本、DNS缓存。 | Network | [zap-connection](https://www.zaproxy.org/docs/desktop/addons/network/options/connection/) |
| zap-decode | 观察 | 正文编码处理 | 部分 | gzip/deflate和指定平台br；不是压缩SSE增量处理证明。 | Network | [zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| zap-traffic | 观察 | HTTP历史/搜索/站点树 | 原生 | 头体、状态、参数、标签/备注和手工请求编辑。 | ZAP Desktop、HTTP API | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/) |
| zap-break | 改写 | HTTP断点与继续 | 原生 | UI/API暂停、编辑、继续或丢弃。 | break | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| zap-rewrite | 改写 | 替换/脚本/本地响应 | 可选 | Replacer/MapLocal/Proxy与Sender脚本。 | Replacer、Map Local | [zap-replacer](https://www.zaproxy.org/docs/desktop/addons/replacer/)、[zap-maplocal](https://www.zaproxy.org/docs/desktop/addons/map-local/)、[zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| zap-ws | 实时消息 | WebSocket消息与控制 | 可选 | 双向/二进制、UI/API、消息断点/脚本和已有测试模块。 | WebSockets、websocket | [zap-ws](https://www.zaproxy.org/docs/desktop/addons/websockets/)、[zap-ws-api](https://www.zaproxy.org/docs/desktop/addons/websockets/api/) |
| zap-sse | 实时消息 | SSE截获与事件显示 | 可选 | 专用事件tab；压缩开放流增量与持久游标未验证。 | Server-Sent Events | [zap-sse](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/) |
| zap-cert | 证书 | CA和服务器/客户端证书 | 原生 | Network证书与mTLS设置，客户端需信任相应CA。 | Network | [zap-server-certs](https://www.zaproxy.org/docs/desktop/addons/network/options/servercertificates/)、[zap-client-certs](https://www.zaproxy.org/docs/desktop/addons/network/options/clientcertificates/) |
| zap-contexts | 会话 | 上下文/用户/范围/认证 | 原生 | 每应用的认证方法、验证指标、会话和用户。 | context、users、authentication | [zap-auth](https://www.zaproxy.org/docs/desktop/start/features/authentication/) |
| zap-authhelper | 会话 | 登录辅助和认证统计 | 可选 | 浏览器/客户端脚本/自动识别等；OAuth2初步支持不能当作全部OAuth流程。 | Authentication Helper、Authentication Statistics | [zap-authhelper](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/)、[zap-oauth](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/oauth2-auth/) |
| zap-httpstate | 会话 | Cookie和HTTP鉴权跟踪 | 部分 | 全局HTTP State/HTTP Sessions，不是浏览器Context隔离。 | httpSessions | [zap-connection](https://www.zaproxy.org/docs/desktop/addons/network/options/connection/)、[zap-auth](https://www.zaproxy.org/docs/desktop/start/features/authentication/) |
| zap-persist | 存储 | 持续数据库记录和重开 | 原生 | 启用persist后连续保存；未持久会话关闭后不可重开。 | core | [zap-session](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/) |
| zap-budget | 存储 | 恢复日志/正文预算/退出压缩 | 原生 | 请求响应最大体积、数据库恢复日志和持久策略。 | core | [zap-database](https://www.zaproxy.org/docs/desktop/ui/dialogs/options/database/) |
| zap-exim | 导出 | HAR/消息/URL/站点树 | 可选 | HAR双向、原始二进制/文本/XML与日志；导入会规范化部分HTTP字段。 | exim、Import/Export | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| zap-report | 报告 | 模板报告和差异 | 可选 | Report Generation按范围/风险/置信度，HTML/MD/PDF/JSON/SARIF依所装模板；Diff比较请求响应。 | Report Generation、Diff | [zap-reports](https://www.zaproxy.org/docs/desktop/addons/report-generation/)、[zap-diff](https://www.zaproxy.org/docs/desktop/addons/diff/)、[zap-market](https://www.zaproxy.org/addons/) |
| zap-api-structure | API结构 | OpenAPI/Postman/GraphQL/SOAP/gRPC | 可选 | 具名插件导入/识别/解析，不把定义导入误写成自动生成定义。 | OpenAPI Support、Postman Support、GraphQL Support、SOAP Support、gRPC Support | [zap-market](https://www.zaproxy.org/addons/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| zap-passive | 检查 | 被动检查和告警管理 | 可选 | 已观察流量检查、队列、风险/置信度/证据和筛选。 | pscan、alert、Alert Filters | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| zap-testing | 检查 | 扩展安全测试模块 | 可选 | ActiveRules/AccessControl/Sequence/Fuzzer/OAST，仅列存在性不提供流程。 | Active Scan Rules、Access Control Testing、Sequence Scanner、Fuzzer、OAST Support | [zap-market](https://www.zaproxy.org/addons/) |
| zap-selenium | 浏览器 | 多引擎/WebDriver脚本 | 可选 | Chrome/Edge/Firefox/Safari/HtmlUnit、headless，JS/URL/表单/点击。 | Selenium / WebDriver scripts | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| zap-client | 浏览器 | DOM/事件/Client Map | 可选 | 扩展记录DOM变化/表单/输入/链接/Cookie和fragment页面，历史与YAML导出。 | Client Side Integration / Client Spider | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| zap-spiders | 浏览器 | HTTP与现代客户端页面发现 | 可选 | HTTP Spider/ClientSpider；AJAX模块是有渠道变化的历史兼容功能。 | spider、Client Side Integration / Client Spider | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-market](https://www.zaproxy.org/addons/) |
| zap-zest | 工作流 | 交互录制/编辑/回放 | 可选 | HTTP和客户端脚本、树形编辑、导入导出，不等于未知动作自动恢复。 | Zest / Browser Recorder | [zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| zap-zest-controls | 工作流 | 条件/循环/断言 | 可选 | Zest正式数据对象支持条件/循环/断言，未声称并行或跨进程幂等。 | Zest / Browser Recorder | [zap-zest-control](https://github.com/zaproxy/zest/tree/5cff406fbbe575abdff0e336ae5053970ecbb61a/src/main/java/org/zaproxy/zest/core/v1)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| zap-automation | 工作流 | YAML多任务与Job Tests | 可选 | 环境/认证/delay/统计或URL测试/退出码/报告，插件扩展任务。 | Automation Framework YAML | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/) |
| zap-history | 工作流 | 客户端历史/任务进度/工具回执 | 部分 | 不同模块的历史和状态；没有据此推断统一业务checkpoint。 | automation、stats | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-llm-chat](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/) |
| zap-scripts | 扩展 | JSR-223脚本类别 | 原生 | Extender/Proxy/Sender/认证/会话/standalone/targeted和检查脚本；语言按插件。 | JSR-223 / Extender scripts | [zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| zap-plugins | 扩展 | Marketplace与独立更新 | 原生 | UI/CLI/API安装更新插件；alpha/beta/release不能混成稳定。 | autoupdate | [zap-market](https://www.zaproxy.org/addons/)、[zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/) |
| zap-mcp | 机器接口 | 官方HTTP MCP | 可选 | 17工具、10资源模板类别、2提示；同机可信合同，支持Extender自定义工具资源。 | MCP HTTP server | [zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/)、[zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/)、[zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/)、[zap-mcp-prompts](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-prompts/) |
| zap-history-range | 机器接口 | MCP分层历史/正文范围 | 可选 | 字段/offset/max正文读取，Length/Offset/Returned/Truncated元数据。 | zap_get_history | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| zap-llm | 模型 | 多供应商聊天和工具调用 | 可选 | LLM+MCP可在聊天调用工具，默认不选装不发送数据；供应商费用独立。 | Azure OpenAI / Anthropic / Gemini / Ollama / OpenAI Compatible | [zap-llm](https://www.zaproxy.org/docs/desktop/addons/llm-support/)、[zap-llm-options](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/) |
| zap-llm-history | 模型 | 聊天回执/Trusted范围与切换限制 | 部分 | 独立聊天/模型/工具/token记录；换provider时展示历史不保证给新模型的上下文。 | Azure OpenAI / Anthropic / Gemini / Ollama / OpenAI Compatible | [zap-llm-chat](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/)、[zap-llm-options](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/) |
| zap-hud | 界面 | 浏览器内HUD | 可选 | 部分ZAP功能进入浏览器；官方列覆盖和多标签限制。 | HUD | [zap-hud](https://www.zaproxy.org/docs/desktop/addons/hud/) |
| zap-api-access | 访问控制 | 本机/API key和文件接口 | 原生 | HTTP API默认本机，文件传输默认关闭且需API key；MCP有独立可选key。 | HTTP API、MCP HTTP server | [zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/)、[zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| zap-runtime | 运行 | CLI/daemon/统计/容器 | 原生 | 桌面跨平台，DockerHub/GHCR stable/weekly/nightly/bare及healthcheck。 | zap.sh / zap.bat / daemon、stable / weekly / nightly / bare Docker | [zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/)、[zap-readme](https://github.com/zaproxy/zaproxy/blob/1228a82745c5bb22d9e33e0eeb826c533c359443/README.md)、[zap-docker](https://www.zaproxy.org/docs/docker/about/) |

## 公开接口、命令和扩展目录

这里只记录产品公开的具名入口。MCP 工具、SDK 方法、CLI 参数、工作流块及规则协议分别保留原分类，不把它们当同一单位计分。精确接口名用于检索；用途是本文概括。

| 分类 | 接口 / 命令 / 配置 | 状态 | 用途与边界 | 证据 |
|---|---|---|---|---|
| 人工界面 | `ZAP Desktop` | 原生 | History/Sites/Request/Response/Alerts/Break等工作台。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| CLI | `zap.sh / zap.bat / daemon` | 原生 | 桌面、批处理/后台、会话、配置与插件管理。 | [zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/) |
| 机器接口 | `HTTP API` | 原生 | JSON/HTML/XML，actions/views/others；默认本机，可配key和来源。 | [zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/) |
| MCP | `MCP HTTP server` | 可选 | 官方插件提供tools/resources/prompts，同机可信客户端合同。 | [zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| 工作流接口 | `Automation Framework YAML` | 可选 | 环境、认证、多任务、Job Tests、退出码与报告。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/) |
| 浏览器脚本 | `Selenium / WebDriver scripts` | 可选 | 多浏览器启动，URL/JS/点击/表单交互。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| 脚本接口 | `Zest / Browser Recorder` | 可选 | HTTP和客户端交互录制、图形编辑、回放与导入导出。 | [zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| 扩展接口 | `JSR-223 / Extender scripts` | 原生 | 脚本扩展API/UI/代理/认证/会话和检查模块。 | [zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| HTTP API 组 | `accessControl` | 可选 | 访问控制模块状态与报告 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `acsrf` | 可选 | CSRF token配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `ajaxSpider` | 可选 | 旧AJAX浏览器发现任务 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `alert` | 可选 | 告警读取与管理 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `alertFilter` | 可选 | 告警筛选 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `ascan` | 可选 | 已有检查任务和策略 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `authentication` | 原生 | 认证方法与登录识别 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `authorization` | 可选 | 授权状态检测配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `automation` | 可选 | YAML计划与进度 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `autoupdate` | 可选 | 版本和插件管理 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `break` | 原生 | HTTP断点/继续/丢弃 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `client` | 可选 | 客户端事件和Client Map | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `clientSpider` | 可选 | 现代页面发现任务 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `context` | 原生 | 范围/技术/上下文 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `core` | 原生 | 会话/消息/版本/代理与文件 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `custompayloads` | 可选 | 测试数据配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `dev` | 可选 | 开发诊断 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `exim` | 可选 | 消息/HAR/日志/站点树导入导出 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `forcedUser` | 可选 | 手工固定用户模式 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `graphql` | 可选 | GraphQL结构支持 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `httpSessions` | 原生 | HTTP会话观察 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `hud` | 可选 | 浏览器内界面 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `keyboard` | 可选 | 键盘配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `localProxies` | 可选 | 本地监听兼容接口 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `network` | 可选 | 连接/证书/代理配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `oast` | 可选 | 异步回调诊断模块 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `openapi` | 可选 | OpenAPI定义导入 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `paramDigger` | 可选 | 参数发现模块 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `params` | 可选 | 参数观察 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `pnh` | 可选 | 旧浏览器集成兼容 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `postman` | 可选 | Postman集合导入 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `pscan` | 可选 | 被动检查队列 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `quickstartlaunch` | 可选 | 浏览器启动 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `replacer` | 可选 | 流量替换规则 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `reports` | 可选 | 报告生成 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `retest` | 可选 | 已有结果复核 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `reveal` | 可选 | 页面观察辅助 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `revisit` | 可选 | 流量重访工具 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `ruleConfig` | 可选 | 规则配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `script` | 可选 | 脚本管理 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `search` | 可选 | 流量搜索 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `selenium` | 可选 | 浏览器/驱动配置 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `sessionManagement` | 可选 | 会话机制 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `soap` | 可选 | SOAP结构导入 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `spider` | 可选 | HTTP页面发现 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `stats` | 原生 | 统计监控 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `users` | 原生 | 用户和凭据 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `wappalyzer` | 可选 | 技术识别 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| HTTP API 组 | `websocket` | 可选 | 连接和消息 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| MCP tool | `zap_version` | 可选 | 版本 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_info` | 可选 | 基础信息 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_create_context` | 可选 | 范围上下文 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_start_spider` | 可选 | 启动发现任务 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_stop_spider` | 可选 | 停止发现任务 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_get_spider_status` | 可选 | 发现任务进度 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_start_ajax_spider` | 可选 | 启动旧AJAX任务 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_stop_ajax_spider` | 可选 | 停止AJAX任务 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_get_ajax_spider_status` | 可选 | AJAX任务进度 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_start_active_scan` | 可选 | 启动已有检查模块，仅列存在性 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_stop_active_scan` | 可选 | 停止检查任务 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_get_active_scan_status` | 可选 | 检查任务进度 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_get_passive_scan_status` | 可选 | 被动队列状态 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_get_history` | 可选 | 按字段和正文范围读取HTTP历史 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_generate_report` | 可选 | 模板报告 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_list_resources` | 可选 | 兼容只支持tools的客户端 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP tool | `zap_read_resource` | 可选 | 读取资源 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| MCP resource | `zap://alerts` | 可选 | 紧凑告警概要 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://alerts/{alertRef}` | 可选 | 实例及historyRef | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://contexts` | 可选 | 范围 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://history` | 可选 | 历史条数概要 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://history/{id}` | 可选 | 单条HTTP头体 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://scan-policies` | 可选 | 策略 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://scan-status` | 可选 | 长任务状态 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://sites` | 可选 | 顶层站点 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://sites-tree` | 可选 | 完整站点树 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP resource | `zap://report-templates` | 可选 | 模板名称/扩展名 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| MCP prompt | `zap_baseline_scan` | 可选 | 可发现的被动工作流模板。 | [zap-mcp-prompts](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-prompts/) |
| MCP prompt | `zap_full_scan` | 可选 | 可发现的完整检查模板；本报告不提供操作流程。 | [zap-mcp-prompts](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-prompts/) |
| 官方具名 addon / 类别 | `Network` | 可选 | HTTP2/证书/代理网络栈 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Server-Sent Events` | 可选 | SSE截获和事件显示 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `WebSockets` | 可选 | 消息/断点/API/脚本 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `MCP Integration` | 可选 | MCP接口和扩展 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `LLM Support` | 可选 | 多模型聊天和工具调用 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Automation Framework` | 可选 | YAML计划/Job Tests | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Authentication Helper` | 可选 | 认证辅助/浏览器/OAuth | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Authentication Statistics` | 可选 | 登录状态统计 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Selenium` | 可选 | 浏览器/WebDriver脚本 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Linux / macOS / Windows WebDrivers` | 可选 | 平台浏览器驱动 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Client Side Integration / Client Spider` | 可选 | 浏览器扩展/客户端事件/Client Map/页面发现 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `AJAX Spider` | 可选 | 旧AJAX模块，交付渠道有退役变化 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Zest` | 可选 | 录制/编辑/回放 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Script Console / GraalVM JS / Groovy / Kotlin` | 可选 | 脚本编辑和语言引擎 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Community Scripts` | 可选 | 可选社区脚本集合 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Import/Export` | 可选 | HAR/原始消息/URL/站点树 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Report Generation` | 可选 | 可扩展报告模板 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Diff` | 可选 | 请求响应差异 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Replacer` | 可选 | 自动替换 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Map Local` | 可选 | 本地响应映射 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Encoder` | 可选 | 编码/解码/hash处理器 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `JSON View` | 可选 | 格式化JSON | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Browser View` | 可选 | HTML响应渲染 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `HUD` | 可选 | 浏览器内部分ZAP界面 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `OpenAPI Support` | 可选 | 定义导入和API结构 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Postman Support` | 可选 | 集合导入 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `GraphQL Support` | 可选 | GraphQL结构 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `SOAP Support` | 可选 | SOAP定义 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `gRPC Support` | 可选 | gRPC/Protobuf观察 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Passive Scanner / Passive Scan Rules` | 可选 | 已观察流量的被动检查 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Active Scan Rules` | 可选 | 已有检查规则组，仅列存在性 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Access Control Testing` | 可选 | 已有访问控制模块，仅列存在性 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Sequence Scanner` | 可选 | 已有多请求序列模块，仅列存在性 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Fuzzer` | 可选 | 已有测试数据模块，仅列存在性 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `OAST Support` | 可选 | 异步回调诊断，仅列存在性 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Params / Parameter Digger` | 可选 | 参数观察/发现 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Technology Detection` | 可选 | 技术识别 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `HTTPS Info / TLS Debug` | 可选 | 证书/TLS诊断 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Alert Filters` | 可选 | 告警筛选 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Insights` | 可选 | 结果和流量辅助洞察 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Retest` | 可选 | 已有结果复核 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `OWASP PTK` | 可选 | 浏览器侧集成和被动信息 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Retire.js` | 可选 | 前端依赖诊断 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `All In One Notes / Neonmarker / Highlighter` | 可选 | 备注/标记显示 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Call Graph / TreeTools` | 可选 | 关系和树查看 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Invoke Applications` | 可选 | 外部工具集成 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Quick Start` | 可选 | 快速接入/浏览器启动 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Database` | 可选 | 可选数据库基础设施 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 官方具名 addon / 类别 | `Dev Add-On` | 可选 | 开发诊断 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| 模型接口 | `Azure OpenAI / Anthropic / Gemini / Ollama / OpenAI Compatible` | 可选 | 多provider/model、自定义端点、Trusted范围。 | [zap-llm-options](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/) |
| 交付接口 | `stable / weekly / nightly / bare Docker` | 原生 | DockerHub/GHCR，healthcheck和不同更新节奏。 | [zap-docker](https://www.zaproxy.org/docs/docker/about/) |

## 统一比较维度的逐项依据

此表为横向总表每个格子的依据。未证实保留为未知，不转换为不存在；部分能力必须结合限定条件阅读。

| ID | 维度 | 状态 | 核对结论 | 证据 |
|---|---|---|---|---|
| <a id="d01"></a>D01 | 原生 MCP tools | 可选 | 官方MCP HTTP工具。 | [zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| <a id="d02"></a>D02 | MCP resources / prompts | 可选 | 10资源类别、2提示。 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/)、[zap-mcp-prompts](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-prompts/) |
| <a id="d03"></a>D03 | stdio 接入 | 未证实 | 已确认官方HTTP MCP，未核实stdio入口。 | [zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| <a id="d04"></a>D04 | HTTP 远程机器接口 | 原生 | core HTTP API；MCP为插件。 | [zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/)、[zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| <a id="d05"></a>D05 | 任务操作 CLI | 原生 | CLI/daemon、配置/会话/插件及自动化。 | [zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/) |
| <a id="d06"></a>D06 | 人工操作 UI | 原生 | 桌面工作台，另有HUD插件。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-hud](https://www.zaproxy.org/docs/desktop/addons/hud/) |
| <a id="d07"></a>D07 | 可编程 SDK / 插件 API | 原生 | API、addon和扩展脚本。 | [zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/)、[zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| <a id="d08"></a>D08 | 本地运行 | 原生 | 本地核心，LLM可选。 | [zap-readme](https://github.com/zaproxy/zaproxy/blob/1228a82745c5bb22d9e33e0eeb826c533c359443/README.md)、[zap-llm](https://www.zaproxy.org/docs/desktop/addons/llm-support/) |
| <a id="d09"></a>D09 | 官方托管云 | 未证实 | 已查core/API及官方插件目录，未确认该维度明确合同。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="d10"></a>D10 | Docker / 容器交付 | 原生 | 官方多渠道Docker镜像。 | [zap-docker](https://www.zaproxy.org/docs/docker/about/) |
| <a id="d11"></a>D11 | 安装与运行诊断入口 | 原生 | API状态、Job Tests、Docker health。 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-docker](https://www.zaproxy.org/docs/docker/about/) |
| <a id="d12"></a>D12 | 工具按能力分组启用 | 部分 | 可选插件/脚本/规则；未确认MCP tool profile。 | [zap-market](https://www.zaproxy.org/addons/)、[zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| <a id="b01"></a>B01 | 启动受控浏览器 | 可选 | Selenium启动和脚本控制。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b02"></a>B02 | 连接已有浏览器 / CDP | 部分 | 已有浏览器可装Client扩展接入；非CDP attach。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="b03"></a>B03 | 多浏览器引擎 | 可选 | Chrome/Edge/Firefox/Safari/HtmlUnit。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b04"></a>B04 | headless / headed | 可选 | 公开headed/headless。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b05"></a>B05 | 独立会话 / Context | 部分 | profile和应用Context/User不同于Playwright Context。 | [zap-auth](https://www.zaproxy.org/docs/desktop/start/features/authentication/)、[zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b06"></a>B06 | 持久用户目录 / 配置 | 部分 | Client带Firefox profile，未证实通用user-data-dir恢复。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="b07"></a>B07 | 标签页与 popup | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b08"></a>B08 | iframe 操作 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b09"></a>B09 | 导航与历史 | 可选 | Selenium URL和Zest回放。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="b10"></a>B10 | 点击与指针动作 | 可选 | Selenium脚本正式支持点击。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b11"></a>B11 | 输入、键盘与表单 | 可选 | Selenium脚本正式支持填表。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b12"></a>B12 | 拖拽与滚动 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b13"></a>B13 | 原生对话框决策 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b14"></a>B14 | 文件上传 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b15"></a>B15 | 下载跟踪与保存 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b16"></a>B16 | 页面 JavaScript 执行 | 可选 | Selenium脚本可执行页面JS。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b17"></a>B17 | 条件等待 | 部分 | 自动化delay/验证；统一元素wait工具未证实。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-auth](https://www.zaproxy.org/docs/desktop/start/features/authentication/) |
| <a id="b18"></a>B18 | Cookie 管理 | 部分 | Client读取Cookie，HTTP State跟踪；非浏览器CRUD全集。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-connection](https://www.zaproxy.org/docs/desktop/addons/network/options/connection/) |
| <a id="b19"></a>B19 | 浏览器存储状态导入导出 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b20"></a>B20 | 设备与环境模拟 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="b21"></a>B21 | 网络离线 / 节流 | 部分 | Network限速，非完整浏览器离线模拟。 | [zap-rate](https://www.zaproxy.org/docs/desktop/addons/network/options/ratelimit/) |
| <a id="o01"></a>O01 | ARIA / 无障碍快照 | 不适用 | DOM/事件观察不等于ARIA快照。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="o02"></a>O02 | 元素引用 refs | 不适用 | 未核实Agent快照ref机制。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o03"></a>O03 | 增量快照 / 差异输出 | 部分 | DOMMutation/NodeAdded事件，非版本化ARIA增量。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="o04"></a>O04 | 快照搜索、裁剪或过滤 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o05"></a>O05 | 过期引用合同 | 不适用 | 没有此报告核实的快照ref合同对象。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="o06"></a>O06 | 页面 / 元素截图 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o07"></a>O07 | 标注截图 / 视觉定位 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o08"></a>O08 | HTML / DOM / 文本读取 | 可选 | DOM元素/文本/链接/HTML响应。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="o09"></a>O09 | Schema 约束结构化提取 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o10"></a>O10 | 自然语言定位 / act | 部分 | LLM调用MCP不等于通用自然语言页面定位。 | [zap-llm](https://www.zaproxy.org/docs/desktop/addons/llm-support/)、[zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| <a id="o11"></a>O11 | 定位自适应 / 恢复 | 未证实 | 已查Selenium/Client/Zest正式文档，未确认该项作为独立动作或观察合同。 | [zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| <a id="o12"></a>O12 | 页面 PDF 导出 | 不适用 | PDF报告不是页面打印PDF。 | [zap-reports](https://www.zaproxy.org/docs/desktop/addons/report-generation/) |
| <a id="n01"></a>N01 | 独立代理捕获外部客户端 | 原生 | 独立HTTP客户端代理。 | [zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| <a id="n02"></a>N02 | HTTPS 解密与 CA | 原生 | CA与HTTPS MITM。 | [zap-server-certs](https://www.zaproxy.org/docs/desktop/addons/network/options/servercertificates/) |
| <a id="n03"></a>N03 | HTTP/2 支持 | 原生 | 2.13起正式HTTP2。 | [zap-http2](https://www.zaproxy.org/docs/desktop/releases/2.13.0/) |
| <a id="n04"></a>N04 | HTTP/3 / QUIC 支持 | 未证实 | 无核实HTTP3模式；HAR h3转H2不是支持证据。 | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/)、[zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| <a id="n05"></a>N05 | TCP / UDP 非 HTTP 流量 | 未证实 | 未确认通用TCP/UDP捕获解码。 | [zap-network](https://www.zaproxy.org/docs/desktop/addons/network/) |
| <a id="n06"></a>N06 | 代理模式与上游链路 | 原生 | regular/transparent/多监听/透传和HTTP/SOCKS上游。 | [zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/)、[zap-connection](https://www.zaproxy.org/docs/desktop/addons/network/options/connection/) |
| <a id="n07"></a>N07 | 请求 / 响应详情 | 原生 | History/API头体。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/) |
| <a id="n08"></a>N08 | 搜索、过滤与范围 | 原生 | 搜索、Context范围与站点/历史。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| <a id="n09"></a>N09 | 多值 / 有序响应头 | 未证实 | 有原始头文本，未确认顺序/重复头保真合同。 | [zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/)、[zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| <a id="n10"></a>N10 | 正文解码与格式展示 | 部分 | gzip/deflate、指定平台br及格式插件。 | [zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/)、[zap-market](https://www.zaproxy.org/addons/) |
| <a id="n11"></a>N11 | 请求 / 响应修改与 mock | 可选 | Replacer/MapLocal/代理脚本。 | [zap-replacer](https://www.zaproxy.org/docs/desktop/addons/replacer/)、[zap-maplocal](https://www.zaproxy.org/docs/desktop/addons/map-local/)、[zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| <a id="n12"></a>N12 | 断点与手动继续 | 原生 | HTTP断点UI和break API。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| <a id="n13"></a>N13 | 请求编辑与重发 | 原生 | 手工请求/API发送，HAR发送为插件。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| <a id="n14"></a>N14 | 浏览器网络路由 / mock | 不适用 | 代理层处理不等于browser.route。 | [zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| <a id="n15"></a>N15 | HAR 导入 / 导出 | 可选 | HAR双向，导入有规范化边界。 | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| <a id="n16"></a>N16 | cURL / 客户端代码导出 | 未证实 | 确认HAR/原始消息/Zest导出，未核实cURL/多语言客户端。 | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="n17"></a>N17 | API 结构 / OpenAPI | 可选 | OpenAPI等导入与结构支持，非已证实自动生成。 | [zap-market](https://www.zaproxy.org/addons/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| <a id="m01"></a>M01 | WebSocket 消息查看 | 可选 | WS消息tab和API。 | [zap-ws](https://www.zaproxy.org/docs/desktop/addons/websockets/) |
| <a id="m02"></a>M02 | WebSocket 双向 / 二进制 | 可选 | 双向/二进制/连接信息。 | [zap-ws](https://www.zaproxy.org/docs/desktop/addons/websockets/)、[zap-ws-api](https://www.zaproxy.org/docs/desktop/addons/websockets/api/) |
| <a id="m03"></a>M03 | WebSocket 修改 / 注入 | 可选 | 消息发送、断点和脚本。 | [zap-ws](https://www.zaproxy.org/docs/desktop/addons/websockets/)、[zap-ws-api](https://www.zaproxy.org/docs/desktop/addons/websockets/api/) |
| <a id="m04"></a>M04 | SSE 事件级解析 | 可选 | SSE插件截获与事件显示。 | [zap-sse](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/) |
| <a id="m05"></a>M05 | 压缩 SSE 增量解析 | 未证实 | 官方只确认SSE展示，未验证压缩开放流增量。 | [zap-sse](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/)、[zap-local](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| <a id="m06"></a>M06 | 开放连接期间查询消息 | 可选 | WS/SSE连接中观察；不表示MCP全暴露。 | [zap-ws](https://www.zaproxy.org/docs/desktop/addons/websockets/)、[zap-sse](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/) |
| <a id="m07"></a>M07 | 消息持久化与增量游标 | 部分 | 持久session/WS消息ID分页；未确认跨重启单调SSE游标。 | [zap-session](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/)、[zap-ws-api](https://www.zaproxy.org/docs/desktop/addons/websockets/api/) |
| <a id="m08"></a>M08 | 消息完整性 / 截断标记 | 部分 | MCP正文范围truncated；SSE失败/尾部标记未证实。 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/)、[zap-sse](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/) |
| <a id="w01"></a>W01 | 内置模型驱动执行循环 | 可选 | LLM+MCP聊天可模型调用工具，非实测通用业务Agent。 | [zap-llm](https://www.zaproxy.org/docs/desktop/addons/llm-support/) |
| <a id="w02"></a>W02 | 多模型 / 自定义模型 | 可选 | 五类供应商及自定义端点/模型。 | [zap-llm-options](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/) |
| <a id="w03"></a>W03 | 用户自定义工具 / 动作 | 可选 | Extender扩展MCP工具资源与脚本。 | [zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/)、[zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| <a id="w04"></a>W04 | 多步骤工作流定义 | 可选 | YAML和Zest多步定义。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="w05"></a>W05 | 条件、循环与并行 | 部分 | Zest条件/循环/断言；未证实并行合同。 | [zap-zest-control](https://github.com/zaproxy/zest/tree/5cff406fbbe575abdff0e336ae5053970ecbb61a/src/main/java/org/zaproxy/zest/core/v1)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/) |
| <a id="w06"></a>W06 | 人工接管 / 审批节点 | 部分 | 流量断点人工接管，非统一业务审批节点。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-llm-chat](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/) |
| <a id="w07"></a>W07 | 任务结果验证 | 可选 | Job Tests与Zest断言。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-zest-control](https://github.com/zaproxy/zest/tree/5cff406fbbe575abdff0e336ae5053970ecbb61a/src/main/java/org/zaproxy/zest/core/v1) |
| <a id="w08"></a>W08 | 步骤历史 / 动作回执 | 部分 | Client历史、任务状态、LLM工具回执分散提供。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-llm-chat](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/) |
| <a id="w09"></a>W09 | 自动步骤检查点 | 未证实 | 未确认动作前后自动持久业务checkpoint。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="w10"></a>W10 | 跨进程恢复 / 状态重绑 | 部分 | 数据库重开记录配置；不等于自动重绑业务页面。 | [zap-session](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/) |
| <a id="w11"></a>W11 | 未知结果处理 / 防重复执行 | 未证实 | 未确认未知动作结果防重复执行合同。 | [zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-llm-chat](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/) |
| <a id="w12"></a>W12 | 历史重放 / 动作缓存 | 可选 | Zest/客户端交互回放，不等于自动中断恢复。 | [zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="w13"></a>W13 | 凭据 / 登录辅助 | 可选 | Context/User/认证辅助/浏览器登录和会话。 | [zap-auth](https://www.zaproxy.org/docs/desktop/start/features/authentication/)、[zap-authhelper](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/) |
| <a id="w14"></a>W14 | 文件解析 / 文档数据处理 | 部分 | HAR/API定义文件，不是通用PDF/Office任务解析。 | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/)、[zap-market](https://www.zaproxy.org/addons/) |
| <a id="w15"></a>W15 | 任务调度 / webhook | 部分 | API任务异步状态；统一定时/完成webhook未核实。 | [zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| <a id="t01"></a>T01 | 浏览器 Console / 异常 | 部分 | Client浏览器事件，不代表完整DevTools Console接口。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="t02"></a>T02 | 性能 trace / 性能分析 | 部分 | 网络时序/统计，非浏览器CPU trace。 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="t03"></a>T03 | Heap / 内存诊断 | 未证实 | 已查core/API及官方插件目录，未确认该维度明确合同。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="t04"></a>T04 | 视频 / 执行 trace | 部分 | Zest和客户端历史可回看，不是视频。 | [zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/)、[zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="t05"></a>T05 | 动作与网络关联视图 | 部分 | Client Map可跳Sites；官方说未必是创建节点的同一消息，不声称因果。 | [zap-client](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| <a id="t06"></a>T06 | 被动检查 / 诊断信号 | 可选 | 被动规则/客户端检查/TLS与技术诊断。 | [zap-market](https://www.zaproxy.org/addons/)、[zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="t07"></a>T07 | 扩展安全测试模块 | 可选 | 已有测试模块，仅列存在性。 | [zap-market](https://www.zaproxy.org/addons/) |
| <a id="t08"></a>T08 | 差异比较 / 报告 | 可选 | Diff与模板报告。 | [zap-diff](https://www.zaproxy.org/docs/desktop/addons/diff/)、[zap-reports](https://www.zaproxy.org/docs/desktop/addons/report-generation/) |
| <a id="s01"></a>S01 | 持久流量存储与重开 | 原生 | 启用persist后持续数据库记录和重开。 | [zap-session](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/) |
| <a id="s02"></a>S02 | 记录标签、备注与链接 | 原生 | 标签/备注/Context和historyRef，非统一业务DAG。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/)、[zap-mcp-resources](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| <a id="s03"></a>S03 | 二进制附件保存 | 可选 | 保存原始消息和二进制响应。 | [zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| <a id="s04"></a>S04 | 文件哈希与大小证据 | 未证实 | 已查core/API及官方插件目录，未确认该维度明确合同。 | [zap-features](https://www.zaproxy.org/docs/desktop/start/features/) |
| <a id="s05"></a>S05 | 队列 / 丢弃 / 写入状态 | 部分 | 被动队列/任务状态；traffic writer完成/丢弃计数未证实。 | [zap-mcp-tools](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/)、[zap-api-catalogue](https://www.zaproxy.org/docs/api/) |
| <a id="s06"></a>S06 | 保留预算与清理范围 | 原生 | 正文预算/数据库压缩/持久策略，非全部插件统一预算。 | [zap-database](https://www.zaproxy.org/docs/desktop/ui/dialogs/options/database/) |
| <a id="s07"></a>S07 | 证据打包 / 导出 | 可选 | 报告/HAR/原始报文/站点树/Zest。 | [zap-reports](https://www.zaproxy.org/docs/desktop/addons/report-generation/)、[zap-exim](https://www.zaproxy.org/docs/desktop/addons/import-export/)、[zap-zest](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| <a id="x01"></a>X01 | 配置文件 / 运行时配置 | 原生 | CLI/config/API/插件配置，热更新按模块。 | [zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/)、[zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/) |
| <a id="x02"></a>X02 | 插件 / addon 生态 | 原生 | Marketplace和扩展脚本。 | [zap-market](https://www.zaproxy.org/addons/)、[zap-scripts](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| <a id="x03"></a>X03 | MCP 权限 / 只读提示 | 部分 | Trusted/工具开关与本机合同不是强制沙箱。 | [zap-llm-options](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/)、[zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| <a id="x04"></a>X04 | 网络服务认证与访问控制 | 部分 | HTTP API key/来源；MCP可选key且限定可信同机。 | [zap-api](https://www.zaproxy.org/docs/desktop/start/features/api/)、[zap-mcp](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| <a id="x05"></a>X05 | 进程资源清理与所有权 | 部分 | 会话/daemon/browser生命周期分散；借用CDP所有权未证实。 | [zap-cmd](https://www.zaproxy.org/docs/desktop/cmdline/)、[zap-selenium](https://www.zaproxy.org/docs/desktop/addons/selenium/)、[zap-session](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/) |
| <a id="x06"></a>X06 | 结构化日志与运行状态 | 原生 | Output/API/统计/任务和Docker health。 | [zap-api-catalogue](https://www.zaproxy.org/docs/api/)、[zap-automation](https://www.zaproxy.org/docs/automate/automation-framework/)、[zap-docker](https://www.zaproxy.org/docs/docker/about/) |

## 一手来源目录

| ID | 官方资料 / 固定源码 |
|---|---|
| zap-meta | [main HEAD](https://api.github.com/repos/zaproxy/zaproxy/commits/main) |
| zap-release | [core 最新正式发布](https://github.com/zaproxy/zaproxy/releases/tag/v2.17.0) |
| zap-license | [core Apache-2.0](https://github.com/zaproxy/zaproxy/blob/1228a82745c5bb22d9e33e0eeb826c533c359443/LICENSE) |
| zap-readme | [官方定位](https://github.com/zaproxy/zaproxy/blob/1228a82745c5bb22d9e33e0eeb826c533c359443/README.md) |
| zap-features | [核心功能目录](https://www.zaproxy.org/docs/desktop/start/features/) |
| zap-market | [插件名称/版本/成熟度](https://www.zaproxy.org/addons/) |
| zap-cmd | [命令行](https://www.zaproxy.org/docs/desktop/cmdline/) |
| zap-api | [HTTP API 合同](https://www.zaproxy.org/docs/desktop/start/features/api/) |
| zap-api-catalogue | [HTTP API 全部公开组](https://www.zaproxy.org/docs/api/) |
| zap-network | [Network 插件](https://www.zaproxy.org/docs/desktop/addons/network/) |
| zap-http2 | [HTTP/2 支持](https://www.zaproxy.org/docs/desktop/releases/2.13.0/) |
| zap-local | [监听/透明代理/ALPN/内容解码](https://www.zaproxy.org/docs/desktop/addons/network/options/localservers/) |
| zap-connection | [上游代理/HTTP状态/TLS](https://www.zaproxy.org/docs/desktop/addons/network/options/connection/) |
| zap-server-certs | [CA和服务器证书](https://www.zaproxy.org/docs/desktop/addons/network/options/servercertificates/) |
| zap-client-certs | [客户端证书](https://www.zaproxy.org/docs/desktop/addons/network/options/clientcertificates/) |
| zap-rate | [网络限速](https://www.zaproxy.org/docs/desktop/addons/network/options/ratelimit/) |
| zap-auth | [上下文/用户/认证](https://www.zaproxy.org/docs/desktop/start/features/authentication/) |
| zap-authhelper | [认证辅助](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/) |
| zap-oauth | [OAuth2初步范围](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/oauth2-auth/) |
| zap-session | [会话数据库持续记录与重开](https://www.zaproxy.org/docs/desktop/ui/dialogs/persistsession/) |
| zap-database | [正文预算/恢复日志/数据库压缩](https://www.zaproxy.org/docs/desktop/ui/dialogs/options/database/) |
| zap-exim | [HAR/消息/站点树导入导出](https://www.zaproxy.org/docs/desktop/addons/import-export/) |
| zap-reports | [模板报告](https://www.zaproxy.org/docs/desktop/addons/report-generation/) |
| zap-diff | [请求响应差异](https://www.zaproxy.org/docs/desktop/addons/diff/) |
| zap-replacer | [替换规则](https://www.zaproxy.org/docs/desktop/addons/replacer/) |
| zap-maplocal | [本地响应映射](https://www.zaproxy.org/docs/desktop/addons/map-local/) |
| zap-ws | [WebSocket插件](https://www.zaproxy.org/docs/desktop/addons/websockets/) |
| zap-ws-api | [WebSocket API](https://www.zaproxy.org/docs/desktop/addons/websockets/api/) |
| zap-sse | [SSE插件](https://www.zaproxy.org/docs/desktop/addons/server-sent-events/) |
| zap-automation | [YAML任务/认证/Job Tests](https://www.zaproxy.org/docs/automate/automation-framework/) |
| zap-selenium | [浏览器/WebDriver脚本](https://www.zaproxy.org/docs/desktop/addons/selenium/) |
| zap-client | [ClientMap/DOM/客户端历史](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/) |
| zap-zest | [录制/编辑/回放脚本](https://www.zaproxy.org/docs/desktop/addons/zest/) |
| zap-zest-control | [Zest条件/循环/断言源码](https://github.com/zaproxy/zest/tree/5cff406fbbe575abdff0e336ae5053970ecbb61a/src/main/java/org/zaproxy/zest/core/v1) |
| zap-scripts | [JSR-223脚本类别](https://www.zaproxy.org/docs/desktop/start/features/scripts/) |
| zap-hud | [浏览器内HUD](https://www.zaproxy.org/docs/desktop/addons/hud/) |
| zap-mcp | [官方MCP插件与访问合同](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/) |
| zap-mcp-tools | [MCP工具全集](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-tools/) |
| zap-mcp-resources | [MCP资源全集](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-resources/) |
| zap-mcp-prompts | [MCP提示全集](https://www.zaproxy.org/docs/desktop/addons/mcp-integration/mcp-prompts/) |
| zap-llm | [可选LLM工具调用](https://www.zaproxy.org/docs/desktop/addons/llm-support/) |
| zap-llm-options | [供应商/模型/Trusted策略](https://www.zaproxy.org/docs/desktop/addons/llm-support/options/) |
| zap-llm-chat | [聊天/工具回执及切换限制](https://www.zaproxy.org/docs/desktop/addons/llm-support/chat/) |
| zap-docker | [镜像渠道和healthcheck](https://www.zaproxy.org/docs/docker/about/) |
