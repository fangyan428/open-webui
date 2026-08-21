import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from fastapi import HTTPException
from open_webui.models.users import UserModel
from open_webui.routers import configs
from open_webui.routers import tools as tools_router
from open_webui.utils import middleware
from open_webui.utils.auth import get_admin_user_forbidden

REPO_ROOT = Path(__file__).resolve().parents[2]
AMAP_TOOL_NAMES = {
    'maps_regeocode',
    'maps_geo',
    'maps_weather',
    'maps_bicycling',
    'maps_direction_walking',
    'maps_direction_driving',
    'maps_direction_transit_integrated',
    'maps_distance',
    'maps_text_search',
    'maps_around_search',
    'maps_search_detail',
}


def user(user_id: str = 'student-1', role: str = 'user') -> UserModel:
    return UserModel.model_construct(id=user_id, role=role)


def env_json(name: str):
    env_file = REPO_ROOT / 'deploy' / 'jiaoxiaoai.env.example'
    for line in env_file.read_text(encoding='utf-8').splitlines():
        key, separator, value = line.partition('=')
        if separator and key == name:
            return json.loads(value)
    raise AssertionError(f'{name} is missing from {env_file}')


def amap_connection() -> dict:
    path = REPO_ROOT / 'deploy' / 'managed' / 'mcp' / 'amap.yaml'
    connection = yaml.safe_load(path.read_text(encoding='utf-8'))
    connection['url'] = connection['url'].replace('${AMAP_MCP_KEY}', 'replace-with-amap-mcp-key')
    return copy.deepcopy(connection)


