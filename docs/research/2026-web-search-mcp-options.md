# “交小AI”第二阶段：Web Search 与 MCP 选型调研

> 调研基准日：2026-08-20  
> 仓库基线：Open WebUI `0.11.0`，`01f4282f1ffe0d6212f58d3afbeae21fffd0c4be`（2026-07-27）  
> 资料范围：协议、产品官方文档和项目官方仓库；社区 MCP 只以其自身仓库说明维护状态，并明确标注其不是上游数据提供方的官方实现。

## 结论

建议一期只上以下能力，避免把“能接入”误当成“新生真正需要”：

1. **联网搜索：Open WebUI 原生 Perplexity Search API**。它是五个候选中唯一在官方接口中明确支持 `search_language_filter` 数组、并以 `zh` 为示例的托管搜索 API，费用与 Brave 同为 **$5/1000 次成功请求**。但当前仓库的原生适配器只传 `query` 和 `max_results`，没有传中英文过滤条件；因此实施时只应做一个小的原生适配参数补齐，并在上线前做中英同条件评测。不要另建 Web Search MCP。
2. **地图 / POI / 路线：高德地图官方远程 MCP**。官方明确提供并推荐 Streamable HTTP，覆盖中国大陆 POI、地理编码、天气、步行/骑行/驾车/公交路线与距离。一期只允许查询类工具，关闭生成专属地图、导航唤端、打车等会产生外部动作或跳转的工具。
3. **开发者资料检索（可选，只授权计算机相关学生组）：Context7 官方远程 MCP**。只有 `resolve-library-id` 和 `query-docs` 两个只读工具，能力窄、风险面小。它不替代通用 Web Search。

以下能力有价值，但不应在一期默认启用：

- **校园实时信息**：优先级实际高于通用开发者工具，但需先申请上海交通大学开发者平台应用和 `bus`/`calendar` scope。拿到官方接口权限后，以最小只读 OpenAPI 服务提供校车实时信息和校历；不抓取登录后的校园网页，不在一期接个人课表、考试、校园卡。
- **学术论文**：Semantic Scholar 官方 API 数据质量和覆盖面适合学生，但目前找到的 Streamable HTTP MCP 是社区包装器，不是 Semantic Scholar 官方 MCP。建议先完成供应链、限流和接口验收再小范围接入；若风险不可接受，直接基于官方 REST API 做一个极小的只读 OpenAPI façade。
- **Bilibili**：Bilibili 官方开放平台本轮未找到面向全站的公共视频搜索和字幕读取 API。当前较成熟候选 `XZXZZX-Ai/bilibili-mcp` 是社区项目、依赖登录 Cookie 且只有 stdio；即使通过 Open WebUI 官方 `mcpo` bridge 接入，也应等合规、账号风控和运维方案确认后再试点。

**本轮没有 Exa、Brave、Tavily、Perplexity 的可运行 API Key，也没有统一可控的 SearXNG 实例，因此没有做同条件的搜索质量、延迟或可用性跑分。**下面的“推荐”是基于官方接口契约、成本、部署模式及本仓库适配代码的可落地性判断，不声称 Perplexity 已在真实新生问题上胜出。上线前必须完成文末的中英评测门槛。

## 1. Open WebUI 0.11.0 已有能力与边界

### 1.1 当前版本

