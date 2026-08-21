# 交小AI托管配置

- `knowledge/<目录>/manifest.yaml` 定义一个知识库，资料放在同目录的 `files/` 下。
- `mcp/*.yaml` 定义管理员统一开放的 MCP；密钥使用 `${ENV_NAME}` 引用私有 env 文件。
- 应用启动时自动同步，也可由 Admin 在“交小AI设置”中手动重试。

Knowledge 示例：

```yaml
id: campus-guide
name: 校园指南
description: 面向学生的校内办事资料
```

不要把真实 Token、Key 或学生上传文件提交到这里。
