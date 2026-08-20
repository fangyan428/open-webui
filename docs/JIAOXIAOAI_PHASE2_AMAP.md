# 交小AI：高德官方 MCP 接入

本阶段只接入高德官方地图 MCP，复用 Open WebUI 原生的 Streamable HTTP、连接管理、模型工具绑定和访问授权能力，不部署额外 MCP bridge。

## 部署

1. 在高德开放平台创建 MCP Key。官方接入地址为 `https://mcp.amap.com/mcp?key=<key>`。
2. 复制 `deploy/jiaoxiaoai.env.example` 为未跟踪的 `deploy/jiaoxiaoai.env`，替换 `replace-with-amap-mcp-key`。
3. 新数据库会从 `TOOL_SERVER_CONNECTIONS` 初始化连接。已有数据库请在 **Admin Panel > Settings > Connections > Tool Servers** 添加或更新同一连接：
   - Type：`MCP (Streamable HTTP)`
   - ID：`amap`
   - URL：上述官方地址
   - Authentication：`None`
   - Function Name Filter List：复制模板中的查询工具白名单
4. 保持连接关闭，先执行 Admin 的连接验证。验证成功后，为学生组添加 `read` 授权，再开启连接。
5. `交小AI` 模型的工具 ID 为 `server:mcp:amap`。已有模型不会被环境变量覆盖，需要 Admin 在模型设置中勾选高德地图一次。

## 安全边界

- MCP Key 只保存在服务器环境和 Admin 配置中；普通用户访问 Tool Server 配置接口返回 `403`。
- 连接默认 `enable=false`、`access_grants=[]`。只有 Admin 授权的用户或组能够连接。
- MCP 工具白名单按完整工具名精确匹配。目前只允许地理编码、POI、天气、距离、步行/驾车/公交/骑行路线查询。
- 不开放 `maps_ip_location`，也不自动开放高德以后可能新增的个人地图、导航、打车或其他动作工具。
- Admin 关闭或删除连接后，即使模型仍保留工具 ID，聊天请求也不会建立 MCP 连接。

官方文档：

- [高德地图 MCP Server 快速开始](https://lbs.amap.com/api/mcp-server/gettingstarted)
- [高德地图 MCP Server 工具说明](https://lbs.amap.com/api/mcp-server/summary)