- 本仓库 `package.json` 是 `0.11.0`，当前基线提交时间为 2026-07-27；Open WebUI 官方也将 [v0.11.0 标为 Latest](https://github.com/open-webui/open-webui/releases/tag/v0.11.0)。该版本还修复了 Web Search/URL 抓取相关的 NAT64 SSRF 绕过，部署不应降级到 `<0.11.0`，见 [官方安全公告 GHSA-8x5v-cpv7-8jjp](https://github.com/open-webui/open-webui/security/advisories/GHSA-8x5v-cpv7-8jjp)。
- 本仓库已含 Exa、Brave、Tavily、Perplexity Search、SearXNG 等原生适配器，见 [`backend/open_webui/retrieval/web/`](../../backend/open_webui/retrieval/web/)。因此通用联网搜索应继续走原生 Web Search，不增加同功能 MCP。
- v0.11.0 已提供文件搜索/读取、Knowledge、Code Interpreter 等能力，见 [v0.11.0 release notes](https://github.com/open-webui/open-webui/releases/tag/v0.11.0)；第二阶段不重复实现这些工具。

### 1.2 MCP / Tools

- Open WebUI 从 v0.6.31 起原生支持 MCP；当前只直接接受 **MCP Streamable HTTP**，不接受 stdio 或旧 SSE。MCP 只能由 Admin 在 External Tools 添加，普通用户即使获得 Direct Tool Servers 权限也只能自建 OpenAPI 连接。Admin 添加后再按用户/组设置 Access Control。见 [Open WebUI 官方 MCP 文档](https://docs.openwebui.com/features/extensibility/mcp/)。
- 本仓库 MCP 客户端已使用 `streamablehttp_client`，连接前执行授权检查，再按 `config.function_name_filter_list` 过滤工具名，见 [`middleware.py`](../../backend/open_webui/utils/middleware.py)。这足以实现“Admin 添加/启停/授权，Student 只调用授权能力”，无需建立另一套 MCP 注册中心。
- 当前 Admin 配置读取和写入均由 `get_admin_user` 保护，见 [`configs.py`](../../backend/open_webui/routers/configs.py)；普通用户工具列表只返回已启用且有 read grant 的连接，见 [`tools.py`](../../backend/open_webui/routers/tools.py)。空 `access_grants` 在本仓库中是 Admin-only，而不是 public。
- 官方建议大多数普通 REST 集成优先 OpenAPI（网关、审计、配额和可观测性更成熟），只有服务已经提供 MCP 或确实需要 MCP 协议时才选 MCP。见 [MCP vs OpenAPI](https://docs.openwebui.com/features/extensibility/mcp/#when-to-use-mcp-vs-openapi)。这也是校园 API 建议用 OpenAPI façade 的原因。
- 只有第三方仅提供 stdio/旧 SSE 时，才使用 Open WebUI 官方 [`mcpo`](https://github.com/open-webui/mcpo) 转成 OpenAPI；bridge 自身需设 bearer key，并只暴露内网。

### 1.3 RBAC 与 Secrets

- Open WebUI 权限是**加法合并**，没有 Deny；全局默认或任一群组授予就生效。应让全局默认保持最小权限，再向 `students`、`cs-students` 等组显式授权。Workspace Tools 可执行任意 Python，官方视为 root-equivalent，普通学生必须保持关闭。见 [Permissions](https://docs.openwebui.com/features/authentication-access/rbac/permissions/)。
- 普通学生可保留 Features → Web Search，但关闭 Workspace → Tools、Models、Knowledge、Skills 和 Features → Direct Tool Servers、API Keys。MCP 的 read grant 只授给目标组，不授 `*`。
- Web Search key、MCP bearer token、Semantic Scholar key、校园 OAuth client secret、Bilibili Cookie 都应来自服务器环境/Secret 管理器或 Admin-only 连接；不得使用 UserValves，也不得把 key 作为模型参数。若未来原生 Tool 使用 Valve，`password` 类型仅遮挡 UI，默认数据库仍是明文 JSON；必须设置 `ENABLE_VALVE_ENCRYPTION=true` 并固定 `WEBUI_SECRET_KEY`，见 [Valves 官方文档](https://docs.openwebui.com/features/extensibility/plugin/development/valves/#encrypting-valve-values-at-rest)。
- 高德官方远程 MCP 把 key 放在 URL query 中，可能进入反向代理访问日志。使用独立、限额的服务端 key，关闭 query 日志或在内网代理中注入/脱敏，不向学生展示连接 URL。

## 2. Web Search 候选的可落地比较

| 方案 | 官方中英文控制 | 成本 / 部署 | Open WebUI 0.11.0 当前适配 | 结论 |
|---|---|---|---|---|
| **Perplexity Search API** | `search_language_filter` 接受最多 10 个 ISO 639-1 语言；官方示例包含 `zh`，可组合 `zh,en`；另有 country | $5/1000 次成功 `/search`；一次请求可带最多 5 个 query，成功空结果也计费，无 token 费 | 原生；当前只传 `query,max_results`，没有传语言/country | **一期托管首选**，补一个小配置项后实测 |
| **Brave Search API** | 官方有 `country`、`search_lang`、`ui_lang`；默认分别是 `US`、`en`、`en-US` | $5/1000 请求，每月 $5 credit，50 RPS；独立索引，非自托管 | 原生；当前只传 `q,count`，意味着仍落到 US/en 默认 | 不选作一期默认；补地域语言后可进入同条件 A/B |
| **Tavily** | 有 `country=china` 结果提升，但官方接口未见等价的明确多语言过滤器 | 免费 1000 credits/月；PAYG $0.008/credit；basic 通常 1 credit、advanced 2 credits | 原生；当前只传 `query,max_results`，没有 country/search depth | 最省事的试用候选，但中英契约不如 Perplexity 明确 |
| **Exa** | 有 ISO `userLocation`；本轮官方 Search API 未见语言过滤器 | Search $7/1000 请求（最多 10 结果）；新账号/月度 credits；教育项目可申请 grant | 原生；当前传全文/高亮、`type=auto`，未传 location/category | 内容抽取、代码/出版物搜索有特色，但通用中英搜索更贵且语言控制不足；不另接其 Web Search MCP |
| **SearXNG** | 请求支持一个 `language`；官方明确说明不支持真正多语言，需语言前缀或复制不同语言引擎 | 开源自托管，无厂商按次费；需自行承担实例、上游配额、封禁和验证码 | 原生；当前会传 language/safesearch/time/categories | **自托管备选**，不是未经实测的中国搜索“稳赢方案” |

逐项一手资料：

- Perplexity：[语言过滤及 `zh` 示例](https://docs.perplexity.ai/docs/search/filters/language-filter)、[Search API 价格](https://docs.perplexity.ai/docs/getting-started/pricing#search-api-pricing)、[本仓库适配器](../../backend/open_webui/retrieval/web/perplexity_search.py)。
- Brave：[Web Search 参数及默认值](https://api-dashboard.search.brave.com/api-reference/web/search/get)、[价格](https://api-dashboard.search.brave.com/app/plans)、[查询日志最多保留 90 天的隐私说明](https://api-dashboard.search.brave.com/documentation/resources/privacy-notice)、[本仓库适配器](../../backend/open_webui/retrieval/web/brave.py)。
- Tavily：[Search API（含 China country boost）](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[价格](https://help.tavily.com/articles/8816424538-pricing)、[本仓库适配器](../../backend/open_webui/retrieval/web/tavily.py)。
- Exa：[Search API；`publication` 可返回作者、venue、citation 元数据](https://exa.ai/docs/reference/search)、[价格和教育 grant](https://exa.ai/pricing)、[官方远程 MCP](https://exa.ai/docs/reference/exa-mcp)、[本仓库适配器](../../backend/open_webui/retrieval/web/exa.py)。Exa MCP 的通用 `web_search_exa` 与原生 Web Search 重复，因此排除。
- SearXNG：[Search API](https://docs.searxng.org/dev/search_api.html)、[多语言限制](https://docs.searxng.org/admin/settings/settings_engines.html#example-multilingual-search)、[官方引擎配置](https://github.com/searxng/searxng/blob/master/searx/settings.yml)、[本仓库适配器](../../backend/open_webui/retrieval/web/searxng.py)。SearXNG 有 Baidu/Bilibili 等引擎配置，但这些默认关闭且依赖页面抓取；官方 Baidu adapter 也注明不使用官方 API，见 [`baidu.py`](https://github.com/searxng/searxng/blob/master/searx/engines/baidu.py)。因此需把验证码、封禁和结果波动纳入运维成本。

### 为什么最终选 Perplexity，而不是“零代码”的 Tavily

“交小AI”需要同时覆盖中文校园问题和英文课程/开发资料。Perplexity 给出了明确、可验证的多语言接口契约，且价格不高于 Brave。当前原生适配器的缺口很小：只需让 Admin 配置 `zh,en`（或根据查询语言选择）并把它传给已有 Search API，不改 Open WebUI 搜索架构。

这仍是**待基准测试的技术首选**。如果 API 在部署网络不可达、合同/数据政策不合适，或中文评测未达标，回退顺序是：

1. 自托管 SearXNG（校方掌控日志和出口，但要承担上游稳定性）；
2. Tavily（现有适配可立即试用，补 China boost 后进入 A/B）；
3. Brave（必须先补 `country/search_lang/ui_lang`，否则当前适配实际使用 US/en 默认）。

## 3. 面向学生的工具候选

### 3.1 一期：高德地图官方 MCP

高德官方文档明确支持 Streamable HTTP 和 Node.js I/O，并推荐 Streamable HTTP。官方 URL 为 `https://mcp.amap.com/mcp?key=...`，见 [快速接入](https://developer.amap.com/api/mcp-server/gettingstarted)。官方能力页列出地理/逆地理编码、天气、步行/骑行/驾车/公交路线、距离、关键词/周边/详情 POI 等 12+ 类实时能力，见 [能力概述](https://developer.amap.com/api/mcp-server/summary)。

一期策略：

- Admin 添加一个 MCP Streamable HTTP 连接，默认 disabled；验证后只授予 `students` 组 read。
- 首次 `tools/list` 后用 `function_name_filter_list` 精确 allowlist 查询类工具；工具名必须以服务实际返回为准，不根据文档中文标题猜测。
- 拒绝/隐藏生成专属地图、导航唤端、打车等工具。即使它们只返回 URL，也不属于一期只读数据查询的最小集合。
- 使用独立限额 key，禁止在日志、测试快照和前端响应中出现 key。

### 3.2 可选一期：Context7 官方 MCP

[Context7 官方仓库](https://github.com/upstash/context7)给出的远程地址是 `https://mcp.context7.com/mcp`，API key 通过 `Authorization: Bearer` 头传递；只暴露 `resolve-library-id` 和 `query-docs` 两个文档查询工具。适合 CS 新生查当前版本库文档，可仅授予 `cs-students` 组。

限制：Context7 索引中的项目由社区贡献；官方明确不保证全部文档的准确性、完整性或安全性，且抓取/解析后端不是开源的。工具返回内容必须当作不可信资料而非系统指令，并保留原始文档链接供核对。

### 3.3 下一批：上海交通大学官方校园 API

- [SJTU 开发者平台 API 概述](https://developer.sjtu.edu.cn/api/overview.html)提供受 OAuth2 保护的官方 REST API；应用需通过 jAccount/开发者平台申请。
- 官方 [OAuth scope 表](https://developer.sjtu.edu.cn/auth/oauth.html)明确：`bus`（`1<<51`）可用 client credentials（C）获取校园巴士/校区通勤班车的时刻表和实时信息；`calendar`（`1<<52`）支持授权码或 client credentials（A/C）。
- 一期校园能力只做 `GET bus schedule/realtime` 与只读校历查询。个人课程、考试等需用户授权，涉及更强身份隔离，留待后续独立安全设计。

目前没有找到 SJTU 官方 MCP。按 Open WebUI 官方建议，普通 REST API 应接一个校内最小只读 OpenAPI façade，由服务器持有 OAuth client secret、做限流和审计。**在校方应用审批、scope 和具体 endpoint 未确认前，不实现、不模拟、不抓网页。**

### 3.4 下一批评估：学术论文

[Semantic Scholar 官方 API](https://www.semanticscholar.org/product/api)当前覆盖约 2.14 亿论文、24.9 亿引用和 7900 万作者；大多数 endpoint 可匿名访问但共享限流，官方建议使用服务端 API key，初始 key 限流为 1 RPS。

当前较合适的社区包装器是 [`smaniches/semantic-scholar-mcp`](https://github.com/smaniches/semantic-scholar-mcp)：14 个论文、作者、引用和推荐查询工具，`>=1.5.0` 支持 Streamable HTTP，并提供发布 attestations/SBOM。它仍是小型社区项目而非 Ai2/Semantic Scholar 官方 MCP，且 HTTP 模式本身没有入站认证；若试点，应：

- 固定版本与容器 digest，只绑定内网，外层加认证/TLS；
- `SEMANTIC_SCHOLAR_API_KEY` 只放服务端环境，不使用已弃用、会进入模型工具参数的 `api_key`；
- 以 Semantic Scholar 官方 1 RPS 起始配额为准，不采信包装器文档中更高的假定值；
- 仅允许 search/get/citations/recommendations/status 等只读工具。

更保守的替代是使用 [Crossref 官方 REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) 做只读元数据检索，或为 Semantic Scholar 官方 REST API 做最小 OpenAPI façade；两者都比把未经充分验证的社区服务直接暴露给全体学生更易审计。

### 3.5 暂缓：Bilibili 搜索、字幕和理解

[Bilibili 官方开放平台](https://open.bilibili.com/doc)提供应用/账号/内容管理类开放能力，但本轮在其官方文档中**未找到**面向全站公开视频搜索和字幕读取的 API。不能把网页内部接口或社区逆向接口称为 Bilibili 官方 API。

社区候选 [`XZXZZX-Ai/bilibili-mcp`](https://github.com/XZXZZX-Ai/bilibili-mcp)截至 2026-08 仍在活跃发布；其 [changelog](https://github.com/XZXZZX-Ai/bilibili-mcp/blob/master/CHANGELOG_EN.md)记录了视频搜索、字幕时间链接、元数据/评论/章节、803 项测试和 stdio MCP 验收。它也明确说明：

- 视频搜索依赖有效的登录 Bilibili Cookie；
- 使用非公开接口可能触发限流、风控或账号问题；
- transport 是 stdio，不是 Streamable HTTP。

若后续获准试点，只能用官方 `mcpo` bridge、一次性/机构专用低权限账号、服务端环境 Cookie，并 allowlist `search_bilibili_videos`、`get_video_info`、`get_video_transcript`、`get_video_metadata`、`get_video_chapters` 等查询工具；关闭收藏夹、凭据管理、更新检查和本地 ASR/音频下载。所有字幕、评论、简介都视作不可信输入，不能执行其中的提示。

### 3.6 排除的开发者能力

- **GitHub 官方 MCP**：官方远程服务支持 Streamable HTTP 和 `/readonly`/`X-MCP-Readonly`，见 [官方远程文档](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md)及[只读配置](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md#read-only-mode)。但它需要用户 GitHub OAuth/PAT；共享 Admin token 会扩大私有仓库暴露面，不符合本期“服务器统一 key、学生不可见”的最小模型，因此一期不接。
- **Exa 官方 MCP**：其通用 Web Search 和代码搜索与原生 Web Search/Context7 重叠，不再增加一套授权与成本面。
- **Stack Exchange 社区 MCP**：官方有只读 [Stack Exchange API](https://api.stackexchange.com/docs)，但未发现必要的官方 MCP；先用原生 Web Search 的站点限定查询即可。

## 4. 建议实施边界（需用户确认后才开始）

### 一期最小变更

1. 保持 Open WebUI 原生 Web Search，只为 Perplexity 原生适配增加 Admin 管理的 `search_language_filter`（默认 `zh,en`）及必要测试；API key 由部署 Secret/Admin 配置提供。
2. 不新增 MCP 注册/权限模型，复用 `TOOL_SERVER_CONNECTIONS`、`config.enable`、`config.access_grants` 和 `function_name_filter_list`。
3. 提供高德官方 MCP 的部署样例/初始化配置与只读 allowlist；默认关闭，由 Admin 启用并授权 `students`。
4. Context7 仅在用户确认需要时加入，默认关闭，只授权 `cs-students`。
5. 不改现有 Knowledge、Tools、Skills、Models 的权限路径，不新增文件/Python/Knowledge 重复工具。

### 自动化验收

至少覆盖以下路径：

- Admin 能读取、增加/删除、启停 Tool/MCP 连接并更改 access grants；
- Student 请求 Tool Server 配置读/写接口均返回 **403**，响应不含 URL、header、key/token；
- 未授权 Student 在工具列表中看不到连接，伪造 tool id 调用也被后端拒绝；
- 授权 Student 只能看到并调用 enabled 连接 allowlist 中的查询工具，denylisted 工具不出现在 `tools/list` 且不能被直接调用；
- 普通 Student 仍不能管理 Knowledge、Workspace Tools、Skills、Models，现有第一阶段测试继续通过；
- mock provider 验证 Perplexity 请求确实携带预期的 `search_language_filter`，日志和错误响应不泄露 API key；
- MCP 超时、401/429、工具列表变化、服务关闭和 access grant 撤销均 fail closed。

### 上线前同条件搜索评测

拿到候选 key/实例后，再对 Perplexity、Tavily、补齐地域参数后的 Brave，以及自托管 SearXNG 运行同一组 20–30 个问题：

- 中文：校区/学院/选课/政策/近期通知、中文实体歧义、上海本地信息；
- 英文：课程概念、官方库文档、近期论文和英文新闻；
- 混合：英文术语 + 中文意图、中文实体 + 英文资料；
- 安全：SEO 垃圾、转载站、提示注入页面。

记录每个候选的官方来源命中率与 Recall@5、内容抓取成功率、重复结果率、p50/p95 延迟、429/5xx、单次成本和中国部署网络可达性。只有 Perplexity 在中文和英文两组均达到约定门槛后，才成为生产默认；否则按上述回退顺序调整。当前文档不把未运行的 benchmark 写成结果。

## 5. 实施前需要确认的选项

请在开始业务代码前确认：

1. 是否同意一期为 **Perplexity 原生 Web Search + 高德官方 MCP**；
2. 是否同时给 `cs-students` 增加 **Context7**，还是等第二批；
3. 是否启动 SJTU 开发者平台 `bus`/`calendar` 应用申请；
4. 是否接受 Bilibili 暂缓，待合规与专用账号方案明确后再试点。