def test_amap_bootstrap_uses_official_streamable_http_and_query_only_allowlist():
    connection = amap_connection()
    configured_tools = set(connection['config']['function_name_filter_list'].split(','))

    assert connection['url'] == 'https://mcp.amap.com/mcp?key=replace-with-amap-mcp-key'
    assert connection['type'] == 'mcp'
    assert connection['auth_type'] == 'none'
    assert connection['config']['enable'] is True
    assert connection['config']['access_grants'] == [
        {'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}
    ]
    assert configured_tools == AMAP_TOOL_NAMES
    assert 'maps_ip_location' not in configured_tools
    assert env_json('JIAOXIAOAI_MODEL_METADATA')['toolIds'] == []


def test_student_tool_server_configuration_access_returns_403_and_no_secret(monkeypatch):
    get_config = AsyncMock()
    upsert_config = AsyncMock()
    monkeypatch.setattr(configs.Config, 'get', get_config)
    monkeypatch.setattr(configs.Config, 'upsert', upsert_config)

    with pytest.raises(HTTPException) as exc:
        get_admin_user_forbidden(user())

    assert exc.value.status_code == 403
    assert 'replace-with-amap-mcp-key' not in str(exc.value.detail)
    get_config.assert_not_awaited()
    upsert_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_can_enable_authorize_and_delete_amap_connection(monkeypatch):
    connection = amap_connection()
    connection['config']['enable'] = True
    connection['config']['access_grants'] = [
        {
            'principal_type': 'user',
            'principal_id': 'student-1',
            'permission': 'read',
        }
    ]

    get_config = AsyncMock(return_value=[])
    upsert_config = AsyncMock()
    refresh_servers = AsyncMock(return_value=[])
    publish = AsyncMock()
    monkeypatch.setattr(configs.Config, 'get', get_config)
    monkeypatch.setattr(configs.Config, 'upsert', upsert_config)
    monkeypatch.setattr(configs, 'set_tool_servers', refresh_servers)
    monkeypatch.setattr(configs, 'publish_event', publish)

    request = Mock()
    enabled = await configs.set_tool_servers_config(
        request,
        configs.ToolServersConfigForm(TOOL_SERVER_CONNECTIONS=[connection]),
        user('admin-1', 'admin'),
    )
    deleted = await configs.set_tool_servers_config(
        request,
        configs.ToolServersConfigForm(TOOL_SERVER_CONNECTIONS=[]),
        user('admin-1', 'admin'),
    )

    saved = enabled['TOOL_SERVER_CONNECTIONS'][0]
    assert saved['config']['enable'] is True
    assert saved['config']['access_grants'][0]['principal_id'] == 'student-1'
    assert deleted == {'TOOL_SERVER_CONNECTIONS': []}
    assert upsert_config.await_args_list[0].args[0] == {'tool_server.connections': [saved]}
    assert upsert_config.await_args_list[1].args[0] == {'tool_server.connections': []}
    assert refresh_servers.await_count == 2
    assert publish.await_count == 2


@pytest.mark.asyncio
async def test_authorized_student_tool_catalog_does_not_expose_amap_key(monkeypatch):
    connection = amap_connection()
    connection['config']['enable'] = True
    connection['config']['access_grants'] = [
        {
            'principal_type': 'user',
            'principal_id': 'student-1',
            'permission': 'read',
        }
    ]

    monkeypatch.setattr(tools_router, 'ENABLE_PLUGINS', False)
    monkeypatch.setattr(tools_router, 'get_tool_servers', AsyncMock(return_value=[]))
    monkeypatch.setattr(tools_router.Config, 'get', AsyncMock(return_value=[connection]))
    monkeypatch.setattr(tools_router.Groups, 'get_groups_by_member_id', AsyncMock(return_value=[]))
    monkeypatch.setattr(tools_router, 'has_access', AsyncMock(return_value=True))

    result = await tools_router.get_tools(request=Mock(), user=user(), db=Mock())
    payload = [tool.model_dump(mode='json') for tool in result]
    serialized = json.dumps(payload)

    assert [tool['id'] for tool in payload] == ['server:mcp:amap']
    assert payload[0]['name'] == '高德地图'
    assert 'replace-with-amap-mcp-key' not in serialized
    assert 'https://mcp.amap.com' not in serialized


@pytest.mark.asyncio
async def test_authorized_student_connects_and_only_sees_exact_allowlisted_tools(monkeypatch):
    connection = amap_connection()
    connection['config']['enable'] = True
    connection['config']['access_grants'] = [
        {
            'principal_type': 'user',
            'principal_id': 'student-1',
            'permission': 'read',
        }
    ]

    fake_client = Mock()
    fake_client.connect = AsyncMock()
    fake_client.list_tool_specs = AsyncMock(
        return_value=[
            {'name': 'maps_geo', 'description': 'allowed', 'parameters': {}},
            {'name': 'maps_ip_location', 'description': 'not selected', 'parameters': {}},
            {'name': 'personal_map', 'description': 'action', 'parameters': {}},
            {'name': 'danger_maps_geo', 'description': 'suffix collision', 'parameters': {}},
        ]
    )
    fake_client.call_tool = AsyncMock(return_value={'content': 'Shanghai'})
    client_factory = Mock(return_value=fake_client)

    monkeypatch.setattr(middleware.Config, 'get', AsyncMock(return_value=[connection]))
    monkeypatch.setattr(
        'open_webui.utils.access_control.Groups.get_groups_by_member_id',
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(middleware, 'build_tool_server_headers', AsyncMock(return_value=({}, {})))
    monkeypatch.setattr(middleware, 'MCPClient', client_factory)

    result = await middleware.connect_mcp_server(
        request=Mock(),
        server_id='amap',
        user=user(),
        metadata={},
        extra_params={},
    )

    assert result is not None
    connected_client, specs = result
    assert [spec['name'] for spec in specs] == ['maps_geo']
    fake_client.connect.assert_awaited_once_with(url=connection['url'], headers=None)
    assert await connected_client.call_tool('maps_geo', {'address': '上海交通大学'}) == {'content': 'Shanghai'}


@pytest.mark.parametrize(
    ('enabled', 'access_grants'),
    [
        (False, [{'principal_type': 'user', 'principal_id': 'student-1', 'permission': 'read'}]),
        (True, []),
    ],
)
@pytest.mark.asyncio
async def test_disabled_or_unauthorized_amap_connection_fails_closed(monkeypatch, enabled, access_grants):
    connection = amap_connection()
    connection['config']['enable'] = enabled
    connection['config']['access_grants'] = access_grants
    client_factory = Mock()
    monkeypatch.setattr(middleware.Config, 'get', AsyncMock(return_value=[connection]))
    monkeypatch.setattr(middleware, 'MCPClient', client_factory)

    result = await middleware.connect_mcp_server(
        request=Mock(),
        server_id='amap',
        user=user(),
        metadata={},
        extra_params={},
    )

    assert result is None
    client_factory.assert_not_called()
