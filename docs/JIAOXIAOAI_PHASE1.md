# 交小AI第一阶段部署与权限模型

本阶段使用 Open WebUI 原生账号验证流程，不改变认证中间件、用户表或 OAuth/SSO 路由，因此后续可继续接入 jAccount / OIDC。

## 首次部署

1. 复制 `deploy/jiaoxiaoai.env.example` 为 `deploy/jiaoxiaoai.env`，填写 Provider URL、API Key、Provider 返回的基础模型 ID 和稳定的 `WEBUI_SECRET_KEY`。
2. 启动：

   ```bash
   docker compose -f docker-compose.yaml -f docker-compose.jiaoxiaoai.yaml up -d --build
   ```

3. 第一个注册账号按 Open WebUI 原有逻辑成为管理员。环境中的 `DEFAULT_USER_ROLE=user` 让后续注册账号直接成为普通用户。
4. 启动时会一次性创建公开只读的 `交小AI` Workspace Model。它由 `system` 持有，管理员仍可在管理界面编辑；后续重启不会覆盖管理员修改。

## 管理员配置 RAG、Tools 和 MCP

- 在 Knowledge 中创建知识库并上传文件，然后编辑 `交小AI` 模型，把知识库附加到模型。不要向普通用户或 `Anyone` 授予 Knowledge read 权限。
- 在 Tools 或 Connections 中配置 Tool/OpenAPI/MCP 的 URL、Token 和认证。只对需要使用它的用户组（或 `Anyone`）授予 read，再把对应 Tool ID 附加到 `交小AI` 模型。
- 模型附加的 Tools/MCP 会由后端自动合并，不依赖用户浏览器中的个人选择。每次执行仍会经过 Tool 或 Connection 自身的 access grant 校验。

普通用户使用模型时，模型附带但未直接共享的 Knowledge 会被标为“仅模型 RAG”：后端只提供语义检索，不提供知识库浏览、文件列表、grep、全文查看或下载。Knowledge 与 File HTTP API 继续要求独立 read 权限。

## 恢复与迁移

完整恢复应备份并恢复 `open-webui` 数据卷；其中包含数据库、Knowledge 文件、向量索引、Workspace Model 和管理员在网页中的修改。`/api/v1/configs/export` 可额外导出平台配置，但其中可能含密钥，必须按秘密材料保管。

在空数据库上声明式恢复时：

- Provider、默认用户权限、默认模型与 Tool/MCP Connections 可放入未跟踪的 `deploy/jiaoxiaoai.env`。
- 可把稳定的 Knowledge ID 和 Tool ID 写入 `JIAOXIAOAI_MODEL_METADATA`。
- Knowledge ID 只有在对应数据卷或数据库/文件备份一并恢复时才有效。

环境 bootstrap 只创建缺失的 `交小AI` 模型，不会覆盖已存在的模型。日常变更应通过管理员界面完成。

## 验收检查

新建普通用户后验证：

1. 首页默认选中且只能正常使用 `交小AI`，无需填写 API Key。
2. 对知识内容提问可得到 RAG 回答；访问 `/workspace/knowledge` 会被前端拒绝，Knowledge 列表为空，直接请求知识库详情、文件数据和下载接口均被后端拒绝。
3. 模型绑定且已授权的 Tool/MCP 可调用；普通用户无法读取 `/api/v1/configs/tool_servers`，也看不到 URL、Token 或认证配置。
4. `/workspace/models`、`/workspace/tools` 和 API Key 设置不对普通用户显示，对应写接口在后端拒绝普通用户。

