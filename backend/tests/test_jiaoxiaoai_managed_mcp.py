from unittest.mock import AsyncMock

import pytest
from open_webui.utils.jiaoxiaoai_mcp import load_mcp_file, sync_managed_mcp


def test_managed_mcp_resolves_secret_without_storing_it_in_yaml(monkeypatch, tmp_path):
    monkeypatch.setenv('CAMPUS_TOKEN', 'server-secret')
    path = tmp_path / 'campus.yaml'
    path.write_text(
        'url: https://mcp.example/${CAMPUS_TOKEN}\n'
        'type: mcp\n'
        'config:\n  enable: true\n  function_name_filter_list: search\n  access_grants: []\n'
        'info:\n  id: campus\n  name: Campus\n',
        encoding='utf-8',
    )

    result = load_mcp_file(path)

    assert result['url'] == 'https://mcp.example/server-secret'


@pytest.mark.asyncio
async def test_invalid_scan_preserves_last_good_connections(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MCP_DIR', str(tmp_path))
    (tmp_path / 'broken.yaml').write_text('type: mcp\n', encoding='utf-8')
    upsert = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_mcp.Config.upsert', upsert)

    result = await sync_managed_mcp()

    assert result['errors']
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_managed_connection_replaces_legacy_connection_with_same_id(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MCP_DIR', str(tmp_path))
    monkeypatch.setenv('MCP_URL', 'https://new.example/mcp')
    (tmp_path / 'campus.yaml').write_text(
        'url: ${MCP_URL}\n'
        'type: mcp\n'
        'config:\n  enable: true\n  function_name_filter_list: search\n  access_grants: []\n'
        'info:\n  id: campus\n  name: Campus\n',
        encoding='utf-8',
    )
    legacy = {'url': 'https://old.example', 'type': 'mcp', 'config': {}, 'info': {'id': 'campus'}}
    native = {'url': 'https://other.example', 'type': 'mcp', 'config': {}, 'info': {'id': 'other'}}
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_mcp.Config.get', AsyncMock(return_value=[legacy, native]))
    upsert = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_mcp.Config.upsert', upsert)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_mcp._bind_managed_tools', AsyncMock())

    result = await sync_managed_mcp()

    assert result['loaded'] == 1
    saved = upsert.await_args.args[0]['tool_server.connections']
    assert [item['info']['id'] for item in saved] == ['other', 'campus']
    assert saved[-1]['url'] == 'https://new.example/mcp'
