# Whistle：完整公开功能与接口清单

核对日期：2026-10-25。本文按下述源码和官方文档快照整理；不是运行成功率或性能测试。

- 仓库：[https://github.com/avwo/whistle](https://github.com/avwo/whistle)
- 固定源码：`16607ba277b383d050bc6efce046b4c92cc0ae39`
- 版本边界：2.10.12（master HEAD 的 package.json；GitHub /releases/latest 返回 404，不虚构发布标签）
- 授权边界：MIT
- 清单规模：39 个功能分组、201 个具名接口/配置/协议条目、106 个统一维度。条目粒度不同，不用数量排名。
- [返回横向总表](../../COMPETITIVE_ANALYSIS.md)；[机器可读原始记录](whistle.json)。

## 阅读边界

- 核验日期：2026-10-25（Asia/Shanghai）。默认分支 master；源码引用固定到指定 HEAD，网站文档是当日可见的浮动文档。
- Whistle 的 Local Agent API 是官方接口，不应把它描述成只能人工操作或没有 Agent 接入。官方 docs 要求 >=2.10.7；固定 HEAD 还公开 saveSessions/getSavedSessions/request/abort 等方法，详见源码。
- 未找到官方 MCP server 或资源/提示模板的明确合同，标记未证实；这不否定其 Node API 和本地 HTTP 实现。
- 浏览器 ARIA/ref、模型自主规划、业务步骤恢复不属于核心产品定位。Weinre/Console 远程调试不等于完整浏览器自动化。
- WebSocket/TCP 的 Pause/Ignore 是消息传输控制；没有据此声称提供 HTTP 请求响应的通用人工断点编辑器。
- 不把 hosts 映射规则叫作独立 DNS 服务器，不把 SOCKS 上游当 UDP 捕获，也不把插件可编程性推断为已完成安全扫描产品。
- 插件内处理脚本、用户账号与 Node API 是本地运行能力；本报告没有确认官方托管 SaaS。
- 补充固定SHA 16607ba277b383d050bc6efce046b4c92cc0ae39 的bin/api.js全部exports：36个服务方法（含2个HTTPS大小写兼容名）与12个本地utils，总48具名Node API；规范方法46个。
- 同时列出这些Node API实际使用的31个HTTP方法+CGI路径；不是完整Web UI内部CGI接口目录，也不将内部CGI稳定性等同文档承诺。
- 规则目录来自官方protocols正文及导航中的frameScript，去重后94个公开操作名/符号；另保留11个源码兼容名称。@/%是特殊语法，http-proxy等别名与原生协议能力不重复计分。
- 没有枚举任意动态插件前缀、每个参数、过滤表达式或正则接受的协议组合；G/P和rule是内部注册用途，不凭内部数组将其宣称为独立公开产品功能。

## 功能分组、交付范围与边界

| ID | 分类 | 功能 | 状态 | 具体范围与限制 | 具名接口 | 证据 |
|---|---|---|---|---|---|---|
| whistle-protocol | 协议 | HTTP、HTTPS、HTTP/2、WebSocket 与 TCP | 原生 | 官方公开抓包与改写协议范围；未据此声称支持 UDP 或 HTTP/3。 | Network / Inspectors / Timeline / Frames | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| whistle-h2 | 协议 | HTTP/2 开关与请求构造 | 原生 | HTTPS 设置可切 HTTP/2，Composer 可选择 HTTP/2；实际握手限制依赖客户端和服务端。 | HTTPS / Custom Certs、Composer | [whistle-https](https://wproxy.org/docs/gui/https.html)、[whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| whistle-modes | 接入 | HTTP(S)/SOCKS/反向代理 | 原生 | CLI 可监听 HTTPS 与 SOCKS5 端口，常规客户端或外部设备可接入。 | w2 / whistle / wproxy | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-cli](https://wproxy.org/docs/cli.html) |
| whistle-upstream | 接入 | 上游 HTTP、HTTPS、SOCKS 与 PAC | 原生 | 规则支持上游代理及其回退变体和 PAC；host/xhost 为目标解析映射。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-mobile | 接入 | 移动端代理与证书引导 | 原生 | 移动设备设置代理及扫码下载安装 CA；不是无条件捕获所有 App。 | HTTPS / Custom Certs | [whistle-mobile](https://wproxy.org/docs/mobile.html)、[whistle-faq](https://wproxy.org/docs/faq.html) |
| whistle-ui | 界面 | 完整 Web 调试工作台 | 原生 | Network/规则/值/插件/Weinre/Console/Composer 共享界面，官方还提供可选桌面客户端。 | Network / Inspectors / Timeline / Frames、Rules / Values、Composer | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-docs](https://wproxy.org/docs/) |
| whistle-details | 观察 | 请求响应详情与匹配规则 | 原生 | Overview、Inspectors、Timeline 和 Server 错误；可查看已命中的规则。 | Network / Inspectors / Timeline / Frames | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-search | 观察 | 全文/正则与多条件过滤 | 原生 | URL、方法、头体、Host、IP、状态、类型、应用、标记、Composer 和错误筛选。 | Network / Inspectors / Timeline / Frames | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-capture-filter | 观察 | 捕获过滤与显示过滤分开 | 原生 | Include/Exclude Filter 作用未来请求；底部搜索也可过滤已显示请求，公开语义不同。 | Network / Inspectors / Timeline / Frames | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-ui-budget | 存储 | 列表预算与树形查看 | 原生 | Maximum Rows、可选列、域名/路径树、仅本机来源与大正文独立窗口。 | Network / Inspectors / Timeline / Frames | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-ws | 实时消息 | WebSocket/TCP Frames 观察 | 原生 | 连接开放期间查看应用数据和传输方向，可在 Frames Composer 向两端发送自定义数据。 | Network / Inspectors / Timeline / Frames、Local Agent API: network | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-frame-control | 实时消息 | 暂停、继续和忽略传输 | 原生 | Frames 的 Send/Receive、Pause、Ignore，以及对应初始规则控制。 | Network / Inspectors / Timeline / Frames | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-frame-script | 实时消息 | 消息脚本扩展 | 原生 | frameScript 对 WebSocket 和普通 TCP 数据帧进行脚本处理；不推断 SSE 事件级处理。 | Rules / Values | [whistle-framescript](https://wproxy.org/docs/rules/frameScript.html) |
| whistle-frame-cursor | 实时消息 | 帧增量游标与方向筛选 | 原生 | getFrames 支持 reqId、startId/startTime、count、latest、client/server，公开最大单次 120。 | Local Agent API: network | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-maplocal | 改写 | 本地文件、模板与原始响应映射 | 原生 | file/xfile、tpl/xtpl、rawfile/xrawfile 等一等规则类别。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-mapremote | 改写 | 远程 HTTP/WebSocket/隧道路由 | 原生 | http/https/ws/wss/tunnel 及协议继承，host/DNS 目标映射。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-request-rewrite | 改写 | 请求字段和内容改写 | 原生 | 方法、URL 参数/路径、头、Cookie、UA、鉴权字段、CORS、字符集、正文与 JSON 合并/替换。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-response-rewrite | 改写 | 响应字段与内容改写 | 原生 | 状态/重定向、头/Cookie/CORS、正文/JSON，以及 HTML/CSS/JS 增改与 trailers 规则。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-dynamic-rules | 改写 | 动态请求/响应规则脚本 | 原生 | reqScript/resScript、reqRules/resRules 按运行上下文生成规则；不是业务流程执行引擎。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html)、[whistle-reqscript](https://wproxy.org/docs/rules/reqScript.html) |
| whistle-throttle | 调试 | 延迟与带宽节流 | 原生 | 请求/响应延迟和传输速度是一等规则。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-write | 存储 | 请求响应正文或原始报文写出 | 原生 | reqWrite/reqWriteRaw/resWrite/resWriteRaw；可保存响应附件字节，具体规则区分正文和原始报文。 | Rules / Values | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html)、[whistle-reqwrite](https://wproxy.org/docs/rules/reqWrite.html)、[whistle-reswrite](https://wproxy.org/docs/rules/resWrite.html) |
| whistle-composer-build | 重发 | 完整请求构造与文件正文 | 原生 | 方法、URL/参数、头体、文件正文、HTTP2、自定义规则及是否套用全局规则。 | Composer、Local Agent API: network | [whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| whistle-replay | 重发 | 选中流量重发与批量次数 | 原生 | 列表 Replay 或 Composer 编辑后发送；Composer 次数上限 100。 | Composer | [whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-network](https://wproxy.org/docs/gui/network.html) |
| whistle-export | 导出 | 请求导入导出和 cURL | 原生 | Composer 提供 Import/Export/AsCURL；这里不把未核验的 HAR/SAZ 格式当成已证实。 | Composer | [whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| whistle-saved | 存储 | 保存会话与重开 | 原生 | 源码公开 network.saveSessions/getSavedSessions；Composer 自动保存最多 64 条历史。 | Local Agent API: network、Composer | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| whistle-ca | 证书 | CA 下载、系统安装与格式选择 | 原生 | CRT/CER/PEM 和移动二维码；CLI ca 在 Windows/macOS 自动安装，Linux 需手动。 | HTTPS / Custom Certs、w2 / whistle / wproxy | [whistle-https](https://wproxy.org/docs/gui/https.html)、[whistle-cli](https://wproxy.org/docs/cli.html) |
| whistle-cert-custom | 证书 | 自定义服务器证书和根证书 | 部分 | UI 上传成对服务器 key/cert；自定义根证书需指定目录并重启，不能直接在 UI 当普通服务器证书上传。 | HTTPS / Custom Certs | [whistle-https](https://wproxy.org/docs/gui/https.html) |
| whistle-auth | 访问控制 | 管理与只读游客账号 | 原生 | CLI 可设置管理账号和只读 guest 账号，单独 UI 端口与 allowOrigin。 | w2 / whistle / wproxy | [whistle-cli](https://wproxy.org/docs/cli.html) |
| whistle-proxy-auth | 访问控制 | 代理认证扩展 | 可选 | 代理请求认证通过插件 Hook/插件实现；不把管理界面登录等价成代理认证。 | Plugin Hooks / pipe | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| whistle-weinre | 浏览器调试 | 远程 DOM/CSS 检查 | 原生 | Weinre 为页面远程调试入口；需要规则接入，不是 Agent ARIA/ref 自动化。 | Weinre / Console | [whistle-weinre](https://wproxy.org/docs/gui/weinre.html) |
| whistle-console | 浏览器调试 | 远程 Console 日志 | 原生 | 页面 log 规则与 Console 界面记录远程 console。 | Weinre / Console | [whistle-console](https://wproxy.org/docs/gui/console.html)、[whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| whistle-nodeapi | 机器接口 | 官方 Local Agent API | 原生 | 规则、值、插件、网络、CA、HTTPS 与文件操作，Node 进程可调用。 | Local Agent API: network、Local Agent API: rules、Local Agent API: values、Local Agent API: plugins | [whistle-api](https://wproxy.org/docs/extensions/api.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-npm-embed | 机器接口 | NPM 模块嵌入运行 | 原生 | 官方提供将 Whistle 当 Node 模块使用的入口。 | Whistle NPM module | [whistle-npm](https://wproxy.org/docs/extensions/npm.html) |
| whistle-plugin-system | 扩展 | 插件 Hook 与内容管道 | 原生 | 自定义协议、证书、认证、动态规则、请求处理、流式内容 pipe；需要插件实现具体功能。 | Plugin Hooks / pipe | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-plugin-dev](https://wproxy.org/docs/extensions/dev.html) |
| whistle-plugin-ui | 扩展 | 插件界面扩展 | 原生 | 插件可扩展主面板/菜单、Inspectors、Composer 和 Tools，也可无界面运行。 | Plugin UI / menus / tabs | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| whistle-plugin-manage | 扩展 | 插件安装、更新和开关 | 原生 | UI/CLI 安装卸载，插件全局与单独开关、Node API 控制。 | Plugins、w2 / whistle / wproxy、Local Agent API: plugins | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-instance | 运行 | 多实例、存储隔离与配置 | 原生 | 每实例独立 storage 和端口；.whistlerc、config、baseDir、rcPath、系统代理 CLI。 | w2 / whistle / wproxy | [whistle-cli](https://wproxy.org/docs/cli.html) |
| whistle-status | 运行 | 状态、服务器和插件日志 | 原生 | w2 status/run、Server/Console 面板及 API getStatus；不称全自动安装修复 doctor。 | w2 / whistle / wproxy、Local Agent API: network | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-delivery | 运行 | 跨平台 CLI 与官方桌面客户端 | 原生 | Node>=16；Windows/macOS/Linux；文档说明无界面服务器/Docker 场景，但本次未确认官方镜像。 | w2 / whistle / wproxy、Whistle desktop client | [whistle-docs](https://wproxy.org/docs/)、[whistle-package](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/package.json)、[whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |

## 公开接口、命令和扩展目录

这里只记录产品公开的具名入口。MCP 工具、SDK 方法、CLI 参数、工作流块及规则协议分别保留原分类，不把它们当同一单位计分。精确接口名用于检索；用途是本文概括。

| 分类 | 接口 / 命令 / 配置 | 状态 | 用途与边界 | 证据 |
|---|---|---|---|---|
| Web UI | `Network / Inspectors / Timeline / Frames` | 原生 | 抓包列表、请求响应详情、性能时间、WebSocket/TCP 实时数据。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| Web UI | `Composer` | 原生 | 构造/编辑/重发、请求独立规则、HTTP2、文件正文、cURL。 | [whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| Web UI | `Rules / Values` | 原生 | 规则分组、优先级、匹配过滤及外部值管理。 | [whistle-docs](https://wproxy.org/docs/)、[whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| Web UI | `HTTPS / Custom Certs` | 原生 | HTTPS 抓包、HTTP2、自定义服务器证书管理与 CA 下载。 | [whistle-https](https://wproxy.org/docs/gui/https.html) |
| Web UI | `Weinre / Console` | 原生 | 按规则接入页面的远程 DOM/CSS 与 console 调试。 | [whistle-weinre](https://wproxy.org/docs/gui/weinre.html)、[whistle-console](https://wproxy.org/docs/gui/console.html) |
| Web UI | `Plugins` | 原生 | 安装、更新、开关、卸载插件，打开插件设置和扩展界面。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| CLI | `w2 / whistle / wproxy` | 原生 | start/restart/stop/status、add、proxy、ca、install/uninstall、exec、run；多个入口指向同一 CLI。 | [whistle-package](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/package.json)、[whistle-cli](https://wproxy.org/docs/cli.html) |
| Node API | `Local Agent API: network` | 原生 | getStatus/getSessions/getFrames/request/abort/saveSessions/getSavedSessions；有过滤和 live cursor。 | [whistle-api](https://wproxy.org/docs/extensions/api.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Node API | `Local Agent API: rules` | 原生 | 状态/开关、规则列表/读取/新增/选择、优先级及多选设置。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Node API | `Local Agent API: values` | 原生 | 值列表、读取与新增。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Node API | `Local Agent API: plugins` | 原生 | 插件全局开关、列表/读取、选择启用和取消。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Node API | `Local Agent API: CA / HTTPS / files / utils` | 原生 | CA、HTTPS 开关、临时文件、请求响应 JSON 辅助。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| 内部 HTTP API | `本地 Web UI HTTP endpoints` | 部分 | Node API 调用的 sessions/frames/composer/saved/rules 等接口，不与公开 MCP 等价。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| 嵌入 API | `Whistle NPM module` | 原生 | 将代理作为 Node 模块运行及集成。 | [whistle-npm](https://wproxy.org/docs/extensions/npm.html) |
| 插件 API | `Plugin Hooks / pipe` | 原生 | 请求响应规则/证书/代理认证/内容管道与 WebSocket/TCP 扩展。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-plugin-dev](https://wproxy.org/docs/extensions/dev.html) |
| 插件 API | `Plugin UI / menus / tabs` | 原生 | 扩展主面板、Inspectors、Composer、Tools、列表菜单与插件设置。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| 独立官方客户端 | `Whistle desktop client` | 可选 | 官方推荐的桌面安装和配置入口；与本仓库 CLI 包分开。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-docs](https://wproxy.org/docs/) |
| Local Agent Node API | `api.getRootCA` | 原生 | 获取本地代理CA证书数据；底层GET /cgi-bin/rootca | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.isEnabledHTTPS` | 原生 | 读取HTTPS捕获开关；底层GET /cgi-bin/is-enabled-https | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API：兼容别名 | `api.isEnabledHttps` | 原生 | isEnabledHTTPS的大小写兼容别名；底层GET /cgi-bin/is-enabled-https | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.setEnableHTTPS` | 原生 | 设置HTTPS捕获开关；底层POST /cgi-bin/intercept-https-connects | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API：兼容别名 | `api.setEnableHttps` | 原生 | setEnableHTTPS的大小写兼容别名；底层POST /cgi-bin/intercept-https-connects | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.createFile` | 原生 | 保存Buffer或文本为代理临时文件；底层POST /cgi-bin/temp/create | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.getFile` | 原生 | 按临时文件路径读取文本内容；底层GET /cgi-bin/temp/get | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.getStatus` | 原生 | 读取应用版本、存储名称与客户端形态；底层GET /cgi-bin/status | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.getSessions` | 原生 | 按游标、时间、类型、URL、方法、状态或头条件读取抓包记录；底层POST /cgi-bin/sessions | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.saveSessions` | 原生 | 把指定会话集合保存为可重开的命名记录；底层POST /cgi-bin/saved/save | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.getSavedSessions` | 原生 | 读取保存会话并解压返回会话数据；底层GET /cgi-bin/saved/sessions | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.getFrames` | 原生 | 按请求ID、方向、时间/游标读取WebSocket或Socket帧；底层POST /cgi-bin/frames | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.request` | 原生 | 通过Composer构造请求，可带正文、HTTP2和本次规则设置；底层POST /cgi-bin/composer | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.network.abort` | 原生 | 中止指定一个或多个捕获请求；底层POST /cgi-bin/abort | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.getStatus` | 原生 | 读取规则启停、优先级、多选和规则列表状态；底层GET /cgi-bin/rules/status | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.turnOff` | 原生 | 全局停用规则；底层POST /cgi-bin/rules/disable-all-rules | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.turnOn` | 原生 | 全局启用规则；底层POST /cgi-bin/rules/disable-all-rules | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.isMultiSelect` | 原生 | 读取是否允许同时选择多个规则文件；底层GET /cgi-bin/rules/is-multi-select | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.setMultiSelect` | 原生 | 设置规则文件多选模式；底层POST /cgi-bin/rules/allow-multiple-choice | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.setLaterFirst` | 原生 | 设置后置规则优先策略；底层POST /cgi-bin/rules/enable-back-rules-first | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.getList` | 原生 | 列出规则文件及内容和选择状态；底层GET /cgi-bin/rules/list | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.add` | 原生 | 新增或替换规则文件，可配置选中与置顶；底层POST /cgi-bin/rules/add | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.get` | 原生 | 读取指定规则文件内容；底层GET /cgi-bin/rules/value | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.select` | 原生 | 选中并启用指定规则文件；底层POST /cgi-bin/rules/select2 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.unselect` | 原生 | 取消指定规则文件选择或清除选择；底层POST /cgi-bin/rules/unselect2 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.rules.moveToTop` | 原生 | 将指定规则文件移动到顶部；底层POST /cgi-bin/rules/move-top | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.values.getList` | 原生 | 列出命名值及其内容；底层GET /cgi-bin/values/list | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.values.get` | 原生 | 读取指定命名值；底层GET /cgi-bin/values/value | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.values.add` | 原生 | 新增或替换命名值；底层POST /cgi-bin/values/add | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.getStatus` | 原生 | 读取插件全局状态；底层GET /cgi-bin/plugins/status | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.turnOff` | 原生 | 全局停用插件；底层POST /cgi-bin/plugins/disable-all-plugins | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.turnOn` | 原生 | 全局启用插件；底层POST /cgi-bin/plugins/disable-all-plugins | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.getList` | 原生 | 列出已知插件；底层GET /cgi-bin/plugins/list | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.get` | 原生 | 读取指定插件信息；底层GET /cgi-bin/plugins/plugin | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.select` | 原生 | 启用指定插件；底层POST /cgi-bin/plugins/disable-plugin | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent Node API | `api.plugins.unselect` | 原生 | 停用指定插件；底层POST /cgi-bin/plugins/disable-plugin | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent本地辅助函数 | `api.utils.createPattern` | 原生 | 生成规则匹配模式 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.isUtf8` | 原生 | 判断字节内容是否为UTF8 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getText` | 原生 | 从Buffer或base64内容按字符集取得文本 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getUtf8Buf` | 原生 | 将给定数据转换成UTF8 Buffer | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getReqBody` | 原生 | 取得抓包请求的文本正文 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getResBody` | 原生 | 取得抓包响应的文本正文 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getReqJson` | 原生 | 将抓包请求正文解析为JSON | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getResJson` | 原生 | 将抓包响应正文解析为JSON | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getRawReq` | 原生 | 组合请求行、头和文本正文用于查看 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getRawRes` | 原生 | 组合状态行、头和文本正文用于查看 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getRules` | 原生 | 读取会话命中的去重规则文本 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent本地辅助函数 | `api.utils.getTimings` | 原生 | 计算DNS、连接、请求、响应、下载、总耗时与首字节时间 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/rootca` | 部分 | 支撑api.getRootCA；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/is-enabled-https` | 部分 | 支撑api.isEnabledHTTPS, api.isEnabledHttps；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/intercept-https-connects` | 部分 | 支撑api.setEnableHTTPS, api.setEnableHttps；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/temp/create` | 部分 | 支撑api.createFile；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/temp/get` | 部分 | 支撑api.getFile；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/status` | 部分 | 支撑api.network.getStatus；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/sessions` | 部分 | 支撑api.network.getSessions；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/saved/save` | 部分 | 支撑api.network.saveSessions；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/saved/sessions` | 部分 | 支撑api.network.getSavedSessions；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/frames` | 部分 | 支撑api.network.getFrames；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/composer` | 部分 | 支撑api.network.request；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/abort` | 部分 | 支撑api.network.abort；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/rules/status` | 部分 | 支撑api.rules.getStatus；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/disable-all-rules` | 部分 | 支撑api.rules.turnOff, api.rules.turnOn；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/rules/is-multi-select` | 部分 | 支撑api.rules.isMultiSelect；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/allow-multiple-choice` | 部分 | 支撑api.rules.setMultiSelect；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/enable-back-rules-first` | 部分 | 支撑api.rules.setLaterFirst；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/rules/list` | 部分 | 支撑api.rules.getList；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/add` | 部分 | 支撑api.rules.add；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/rules/value` | 部分 | 支撑api.rules.get；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/select2` | 部分 | 支撑api.rules.select；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/unselect2` | 部分 | 支撑api.rules.unselect；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/rules/move-top` | 部分 | 支撑api.rules.moveToTop；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/values/list` | 部分 | 支撑api.values.getList；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/values/value` | 部分 | 支撑api.values.get；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/values/add` | 部分 | 支撑api.values.add；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/plugins/status` | 部分 | 支撑api.plugins.getStatus；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/plugins/disable-all-plugins` | 部分 | 支撑api.plugins.turnOff, api.plugins.turnOn；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/plugins/list` | 部分 | 支撑api.plugins.getList；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `GET /cgi-bin/plugins/plugin` | 部分 | 支撑api.plugins.get；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| Local Agent底层HTTP路径 | `POST /cgi-bin/plugins/disable-plugin` | 部分 | 支撑api.plugins.select, api.plugins.unselect；此处只枚举公开Node API调用的路径，不声称所有Web UI内部CGI均为稳定公共API。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-extra-api-transport](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| 规则协议：特殊规则 | `rule:@` | 原生 | 引入外部规则或设置客户端证书 | [whistle-rule-external](https://wproxy.org/docs/rules/@.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：特殊规则 | `rule:%` | 原生 | 设置插件变量值 | [whistle-rule-plugin-vars](https://wproxy.org/docs/rules/plugin-vars.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:file` | 原生 | 以本地文件/目录内容响应 | [whistle-rule-file](https://wproxy.org/docs/rules/file.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:xfile` | 原生 | 本地文件存在时响应，否则继续真实请求 | [whistle-rule-xfile](https://wproxy.org/docs/rules/xfile.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:tpl` | 原生 | 以本地模板生成响应 | [whistle-rule-tpl](https://wproxy.org/docs/rules/tpl.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:xtpl` | 原生 | 模板存在时生成响应，否则继续真实请求 | [whistle-rule-xtpl](https://wproxy.org/docs/rules/xtpl.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:rawfile` | 原生 | 使用含状态行/头/正文的本地响应文件 | [whistle-rule-rawfile](https://wproxy.org/docs/rules/rawfile.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：本地映射 | `rule:xrawfile` | 原生 | 本地完整响应文件存在时使用，否则继续真实请求 | [whistle-rule-xrawfile](https://wproxy.org/docs/rules/xrawfile.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：远程映射 | `rule:https` | 原生 | 将目标映射到指定HTTPS地址 | [whistle-rule-https](https://wproxy.org/docs/rules/https.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：远程映射 | `rule:http` | 原生 | 将目标映射到指定HTTP地址 | [whistle-rule-http](https://wproxy.org/docs/rules/http.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：远程映射 | `rule:wss` | 原生 | 映射TLS WebSocket目的地址 | [whistle-rule-wss](https://wproxy.org/docs/rules/wss.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：远程映射 | `rule:ws` | 原生 | 映射未加密WebSocket目的地址 | [whistle-rule-ws](https://wproxy.org/docs/rules/ws.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：远程映射 | `rule:tunnel` | 原生 | 映射隧道连接目的地址 | [whistle-rule-tunnel](https://wproxy.org/docs/rules/tunnel.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:host` | 原生 | 映射目标主机/IP或端口 | [whistle-rule-host](https://wproxy.org/docs/rules/host.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:xhost` | 原生 | 目标地址映射失败时使用原地址回退 | [whistle-rule-xhost](https://wproxy.org/docs/rules/xhost.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:proxy` | 原生 | 设置上游HTTP代理 | [whistle-rule-proxy](https://wproxy.org/docs/rules/proxy.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:xproxy` | 原生 | 上游HTTP代理失败时直接连接回退 | [whistle-rule-xproxy](https://wproxy.org/docs/rules/xproxy.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:https-proxy` | 原生 | 设置TLS连接的上游HTTP代理 | [whistle-rule-https-proxy](https://wproxy.org/docs/rules/https-proxy.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:xhttps-proxy` | 原生 | HTTPS上游代理失败时直接连接回退 | [whistle-rule-xhttps-proxy](https://wproxy.org/docs/rules/xhttps-proxy.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:socks` | 原生 | 设置上游SOCKS代理 | [whistle-rule-socks](https://wproxy.org/docs/rules/socks.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:xsocks` | 原生 | SOCKS上游失败时直接连接回退 | [whistle-rule-xsocks](https://wproxy.org/docs/rules/xsocks.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：目标地址与上游 | `rule:pac` | 原生 | 按PAC决定上游代理 | [whistle-rule-pac](https://wproxy.org/docs/rules/pac.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:urlParams` | 原生 | 合并或更新URL查询参数 | [whistle-rule-urlParams](https://wproxy.org/docs/rules/urlParams.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:pathReplace` | 原生 | 替换请求URL路径内容 | [whistle-rule-pathReplace](https://wproxy.org/docs/rules/pathReplace.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:sniCallback` | 原生 | 使用插件处理服务端证书选择 | [whistle-rule-sniCallback](https://wproxy.org/docs/rules/sniCallback.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:method` | 原生 | 改写请求HTTP方法 | [whistle-rule-method](https://wproxy.org/docs/rules/method.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:tlsOptions` | 原生 | 配置到服务端的TLS连接选项 | [whistle-rule-tlsOptions](https://wproxy.org/docs/rules/cipher.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqHeaders` | 原生 | 合并或改写请求头 | [whistle-rule-reqHeaders](https://wproxy.org/docs/rules/reqHeaders.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:forwardedFor` | 原生 | 设置请求来源转发头 | [whistle-rule-forwardedFor](https://wproxy.org/docs/rules/forwardedFor.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:ua` | 原生 | 设置User-Agent | [whistle-rule-ua](https://wproxy.org/docs/rules/ua.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:auth` | 原生 | 设置HTTP Basic认证信息 | [whistle-rule-auth](https://wproxy.org/docs/rules/auth.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:cache` | 原生 | 设置HTTP缓存相关头 | [whistle-rule-cache](https://wproxy.org/docs/rules/cache.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:referer` | 原生 | 设置Referer | [whistle-rule-referer](https://wproxy.org/docs/rules/referer.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:attachment` | 原生 | 设置下载附件文件名和内容处置 | [whistle-rule-attachment](https://wproxy.org/docs/rules/attachment.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqCharset` | 原生 | 设置请求字符集 | [whistle-rule-reqCharset](https://wproxy.org/docs/rules/reqCharset.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqCookies` | 原生 | 合并或改写请求Cookie | [whistle-rule-reqCookies](https://wproxy.org/docs/rules/reqCookies.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqCors` | 原生 | 改写请求跨域相关头 | [whistle-rule-reqCors](https://wproxy.org/docs/rules/reqCors.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqType` | 原生 | 设置请求Content-Type | [whistle-rule-reqType](https://wproxy.org/docs/rules/reqType.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqBody` | 原生 | 替换请求正文 | [whistle-rule-reqBody](https://wproxy.org/docs/rules/reqBody.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqMerge` | 原生 | 合并请求JSON或表单数据 | [whistle-rule-reqMerge](https://wproxy.org/docs/rules/reqMerge.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqPrepend` | 原生 | 在请求正文前添加内容 | [whistle-rule-reqPrepend](https://wproxy.org/docs/rules/reqPrepend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqAppend` | 原生 | 在请求正文后添加内容 | [whistle-rule-reqAppend](https://wproxy.org/docs/rules/reqAppend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqReplace` | 原生 | 按文本或规则替换请求正文 | [whistle-rule-reqReplace](https://wproxy.org/docs/rules/reqReplace.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqWrite` | 原生 | 将请求正文写入文件 | [whistle-rule-reqWrite](https://wproxy.org/docs/rules/reqWrite.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqWriteRaw` | 原生 | 将请求头与正文写入文件 | [whistle-rule-reqWriteRaw](https://wproxy.org/docs/rules/reqWriteRaw.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqRules` | 原生 | 为请求动态提供附加规则 | [whistle-rule-reqRules](https://wproxy.org/docs/rules/reqRules.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：请求改写 | `rule:reqScript` | 原生 | 通过请求阶段脚本生成规则 | [whistle-rule-reqScript](https://wproxy.org/docs/rules/reqScript.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:statusCode` | 原生 | 直接生成指定状态响应 | [whistle-rule-statusCode](https://wproxy.org/docs/rules/statusCode.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:replaceStatus` | 原生 | 替换上游响应状态码 | [whistle-rule-replaceStatus](https://wproxy.org/docs/rules/replaceStatus.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:redirect` | 原生 | 返回HTTP重定向响应 | [whistle-rule-redirect](https://wproxy.org/docs/rules/redirect.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:locationHref` | 原生 | 通过页面位置跳转重定向 | [whistle-rule-locationHref](https://wproxy.org/docs/rules/locationHref.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resHeaders` | 原生 | 合并或改写响应头 | [whistle-rule-resHeaders](https://wproxy.org/docs/rules/resHeaders.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:responseFor` | 原生 | 标注响应来源信息 | [whistle-rule-responseFor](https://wproxy.org/docs/rules/responseFor.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resCharset` | 原生 | 设置响应字符集 | [whistle-rule-resCharset](https://wproxy.org/docs/rules/resCharset.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resCookies` | 原生 | 合并或改写响应Cookie | [whistle-rule-resCookies](https://wproxy.org/docs/rules/resCookies.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resCors` | 原生 | 设置响应跨域相关头 | [whistle-rule-resCors](https://wproxy.org/docs/rules/resCors.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resType` | 原生 | 设置响应Content-Type | [whistle-rule-resType](https://wproxy.org/docs/rules/resType.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resBody` | 原生 | 替换响应正文 | [whistle-rule-resBody](https://wproxy.org/docs/rules/resBody.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resMerge` | 原生 | 合并响应JSON数据 | [whistle-rule-resMerge](https://wproxy.org/docs/rules/resMerge.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resPrepend` | 原生 | 在响应正文前添加内容 | [whistle-rule-resPrepend](https://wproxy.org/docs/rules/resPrepend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resAppend` | 原生 | 在响应正文后添加内容 | [whistle-rule-resAppend](https://wproxy.org/docs/rules/resAppend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resReplace` | 原生 | 按文本或规则替换响应正文 | [whistle-rule-resReplace](https://wproxy.org/docs/rules/resReplace.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:htmlPrepend` | 原生 | 在HTML内容前添加片段 | [whistle-rule-htmlPrepend](https://wproxy.org/docs/rules/htmlPrepend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:htmlBody` | 原生 | 替换HTML内容 | [whistle-rule-htmlBody](https://wproxy.org/docs/rules/htmlBody.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:htmlAppend` | 原生 | 在HTML内容后添加片段 | [whistle-rule-htmlAppend](https://wproxy.org/docs/rules/htmlAppend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:cssPrepend` | 原生 | 在样式内容前添加CSS | [whistle-rule-cssPrepend](https://wproxy.org/docs/rules/cssPrepend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:cssBody` | 原生 | 替换样式内容 | [whistle-rule-cssBody](https://wproxy.org/docs/rules/cssBody.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:cssAppend` | 原生 | 在样式内容后添加CSS | [whistle-rule-cssAppend](https://wproxy.org/docs/rules/cssAppend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:jsPrepend` | 原生 | 在脚本内容前添加JavaScript | [whistle-rule-jsPrepend](https://wproxy.org/docs/rules/jsPrepend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:jsBody` | 原生 | 替换脚本内容 | [whistle-rule-jsBody](https://wproxy.org/docs/rules/jsBody.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:jsAppend` | 原生 | 在脚本内容后添加JavaScript | [whistle-rule-jsAppend](https://wproxy.org/docs/rules/jsAppend.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:trailers` | 原生 | 设置HTTP尾部字段 | [whistle-rule-trailers](https://wproxy.org/docs/rules/trailers.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resWrite` | 原生 | 将响应正文写入文件 | [whistle-rule-resWrite](https://wproxy.org/docs/rules/resWrite.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resWriteRaw` | 原生 | 将响应头与正文写入文件 | [whistle-rule-resWriteRaw](https://wproxy.org/docs/rules/resWriteRaw.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resRules` | 原生 | 为响应阶段提供附加规则 | [whistle-rule-resRules](https://wproxy.org/docs/rules/resRules.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:resScript` | 原生 | 通过响应阶段脚本生成规则 | [whistle-rule-resScript](https://wproxy.org/docs/rules/resScript.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：通用处理 | `rule:pipe` | 原生 | 把请求响应内容交给插件管道处理 | [whistle-rule-pipe](https://wproxy.org/docs/rules/pipe.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：通用处理 | `rule:delete` | 原生 | 删除指定头、Cookie或参数等字段 | [whistle-rule-delete](https://wproxy.org/docs/rules/delete.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：通用处理 | `rule:headerReplace` | 原生 | 按规则替换请求或响应头中的内容 | [whistle-rule-headerReplace](https://wproxy.org/docs/rules/headerReplace.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：限速与延迟 | `rule:reqDelay` | 原生 | 延迟向服务端发送请求 | [whistle-rule-reqDelay](https://wproxy.org/docs/rules/reqDelay.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：限速与延迟 | `rule:resDelay` | 原生 | 延迟向客户端返回响应 | [whistle-rule-resDelay](https://wproxy.org/docs/rules/resDelay.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：限速与延迟 | `rule:reqSpeed` | 原生 | 限制请求发送速度 | [whistle-rule-reqSpeed](https://wproxy.org/docs/rules/reqSpeed.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：限速与延迟 | `rule:resSpeed` | 原生 | 限制响应发送速度 | [whistle-rule-resSpeed](https://wproxy.org/docs/rules/resSpeed.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：调试工具 | `rule:weinre` | 原生 | 启用页面远程DOM/CSS调试 | [whistle-rule-weinre](https://wproxy.org/docs/rules/weinre.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：调试工具 | `rule:log` | 原生 | 接入页面Console调试 | [whistle-rule-log](https://wproxy.org/docs/rules/log.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：设置 | `rule:style` | 原生 | 设置抓包列表的显示样式 | [whistle-rule-style](https://wproxy.org/docs/rules/style.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：设置 | `rule:lineProps` | 原生 | 为规则行附加属性设置 | [whistle-rule-lineProps](https://wproxy.org/docs/rules/lineProps.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：设置 | `rule:enable` | 原生 | 启用指定代理处理能力 | [whistle-rule-enable](https://wproxy.org/docs/rules/enable.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：设置 | `rule:disable` | 原生 | 关闭指定代理处理能力 | [whistle-rule-disable](https://wproxy.org/docs/rules/disable.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：过滤 | `rule:ignore` | 原生 | 忽略指定类型的规则处理 | [whistle-rule-ignore](https://wproxy.org/docs/rules/ignore.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：过滤 | `rule:skip` | 原生 | ignore规则的兼容名称 | [whistle-rule-skip](https://wproxy.org/docs/rules/skip.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：过滤 | `rule:excludeFilter` | 原生 | 排除满足条件的规则匹配 | [whistle-rule-excludeFilter](https://wproxy.org/docs/rules/excludeFilter.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：过滤 | `rule:includeFilter` | 原生 | 只让满足条件的请求应用规则 | [whistle-rule-includeFilter](https://wproxy.org/docs/rules/includeFilter.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：响应改写 | `rule:frameScript` | 原生 | 以脚本处理WebSocket/TCP应用数据 | [whistle-rule-frameScript](https://wproxy.org/docs/rules/frameScript.html)、[whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:ruleFile` | 部分 | 固定版本源码兼容名称，映射至 rulesFile；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:ruleScript` | 部分 | 固定版本源码兼容名称，映射至 rulesFile；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:rulesScript` | 部分 | 固定版本源码兼容名称，映射至 rulesFile；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:download` | 部分 | 固定版本源码兼容名称，映射至 attachment；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:http-proxy` | 部分 | 固定版本源码兼容名称，映射至 proxy；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:xhttp-proxy` | 部分 | 固定版本源码兼容名称，映射至 xproxy；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:status` | 部分 | 固定版本源码兼容名称，映射至 statusCode；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:hosts` | 部分 | 固定版本源码兼容名称，映射至 host；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:html` | 部分 | 固定版本源码兼容名称，映射至 htmlAppend；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:js` | 部分 | 固定版本源码兼容名称，映射至 jsAppend；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| 规则协议：兼容名称 | `rule:css` | 部分 | 固定版本源码兼容名称，映射至 cssAppend；不作为另一项独立产品能力计数。 | [whistle-extra-protocol-source](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |

## 统一比较维度的逐项依据

此表为横向总表每个格子的依据。未证实保留为未知，不转换为不存在；部分能力必须结合限定条件阅读。

| ID | 维度 | 状态 | 核对结论 | 证据 |
|---|---|---|---|---|
| <a id="d01"></a>D01 | 原生 MCP tools | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="d02"></a>D02 | MCP resources / prompts | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="d03"></a>D03 | stdio 接入 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="d04"></a>D04 | HTTP 远程机器接口 | 部分 | Local Agent API 通过本地 Web UI HTTP 端点工作；不是 MCP HTTP。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="d05"></a>D05 | 任务操作 CLI | 原生 | CLI 除启动外可管理规则、系统代理、证书和插件。 | [whistle-cli](https://wproxy.org/docs/cli.html) |
| <a id="d06"></a>D06 | 人工操作 UI | 原生 | Web 工作台及可选官方桌面客户端。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="d07"></a>D07 | 可编程 SDK / 插件 API | 原生 | 官方 Node API、NPM 模块与插件 Hooks。 | [whistle-api](https://wproxy.org/docs/extensions/api.html)、[whistle-npm](https://wproxy.org/docs/extensions/npm.html)、[whistle-plugin-dev](https://wproxy.org/docs/extensions/dev.html) |
| <a id="d08"></a>D08 | 本地运行 | 原生 | Node/桌面本地运行，无模型要求。 | [whistle-package](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/package.json)、[whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="d09"></a>D09 | 官方托管云 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="d10"></a>D10 | Docker / 容器交付 | 部分 | 有官方文档的 Docker 容器部署场景；本次未确认官方预构建镜像。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="d11"></a>D11 | 安装与运行诊断入口 | 原生 | w2 status、run 和 network.getStatus；覆盖实例而非完整 doctor。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="d12"></a>D12 | 工具按能力分组启用 | 部分 | 规则/插件可分组和开关；未确认 MCP tool profiles。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="b01"></a>B01 | 启动受控浏览器 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b02"></a>B02 | 连接已有浏览器 / CDP | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b03"></a>B03 | 多浏览器引擎 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b04"></a>B04 | headless / headed | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b05"></a>B05 | 独立会话 / Context | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b06"></a>B06 | 持久用户目录 / 配置 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b07"></a>B07 | 标签页与 popup | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b08"></a>B08 | iframe 操作 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b09"></a>B09 | 导航与历史 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b10"></a>B10 | 点击与指针动作 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b11"></a>B11 | 输入、键盘与表单 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b12"></a>B12 | 拖拽与滚动 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b13"></a>B13 | 原生对话框决策 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b14"></a>B14 | 文件上传 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b15"></a>B15 | 下载跟踪与保存 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b16"></a>B16 | 页面 JavaScript 执行 | 部分 | Weinre/Console 远程调试；非标准 browser_act API。 | [whistle-weinre](https://wproxy.org/docs/gui/weinre.html)、[whistle-console](https://wproxy.org/docs/gui/console.html) |
| <a id="b17"></a>B17 | 条件等待 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b18"></a>B18 | Cookie 管理 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b19"></a>B19 | 浏览器存储状态导入导出 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b20"></a>B20 | 设备与环境模拟 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="b21"></a>B21 | 网络离线 / 节流 | 原生 | 代理请求/响应延迟和速度规则，不是浏览器设备模拟。 | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="o01"></a>O01 | ARIA / 无障碍快照 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o02"></a>O02 | 元素引用 refs | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o03"></a>O03 | 增量快照 / 差异输出 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o04"></a>O04 | 快照搜索、裁剪或过滤 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o05"></a>O05 | 过期引用合同 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o06"></a>O06 | 页面 / 元素截图 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o07"></a>O07 | 标注截图 / 视觉定位 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o08"></a>O08 | HTML / DOM / 文本读取 | 部分 | Weinre 可检查远程 DOM/CSS；非 ARIA 或结构化提取。 | [whistle-weinre](https://wproxy.org/docs/gui/weinre.html) |
| <a id="o09"></a>O09 | Schema 约束结构化提取 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o10"></a>O10 | 自然语言定位 / act | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o11"></a>O11 | 定位自适应 / 恢复 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="o12"></a>O12 | 页面 PDF 导出 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="n01"></a>N01 | 独立代理捕获外部客户端 | 原生 | 独立代理捕获浏览器、App 和其他客户端。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-mobile](https://wproxy.org/docs/mobile.html) |
| <a id="n02"></a>N02 | HTTPS 解密与 CA | 原生 | CA、HTTPS 解密、自定义证书。 | [whistle-https](https://wproxy.org/docs/gui/https.html) |
| <a id="n03"></a>N03 | HTTP/2 支持 | 原生 | HTTP/2 设置与 Composer 入口。 | [whistle-https](https://wproxy.org/docs/gui/https.html)、[whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| <a id="n04"></a>N04 | HTTP/3 / QUIC 支持 | 未证实 | 已查官方协议清单，未找到 HTTP/3/QUIC 公开支持合同。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="n05"></a>N05 | TCP / UDP 非 HTTP 流量 | 部分 | 明确支持 TCP；未确认通用 UDP/DTLS 捕获。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="n06"></a>N06 | 代理模式与上游链路 | 原生 | HTTP/HTTPS/SOCKS/反向代理；规则可链 HTTP(S)/SOCKS 上游与 PAC。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md)、[whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="n07"></a>N07 | 请求 / 响应详情 | 原生 | Overview/Inspectors/Timeline 与 network.getSessions。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="n08"></a>N08 | 搜索、过滤与范围 | 原生 | 多条件搜索、捕获过滤、IP/应用/标记/错误等范围。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="n09"></a>N09 | 多值 / 有序响应头 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="n10"></a>N10 | 正文解码与格式展示 | 部分 | 原生 Inspectors/Pretty/字符集规则；Protobuf/自定义内容解码通过 pipe 插件。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| <a id="n11"></a>N11 | 请求 / 响应修改与 mock | 原生 | 丰富本地/远程映射及请求/响应规则。 | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="n12"></a>N12 | 断点与手动继续 | 部分 | WS/TCP Frames 可 Pause/Ignore/继续；未核实通用 HTTP 人工断点编辑器。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="n13"></a>N13 | 请求编辑与重发 | 原生 | Replay、Composer、network.request。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="n14"></a>N14 | 浏览器网络路由 / mock | 不适用 | 规则在代理层，不算浏览器 route 接口。 | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="n15"></a>N15 | HAR 导入 / 导出 | 未证实 | 本次查到 Composer 导入导出和保存会话，尚未确认当前 HAR 双向格式合同。 | [whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="n16"></a>N16 | cURL / 客户端代码导出 | 原生 | Composer AsCURL。 | [whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| <a id="n17"></a>N17 | API 结构 / OpenAPI | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="m01"></a>M01 | WebSocket 消息查看 | 原生 | Frames 与 getFrames 查看实时消息。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="m02"></a>M02 | WebSocket 双向 / 二进制 | 原生 | 方向与二进制 Buffer/base64 支持；TCP 和 WS 数据需区分。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="m03"></a>M03 | WebSocket 修改 / 注入 | 原生 | Frames Composer、frameScript 和插件处理。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-framescript](https://wproxy.org/docs/rules/frameScript.html) |
| <a id="m04"></a>M04 | SSE 事件级解析 | 未证实 | 已核对实时消息文档，明确的是 WS/TCP Frames，未证实 SSE event/id/data 专用解析。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="m05"></a>M05 | 压缩 SSE 增量解析 | 未证实 | 不能由 HTTP 压缩或 pipe 能力推断压缩 SSE 的增量事件解析。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="m06"></a>M06 | 开放连接期间查询消息 | 原生 | 开放连接下 Frames 和 getFrames 支持增量读取。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="m07"></a>M07 | 消息持久化与增量游标 | 部分 | getFrames 有 startId/startTime；会话另有保存/重开，未核实二者合成跨重启消息游标合同。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="m08"></a>M08 | 消息完整性 / 截断标记 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="w01"></a>W01 | 内置模型驱动执行循环 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w02"></a>W02 | 多模型 / 自定义模型 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w03"></a>W03 | 用户自定义工具 / 动作 | 部分 | 可扩展代理插件和 Node API，不是通用业务 Agent 自定义动作框架。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-api](https://wproxy.org/docs/extensions/api.html) |
| <a id="w04"></a>W04 | 多步骤工作流定义 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w05"></a>W05 | 条件、循环与并行 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w06"></a>W06 | 人工接管 / 审批节点 | 部分 | WS/TCP 暂停/继续允许人工调试；非业务步骤审批。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="w07"></a>W07 | 任务结果验证 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w08"></a>W08 | 步骤历史 / 动作回执 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w09"></a>W09 | 自动步骤检查点 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w10"></a>W10 | 跨进程恢复 / 状态重绑 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w11"></a>W11 | 未知结果处理 / 防重复执行 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w12"></a>W12 | 历史重放 / 动作缓存 | 部分 | HTTP 请求 Replay 与 Composer 历史，不是浏览器动作回放。 | [whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| <a id="w13"></a>W13 | 凭据 / 登录辅助 | 部分 | HTTP auth/Cookie 改写、自定义证书；不含浏览器登录自动化。 | [whistle-protocols](https://wproxy.org/docs/rules/protocols.html)、[whistle-https](https://wproxy.org/docs/gui/https.html) |
| <a id="w14"></a>W14 | 文件解析 / 文档数据处理 | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="w15"></a>W15 | 任务调度 / webhook | 不适用 | 本项目主线是网络调试代理，未把浏览器 Agent 合同作为核心定位。 | [whistle-readme](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| <a id="t01"></a>T01 | 浏览器 Console / 异常 | 原生 | Console 远程日志；需页面接入规则。 | [whistle-console](https://wproxy.org/docs/gui/console.html) |
| <a id="t02"></a>T02 | 性能 trace / 性能分析 | 部分 | Timeline 提供网络性能信息；不是浏览器 CPU 性能 trace。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="t03"></a>T03 | Heap / 内存诊断 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="t04"></a>T04 | 视频 / 执行 trace | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="t05"></a>T05 | 动作与网络关联视图 | 部分 | 规则命中与请求在同一详情；不是浏览器动作因果链。 | [whistle-network](https://wproxy.org/docs/gui/network.html) |
| <a id="t06"></a>T06 | 被动检查 / 诊断信号 | 部分 | Server/captureError 与 TLS 排查；未确认内置被动漏洞规则库。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-faq](https://wproxy.org/docs/faq.html) |
| <a id="t07"></a>T07 | 扩展安全测试模块 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="t08"></a>T08 | 差异比较 / 报告 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="s01"></a>S01 | 持久流量存储与重开 | 原生 | saveSessions/getSavedSessions、保存记录和 Composer 历史。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-composer](https://wproxy.org/docs/gui/composer.html) |
| <a id="s02"></a>S02 | 记录标签、备注与链接 | 部分 | 请求 Mark/样式和树形分组；未证实多步业务依赖链接。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-protocols](https://wproxy.org/docs/rules/protocols.html) |
| <a id="s03"></a>S03 | 二进制附件保存 | 原生 | resWrite/reqWrite 等保存正文或原始报文字节。 | [whistle-reswrite](https://wproxy.org/docs/rules/resWrite.html)、[whistle-reqwrite](https://wproxy.org/docs/rules/reqWrite.html) |
| <a id="s04"></a>S04 | 文件哈希与大小证据 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="s05"></a>S05 | 队列 / 丢弃 / 写入状态 | 未证实 | 已查官方文档目录、Local Agent API 与固定源码；未确认该维度的正式功能合同。 | [whistle-docs](https://wproxy.org/docs/) |
| <a id="s06"></a>S06 | 保留预算与清理范围 | 部分 | Maximum Rows、Composer 最多64历史、getFrames 单次120；不是统一长期磁盘预算。 | [whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="s07"></a>S07 | 证据打包 / 导出 | 原生 | 会话/请求导出和正文保存；不宣称自动业务证据报告。 | [whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js)、[whistle-composer](https://wproxy.org/docs/gui/composer.html)、[whistle-reswrite](https://wproxy.org/docs/rules/resWrite.html) |
| <a id="x01"></a>X01 | 配置文件 / 运行时配置 | 原生 | .whistlerc/config/CLI，运行时 Rules/Values/插件开关。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-api-src](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| <a id="x02"></a>X02 | 插件 / addon 生态 | 原生 | npm 插件、Hooks、pipe、自定义协议及 UI 扩展。 | [whistle-plugins](https://wproxy.org/docs/extensions/usage.html)、[whistle-plugin-dev](https://wproxy.org/docs/extensions/dev.html) |
| <a id="x03"></a>X03 | MCP 权限 / 只读提示 | 不适用 | 未确认官方 MCP；guest 账号是 Web UI 权限而非 MCP 只读注解。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-api](https://wproxy.org/docs/extensions/api.html) |
| <a id="x04"></a>X04 | 网络服务认证与访问控制 | 部分 | 管理/只读游客账号与 CORS；代理认证是插件能力。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |
| <a id="x05"></a>X05 | 进程资源清理与所有权 | 部分 | CLI 管理指定 storage 实例生命周期；没有借用浏览器上下文合同。 | [whistle-cli](https://wproxy.org/docs/cli.html) |
| <a id="x06"></a>X06 | 结构化日志与运行状态 | 原生 | status、Server/Console 和插件运行状态。 | [whistle-cli](https://wproxy.org/docs/cli.html)、[whistle-network](https://wproxy.org/docs/gui/network.html)、[whistle-plugins](https://wproxy.org/docs/extensions/usage.html) |

## 一手来源目录

| ID | 官方资料 / 固定源码 |
|---|---|
| whistle-meta | [master HEAD 元数据](https://api.github.com/repos/avwo/whistle/commits/master) |
| whistle-package | [包版本、许可证、Node 要求和 CLI 名](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/package.json) |
| whistle-readme | [官方项目定位与功能](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/README.md) |
| whistle-license | [MIT 许可证](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/LICENSE) |
| whistle-docs | [官方帮助及功能目录](https://wproxy.org/docs/) |
| whistle-network | [Network、过滤、Timeline 和 Frames](https://wproxy.org/docs/gui/network.html) |
| whistle-composer | [请求编辑、重发与保存](https://wproxy.org/docs/gui/composer.html) |
| whistle-https | [HTTPS/HTTP2 与自定义证书](https://wproxy.org/docs/gui/https.html) |
| whistle-cli | [CLI、配置、多实例与账号](https://wproxy.org/docs/cli.html) |
| whistle-api | [官方 Local Agent API](https://wproxy.org/docs/extensions/api.html) |
| whistle-api-src | [本地 API 完整方法与消息游标](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/api.js) |
| whistle-protocols | [全部规则操作类别](https://wproxy.org/docs/rules/protocols.html) |
| whistle-plugins | [插件安装、扩展位置与处理管道](https://wproxy.org/docs/extensions/usage.html) |
| whistle-plugin-dev | [插件开发 Hook/API](https://wproxy.org/docs/extensions/dev.html) |
| whistle-npm | [NPM 模块嵌入](https://wproxy.org/docs/extensions/npm.html) |
| whistle-reqscript | [请求阶段动态规则](https://wproxy.org/docs/rules/reqScript.html) |
| whistle-framescript | [WebSocket/TCP 帧脚本](https://wproxy.org/docs/rules/frameScript.html) |
| whistle-weinre | [远程 DOM 调试](https://wproxy.org/docs/gui/weinre.html) |
| whistle-console | [远程 Console](https://wproxy.org/docs/gui/console.html) |
| whistle-reqwrite | [请求数据保存](https://wproxy.org/docs/rules/reqWrite.html) |
| whistle-reswrite | [响应数据保存](https://wproxy.org/docs/rules/resWrite.html) |
| whistle-mobile | [移动设备接入](https://wproxy.org/docs/mobile.html) |
| whistle-faq | [协议接入限制与错误排查](https://wproxy.org/docs/faq.html) |
| whistle-extra-api-transport | [固定版本Agent API的HTTP路径/认证封装](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/bin/use.js) |
| whistle-extra-protocol-source | [固定版本规则操作名及兼容别名注册](https://github.com/avwo/whistle/blob/16607ba277b383d050bc6efce046b4c92cc0ae39/lib/rules/protocols.js) |
| whistle-rule-external | [规则协议 @](https://wproxy.org/docs/rules/@.html) |
| whistle-rule-plugin-vars | [规则协议 %](https://wproxy.org/docs/rules/plugin-vars.html) |
| whistle-rule-file | [规则协议 file](https://wproxy.org/docs/rules/file.html) |
| whistle-rule-xfile | [规则协议 xfile](https://wproxy.org/docs/rules/xfile.html) |
| whistle-rule-tpl | [规则协议 tpl](https://wproxy.org/docs/rules/tpl.html) |
| whistle-rule-xtpl | [规则协议 xtpl](https://wproxy.org/docs/rules/xtpl.html) |
| whistle-rule-rawfile | [规则协议 rawfile](https://wproxy.org/docs/rules/rawfile.html) |
| whistle-rule-xrawfile | [规则协议 xrawfile](https://wproxy.org/docs/rules/xrawfile.html) |
| whistle-rule-https | [规则协议 https](https://wproxy.org/docs/rules/https.html) |
| whistle-rule-http | [规则协议 http](https://wproxy.org/docs/rules/http.html) |
| whistle-rule-wss | [规则协议 wss](https://wproxy.org/docs/rules/wss.html) |
| whistle-rule-ws | [规则协议 ws](https://wproxy.org/docs/rules/ws.html) |
| whistle-rule-tunnel | [规则协议 tunnel](https://wproxy.org/docs/rules/tunnel.html) |
| whistle-rule-host | [规则协议 host](https://wproxy.org/docs/rules/host.html) |
| whistle-rule-xhost | [规则协议 xhost](https://wproxy.org/docs/rules/xhost.html) |
| whistle-rule-proxy | [规则协议 proxy](https://wproxy.org/docs/rules/proxy.html) |
| whistle-rule-xproxy | [规则协议 xproxy](https://wproxy.org/docs/rules/xproxy.html) |
| whistle-rule-https-proxy | [规则协议 https-proxy](https://wproxy.org/docs/rules/https-proxy.html) |
| whistle-rule-xhttps-proxy | [规则协议 xhttps-proxy](https://wproxy.org/docs/rules/xhttps-proxy.html) |
| whistle-rule-socks | [规则协议 socks](https://wproxy.org/docs/rules/socks.html) |
| whistle-rule-xsocks | [规则协议 xsocks](https://wproxy.org/docs/rules/xsocks.html) |
| whistle-rule-pac | [规则协议 pac](https://wproxy.org/docs/rules/pac.html) |
| whistle-rule-urlParams | [规则协议 urlParams](https://wproxy.org/docs/rules/urlParams.html) |
| whistle-rule-pathReplace | [规则协议 pathReplace](https://wproxy.org/docs/rules/pathReplace.html) |
| whistle-rule-sniCallback | [规则协议 sniCallback](https://wproxy.org/docs/rules/sniCallback.html) |
| whistle-rule-method | [规则协议 method](https://wproxy.org/docs/rules/method.html) |
| whistle-rule-tlsOptions | [规则协议 tlsOptions](https://wproxy.org/docs/rules/cipher.html) |
| whistle-rule-reqHeaders | [规则协议 reqHeaders](https://wproxy.org/docs/rules/reqHeaders.html) |
| whistle-rule-forwardedFor | [规则协议 forwardedFor](https://wproxy.org/docs/rules/forwardedFor.html) |
| whistle-rule-ua | [规则协议 ua](https://wproxy.org/docs/rules/ua.html) |
| whistle-rule-auth | [规则协议 auth](https://wproxy.org/docs/rules/auth.html) |
| whistle-rule-cache | [规则协议 cache](https://wproxy.org/docs/rules/cache.html) |
| whistle-rule-referer | [规则协议 referer](https://wproxy.org/docs/rules/referer.html) |
| whistle-rule-attachment | [规则协议 attachment](https://wproxy.org/docs/rules/attachment.html) |
| whistle-rule-reqCharset | [规则协议 reqCharset](https://wproxy.org/docs/rules/reqCharset.html) |
| whistle-rule-reqCookies | [规则协议 reqCookies](https://wproxy.org/docs/rules/reqCookies.html) |
| whistle-rule-reqCors | [规则协议 reqCors](https://wproxy.org/docs/rules/reqCors.html) |
| whistle-rule-reqType | [规则协议 reqType](https://wproxy.org/docs/rules/reqType.html) |
| whistle-rule-reqBody | [规则协议 reqBody](https://wproxy.org/docs/rules/reqBody.html) |
| whistle-rule-reqMerge | [规则协议 reqMerge](https://wproxy.org/docs/rules/reqMerge.html) |
| whistle-rule-reqPrepend | [规则协议 reqPrepend](https://wproxy.org/docs/rules/reqPrepend.html) |
| whistle-rule-reqAppend | [规则协议 reqAppend](https://wproxy.org/docs/rules/reqAppend.html) |
| whistle-rule-reqReplace | [规则协议 reqReplace](https://wproxy.org/docs/rules/reqReplace.html) |
| whistle-rule-reqWrite | [规则协议 reqWrite](https://wproxy.org/docs/rules/reqWrite.html) |
| whistle-rule-reqWriteRaw | [规则协议 reqWriteRaw](https://wproxy.org/docs/rules/reqWriteRaw.html) |
| whistle-rule-reqRules | [规则协议 reqRules](https://wproxy.org/docs/rules/reqRules.html) |
| whistle-rule-reqScript | [规则协议 reqScript](https://wproxy.org/docs/rules/reqScript.html) |
| whistle-rule-statusCode | [规则协议 statusCode](https://wproxy.org/docs/rules/statusCode.html) |
| whistle-rule-replaceStatus | [规则协议 replaceStatus](https://wproxy.org/docs/rules/replaceStatus.html) |
| whistle-rule-redirect | [规则协议 redirect](https://wproxy.org/docs/rules/redirect.html) |
| whistle-rule-locationHref | [规则协议 locationHref](https://wproxy.org/docs/rules/locationHref.html) |
| whistle-rule-resHeaders | [规则协议 resHeaders](https://wproxy.org/docs/rules/resHeaders.html) |
| whistle-rule-responseFor | [规则协议 responseFor](https://wproxy.org/docs/rules/responseFor.html) |
| whistle-rule-resCharset | [规则协议 resCharset](https://wproxy.org/docs/rules/resCharset.html) |
| whistle-rule-resCookies | [规则协议 resCookies](https://wproxy.org/docs/rules/resCookies.html) |
| whistle-rule-resCors | [规则协议 resCors](https://wproxy.org/docs/rules/resCors.html) |
| whistle-rule-resType | [规则协议 resType](https://wproxy.org/docs/rules/resType.html) |
| whistle-rule-resBody | [规则协议 resBody](https://wproxy.org/docs/rules/resBody.html) |
| whistle-rule-resMerge | [规则协议 resMerge](https://wproxy.org/docs/rules/resMerge.html) |
| whistle-rule-resPrepend | [规则协议 resPrepend](https://wproxy.org/docs/rules/resPrepend.html) |
| whistle-rule-resAppend | [规则协议 resAppend](https://wproxy.org/docs/rules/resAppend.html) |
| whistle-rule-resReplace | [规则协议 resReplace](https://wproxy.org/docs/rules/resReplace.html) |
| whistle-rule-htmlPrepend | [规则协议 htmlPrepend](https://wproxy.org/docs/rules/htmlPrepend.html) |
| whistle-rule-htmlBody | [规则协议 htmlBody](https://wproxy.org/docs/rules/htmlBody.html) |
| whistle-rule-htmlAppend | [规则协议 htmlAppend](https://wproxy.org/docs/rules/htmlAppend.html) |
| whistle-rule-cssPrepend | [规则协议 cssPrepend](https://wproxy.org/docs/rules/cssPrepend.html) |
| whistle-rule-cssBody | [规则协议 cssBody](https://wproxy.org/docs/rules/cssBody.html) |
| whistle-rule-cssAppend | [规则协议 cssAppend](https://wproxy.org/docs/rules/cssAppend.html) |
| whistle-rule-jsPrepend | [规则协议 jsPrepend](https://wproxy.org/docs/rules/jsPrepend.html) |
| whistle-rule-jsBody | [规则协议 jsBody](https://wproxy.org/docs/rules/jsBody.html) |
| whistle-rule-jsAppend | [规则协议 jsAppend](https://wproxy.org/docs/rules/jsAppend.html) |
| whistle-rule-trailers | [规则协议 trailers](https://wproxy.org/docs/rules/trailers.html) |
| whistle-rule-resWrite | [规则协议 resWrite](https://wproxy.org/docs/rules/resWrite.html) |
| whistle-rule-resWriteRaw | [规则协议 resWriteRaw](https://wproxy.org/docs/rules/resWriteRaw.html) |
| whistle-rule-resRules | [规则协议 resRules](https://wproxy.org/docs/rules/resRules.html) |
| whistle-rule-resScript | [规则协议 resScript](https://wproxy.org/docs/rules/resScript.html) |
| whistle-rule-pipe | [规则协议 pipe](https://wproxy.org/docs/rules/pipe.html) |
| whistle-rule-delete | [规则协议 delete](https://wproxy.org/docs/rules/delete.html) |
| whistle-rule-headerReplace | [规则协议 headerReplace](https://wproxy.org/docs/rules/headerReplace.html) |
| whistle-rule-reqDelay | [规则协议 reqDelay](https://wproxy.org/docs/rules/reqDelay.html) |
| whistle-rule-resDelay | [规则协议 resDelay](https://wproxy.org/docs/rules/resDelay.html) |
| whistle-rule-reqSpeed | [规则协议 reqSpeed](https://wproxy.org/docs/rules/reqSpeed.html) |
| whistle-rule-resSpeed | [规则协议 resSpeed](https://wproxy.org/docs/rules/resSpeed.html) |
| whistle-rule-weinre | [规则协议 weinre](https://wproxy.org/docs/rules/weinre.html) |
| whistle-rule-log | [规则协议 log](https://wproxy.org/docs/rules/log.html) |
| whistle-rule-style | [规则协议 style](https://wproxy.org/docs/rules/style.html) |
| whistle-rule-lineProps | [规则协议 lineProps](https://wproxy.org/docs/rules/lineProps.html) |
| whistle-rule-enable | [规则协议 enable](https://wproxy.org/docs/rules/enable.html) |
| whistle-rule-disable | [规则协议 disable](https://wproxy.org/docs/rules/disable.html) |
| whistle-rule-ignore | [规则协议 ignore](https://wproxy.org/docs/rules/ignore.html) |
| whistle-rule-skip | [规则协议 skip](https://wproxy.org/docs/rules/skip.html) |
| whistle-rule-excludeFilter | [规则协议 excludeFilter](https://wproxy.org/docs/rules/excludeFilter.html) |
| whistle-rule-includeFilter | [规则协议 includeFilter](https://wproxy.org/docs/rules/includeFilter.html) |
| whistle-rule-frameScript | [规则协议 frameScript](https://wproxy.org/docs/rules/frameScript.html) |
