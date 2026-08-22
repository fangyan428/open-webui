# 交小AI托管配置

- 整个 `deploy/managed/` 随代码进入 Git，是可在新服务器上重建的声明式部分；这里不存放密钥、用户上传、聊天、数据库或向量索引。
- `knowledge/<目录>/manifest.yaml` 定义一个知识库，需要预置的原始资料放在同目录的 `files/` 下并提交到 Git。
- `mcp/*.yaml` 定义管理员统一开放的 MCP；密钥使用 `${ENV_NAME}` 引用私有 env 文件。
- 应用启动时自动同步，也可由 Admin 在“交小AI设置”中手动重试。
- 博查搜索由内部 `bocha-mcp` Streamable HTTP 服务提供，只开放只读的 `bocha_web_search`；密钥仅通过私有 `deploy/jiaoxiaoai.env` 注入。

Knowledge 示例：

```yaml
id: campus-guide
name: 校园指南
description: 面向学生的校内办事资料
```

仅放置已确认可随代码分发的机构资料；不要把真实 Token、Key 或学生上传文件提交到这里。
