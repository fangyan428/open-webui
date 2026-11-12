# 托管 Tools

将管理后台导出的 Tools JSON 放在此目录。

默认会绑定到 `jiaoxiaoai` 模型。若只想导入但不绑定，可在插件 JSON 中设置：

```json
{
  "enabled": false
}
```

应用启动时会自动同步；也可以通过管理员的“同步插件”按钮手动触发。
