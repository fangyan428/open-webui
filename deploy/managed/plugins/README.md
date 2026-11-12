# 交小AI托管插件

`deploy/managed/plugins/` 是可在新服务器上重建的插件来源。应用启动时会把这里的内容同步到运行时数据库。

## 目录

- `functions/*.json`：Functions 导出文件，可包含 Filter、Action、Pipe 或 Event。
- `tools/*.json`：Tools 导出文件。

JSON 可以是 Open WebUI 后台直接导出的数组，也可以是单个插件对象或：

```json
{
  "plugins": []
}
```

## 从本机后台发布插件

1. 在交小AI管理后台安装并测试插件。
2. 在 Functions 或 Tools 页面选择“导出 JSON”。
3. 将导出文件放到对应目录：
   - Functions：`deploy/managed/plugins/functions/`
   - Tools：`deploy/managed/plugins/tools/`
4. 检查插件 ID、名称和代码，确认不包含真实密钥。
5. 提交并推送仓库，然后在云端拉取并重启交小AI。

仓库内的 `plugin-src/tools/*.py` 是可审查源码。修改源码后运行：

```bash
python scripts/build_managed_plugin_bundles.py
```

脚本会重新生成托管的 Tools JSON。不要把生成目录当作唯一源码直接修改。

## 同步行为

- 只更新或删除带有 `jiaoxiaoai_managed` 标记的插件。
- 后台手工创建的其他插件不会被覆盖或删除。
- 如果托管文件和本机非托管插件使用了相同 ID，同步会报错并保留现有插件。
- 任意一个托管文件格式错误或加载失败时，本次扫描不会应用任何修改。
- Functions 的 `is_active`、`is_global` 和可选 `valves` 会从导出文件恢复。
- Tools 默认绑定到 `jiaoxiaoai` 模型；可在 JSON 中设置 `"enabled": false` 暂时只导入而不绑定。
- 从目录删除插件文件并重新同步，会删除对应的托管插件，但不会影响非托管插件。

## 云端更新

```bash
git pull --ff-only
docker compose -f docker-compose.jiaoxiaoai.yaml up -d --build
```

只修改托管 JSON 时也可以重启应用容器触发同步：

```bash
docker compose -f docker-compose.jiaoxiaoai.yaml restart open-webui
```

管理员也可以在“交小AI设置 → 从服务器目录同步”中点击“同步插件”。

## 安全

Functions 和 Tools 会在服务器上执行 Python 代码，能够访问容器内文件、网络和环境变量。只合并经过审查的代码，并固定依赖版本。不要把 API Key、Token、密码或其他密钥直接写入 JSON；插件应通过环境变量读取私密配置。
