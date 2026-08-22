import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_bocha_server():
    path = REPO_ROOT / 'deploy' / 'bocha-mcp' / 'server.py'
    spec = importlib.util.spec_from_file_location('jiaoxiaoai_bocha_mcp_server', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bocha_mcp_is_managed_enabled_and_public_read():
    path = REPO_ROOT / 'deploy' / 'managed' / 'mcp' / 'bocha.yaml'
    connection = yaml.safe_load(path.read_text(encoding='utf-8'))

    assert connection['url'] == 'http://bocha-mcp:8000/mcp'
    assert connection['type'] == 'mcp'
    assert connection['auth_type'] == 'none'
    assert connection['config']['enable'] is True
    assert connection['config']['function_name_filter_list'] == 'bocha_web_search'
    assert connection['config']['access_grants'] == [
        {'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}
    ]
    assert connection['info']['id'] == 'bocha'


def test_bocha_mcp_sidecar_is_wired_into_both_compose_deployments():
    for filename in ('docker-compose.jiaoxiaoai.yaml', 'docker-compose.jiaoxiaoai.server.yaml'):
        compose = yaml.safe_load((REPO_ROOT / filename).read_text(encoding='utf-8'))
        services = compose['services']

        assert services['open-webui']['depends_on']['bocha-mcp']['condition'] == 'service_healthy'
        assert services['bocha-mcp']['env_file'] == ['./deploy/jiaoxiaoai.env']
        assert services['bocha-mcp']['healthcheck']


def test_bocha_secret_is_declared_but_not_committed():
    env_example = (REPO_ROOT / 'deploy' / 'jiaoxiaoai.env.example').read_text(encoding='utf-8')

    assert 'BOCHA_API_KEY=replace-with-bocha-api-key' in env_example
    assert '${BOCHA_API_KEY}' not in (REPO_ROOT / 'deploy' / 'managed' / 'mcp' / 'bocha.yaml').read_text(
        encoding='utf-8'
    )


def test_bocha_result_formatter_keeps_source_url_and_summary():
    server = _load_bocha_server()

    result = server._format_results(
        {
            'data': {
                'webPages': {
                    'value': [
                        {
                            'name': '校园通知',
                            'url': 'https://example.edu/notice',
                            'summary': '通知摘要',
                        }
                    ]
                }
            }
        }
    )

    assert 'Title: 校园通知' in result
    assert 'URL: https://example.edu/notice' in result
    assert 'Summary: 通知摘要' in result


@pytest.mark.asyncio
async def test_bocha_tool_fails_before_network_when_key_is_missing(monkeypatch):
    server = _load_bocha_server()
    monkeypatch.delenv('BOCHA_API_KEY', raising=False)

    with pytest.raises(RuntimeError, match='not configured'):
        await server.search_bocha_web('交大校历')
