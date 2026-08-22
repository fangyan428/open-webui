# 交小AI部署、入口与权限模型

SAI 展示页已作为 `/welcome` 路由并入 Open WebUI 的同一个前端构建。未登录访问根路径 `/` 时会先进入展示页，点击“进入交小AI”后跳转至 `/auth?redirect=/`，登录成功再进入原聊天首页。整个流程使用同源路由和 Open WebUI 原生账号验证，不改变认证中间件、用户表或 OAuth/SSO 路由，因此后续可继续接入 jAccount / OIDC。

## 首次部署

1. 复制私有运行时配置，设置严格权限：

   ```bash
   cp deploy/jiaoxiaoai.env.example deploy/jiaoxiaoai.env
   chmod 600 deploy/jiaoxiaoai.env
   ```

   填写 Provider URL、API Key、Provider 返回的基础模型 ID、`WEBUI_SECRET_KEY`，以及启用的 MCP 所引用的密钥。jAccount/OIDC 也在这个文件配置，不要把密钥写入根目录 `.env`。
2. 如需修改端口、镜像名或构建镜像源，再执行 `cp .env.example .env` 并编辑根目录 `.env`；否则 Compose 默认值已可直接使用。
3. 构建并启动：

   ```bash
   docker compose -f docker-compose.jiaoxiaoai.yaml up -d --build
   ```

4. 访问 `http://127.0.0.1:3001`。如未在 env 中预置管理员，第一个本地注册账号按 Open WebUI 原有逻辑成为管理员。托管策略会保持注册开启，并让后续账号直接成为普通用户，不经过 pending。
5. 启动时会创建公开只读的 `交小AI` Workspace Model，并恢复学生权限和默认模型。内置 Web Search 默认关闭且不会成为新会话的默认功能，联网搜索由模型绑定的托管 MCP 提供；管理员仍可按需显式启用内置搜索。管理员修改的 Provider、底层模型、名称、提示词和参数不会被重启覆盖。

`docker-compose.jiaoxiaoai.yaml` 是唯一部署入口：它从当前仓库构建一个包含 SAI 展示页、Open WebUI 前端和后端的镜像，同时构建内部博查 MCP 服务。默认只监听 `127.0.0.1:3001`；可通过根目录 `.env` 中的 `JIAOXIAOAI_LISTEN_ADDR` 和 `JIAOXIAOAI_PORT` 调整。需要直接向局域网/公网暴露时才改为 `0.0.0.0`；生产优先保持 `127.0.0.1` 并由 Nginx/Caddy 提供 HTTPS。

## 服务器迁移与更新

新服务器需要的内容只有：

- 完整 Git 工作树（包括 `Dockerfile`、`docker-compose.jiaoxiaoai.yaml`、`backend/`、`src/`、`deploy/managed/` 和 `deploy/bocha-mcp/`）；
- 不进 Git 的 `deploy/jiaoxiaoai.env`；
- 如果迁移现有账号、聊天、Admin 修改、网页上传和向量索引，再安全复制整个 `.cptr/jiaoxiaoai-data/`。新部署不必复制该目录，它会在首启时创建，并根据 `deploy/managed/` 重建预置 Knowledge/MCP。

以后更新代码时保留 `deploy/jiaoxiaoai.env` 和 `.cptr/jiaoxiaoai-data/`，然后执行：

```bash
git pull --ff-only
docker compose -f docker-compose.jiaoxiaoai.yaml up -d --build
```

Compose 只重建/替换容器，不会删除宿主机持久化目录。不要手动删除 `.cptr/jiaoxiaoai-data/`。

## Knowledge 目录与网页追加

- 每个知识库使用 `deploy/managed/knowledge/<目录>/manifest.yaml`，原始资料放在同目录的 `files/`。
- 启动会自动解析、切块、向量化并绑定到交小AI；文件内容哈希未变化时不会重复处理。
- Admin 仍可从网页向同一 Knowledge 追加普通文件。这些文件保存在 `/app/backend/data`，目录同步不会删除或覆盖它们。
- 服务器托管文件必须回到目录中修改；网页编辑或删除接口会返回 `409`。缺目录或坏 manifest 时同步不会执行删除。

## MCP 目录

- 每个连接使用 `deploy/managed/mcp/*.yaml`；`${ENV_NAME}` 会从私有 `deploy/jiaoxiaoai.env` 解析，仓库不保存真实密钥。
- 启动会自动载入并绑定到交小AI；默认包含高德 MCP 和只读的博查 `bocha_web_search`。坏 YAML 或缺密钥不会阻止聊天和 RAG，也不会清空上一次有效配置。
- 模板内必须明确 `enable`、工具白名单和 `access_grants`。普通用户只能调用被开放的工具，不能查看 URL、Token 或认证信息。
- Admin 的“交小AI设置”页可手动重试 Knowledge 同步或 MCP 加载。

普通用户使用模型时，模型附带但未直接共享的 Knowledge 会被标为“仅模型 RAG”：后端只提供语义检索，不提供知识库浏览、文件列表、grep、全文查看或下载。Knowledge 与 File HTTP API 继续要求独立 read 权限。

## 数据持久化（第一阶段）

第一阶段不增加备份系统或单独的 Admin overlay 目录。Compose 的 `.cptr/jiaoxiaoai-data` 挂载会持久化数据库、网页上传、聊天和向量索引；托管目录资料可在空数据卷上重新构建。若主动删除整个数据目录，网页追加文件和 Admin 修改会一并丢失，这是当前已接受的范围。

## 声明式与 Admin UI 的边界

- 可声明式管理：Provider/API 环境变量、jAccount/OIDC、首次管理员、交小AI 模型首次创建、用户权限策略、预置 Knowledge 文件、MCP 连接及密钥引用。
- 仍可在 Admin UI 修改：Provider、底层模型、模型名称/提示词/参数、内置 Web Search，以及向 Knowledge 追加网页托管文件。这些内容保存到 `.cptr/jiaoxiaoai-data/`，重启不覆盖。
- 仍需外部系统操作：在 jAccount 管理端注册 Client/回调 URL、在模型和 MCP 供应商创建/轮换 Key，以及生产域名、HTTPS 和备份策略。这些不能安全地由仓库代替。

## 验收检查

新建普通用户后验证：

1. 首页默认选中且只能正常使用 `交小AI`，无需填写 API Key。
2. 对知识内容提问可得到 RAG 回答；访问 `/workspace/knowledge` 会被前端拒绝，Knowledge 列表为空，直接请求知识库详情、文件数据和下载接口均被后端拒绝。
3. 模型绑定且已授权的 Tool/MCP 可调用；普通用户无法读取 `/api/v1/configs/tool_servers`，也看不到 URL、Token 或认证配置。
4. `/workspace/models`、`/workspace/tools` 和 API Key 设置不对普通用户显示，对应写接口在后端拒绝普通用户。
