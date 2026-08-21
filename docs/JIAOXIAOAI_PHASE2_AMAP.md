# 交小AI：高德官方 MCP 接入

本阶段只接入高德官方地图 MCP，复用 Open WebUI 原生的 Streamable HTTP、连接管理、模型工具绑定和访问授权能力，不部署额外 MCP bridge。

## 部署

1. 在高德开放平台创建 MCP Key。官方接入地址为 `https://mcp.amap.com/mcp?key=<key>`。
2. 复制 `deploy/jiaoxiaoai.env.example` 为未跟踪的 `deploy/jiaoxiaoai.env`，填写 `AMAP_MCP_KEY`。
3. 应用从 `deploy/managed/mcp/amap.yaml` 加载连接；已有数据库也会按同一 ID 更新这项托管配置：
   - Type：`MCP (Streamable HTTP)`
   - ID：`amap`
   - URL：上述官方地址
   - Authentication：`None`
   - Function Name Filter List：复制模板中的查询工具白名单
4. 模板默认启用并授权所有普通用户，但只开放查询类白名单。上线前可由 Admin 验证连接；如不需要高德，删除 YAML 后重新加载 MCP。
5. `server:mcp:amap` 会自动绑定到交小AI，无需网页重复勾选。

## 安全边界

- MCP Key 只保存在服务器环境和 Admin 配置中；普通用户访问 Tool Server 配置接口返回 `403`。
- 模板明确使用公开 read 授权；如需缩小范围，可把 `access_grants` 改成指定学生组。
- MCP 工具白名单按完整工具名精确匹配。目前只允许地理编码、POI、天气、距离、步行/驾车/公交/骑行路线查询。
- 不开放 `maps_ip_location`，也不自动开放高德以后可能新增的个人地图、导航、打车或其他动作工具。
- Admin 关闭或删除连接后，即使模型仍保留工具 ID，聊天请求也不会建立 MCP 连接。

官方文档：

- [高德地图 MCP Server 快速开始](https://lbs.amap.com/api/mcp-server/gettingstarted)
- [高德地图 MCP Server 工具说明](https://lbs.amap.com/api/mcp-server/summary)
