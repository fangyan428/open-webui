import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from open_webui.utils.jiaoxiaoai_plugins import (
    _bind_managed_local_tools,
    _check_id_collisions,
    _prepare_function,
    discover_plugin_bundles,
    sync_managed_plugins,
)


def _plugin(plugin_id: str, kind: str = 'function') -> dict:
    return {
        'id': plugin_id,
        'name': plugin_id.title(),
        'type': 'action' if kind == 'function' else None,
        'content': """class Action:
    async def action(self, body):
        return body
""",
        'meta': {'description': 'managed test plugin'},
        'is_active': True,
    }


def test_discover_plugin_bundles_accepts_native_exports(monkeypatch, tmp_path):
    functions = tmp_path / 'functions'
    tools = tmp_path / 'tools'
    functions.mkdir()
    tools.mkdir()
    (functions / 'reviewed.json').write_text(json.dumps([_plugin('first_action')]), encoding='utf-8')
    (tools / 'reviewed.json').write_text(
        json.dumps({'plugins': [_plugin('campus_tool', 'tool')]}),
        encoding='utf-8',
    )

    records = discover_plugin_bundles(tmp_path)

    assert {(record['_kind'], record['id']) for record in records} == {
        ('function', 'first_action'),
        ('tool', 'campus_tool'),
    }
    assert all(len(record['_sha256']) == 64 for record in records)


def test_discover_plugin_bundles_rejects_duplicate_ids(tmp_path):
    functions = tmp_path / 'functions'
    tools = tmp_path / 'tools'
    functions.mkdir()
    tools.mkdir()
    (functions / 'one.json').write_text(json.dumps([_plugin('duplicate')]), encoding='utf-8')
    (functions / 'two.json').write_text(json.dumps([_plugin('duplicate')]), encoding='utf-8')

    with pytest.raises(ValueError, match='duplicate managed function id'):
        discover_plugin_bundles(tmp_path)


def test_prepare_function_loads_and_marks_managed_plugin(tmp_path):
    functions = tmp_path / 'functions'
    tools = tmp_path / 'tools'
    functions.mkdir()
    tools.mkdir()
    (functions / 'reviewed.json').write_text(json.dumps([_plugin('first_action')]), encoding='utf-8')

    prepared = asyncio.run(_prepare_function(discover_plugin_bundles(tmp_path)[0]))

    assert prepared['type'] == 'action'
    assert prepared['form'].meta.manifest['jiaoxiaoai_managed'] is True
    assert prepared['form'].meta.manifest['managed_source'] == 'reviewed.json'


def test_invalid_scan_preserves_last_good_plugins(monkeypatch, tmp_path):
    functions = tmp_path / 'functions'
    tools = tmp_path / 'tools'
    functions.mkdir()
    tools.mkdir()
    (functions / 'broken.json').write_text('{not-json', encoding='utf-8')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_PLUGINS_DIR', str(tmp_path))
    load_existing = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_plugins._load_existing', load_existing)

    result = asyncio.run(sync_managed_plugins())

    assert result['errors']
    assert result['loaded'] == 0
    load_existing.assert_not_awaited()


def test_non_managed_plugin_id_collision_is_rejected():
    records = [{'id': 'campus_tool', '_kind': 'tool'}]
    existing_tool = SimpleNamespace(id='campus_tool', meta=SimpleNamespace(manifest={}))

    with pytest.raises(ValueError, match='non-managed plugin'):
        _check_id_collisions(records, [], [existing_tool])


def test_managed_tool_binding_preserves_mcp_and_native_tools(monkeypatch):
    model = SimpleNamespace(
        id='jiaoxiaoai',
        base_model_id='provider-model',
        name='交小AI',
        meta=SimpleNamespace(
            model_dump=lambda **_: {
                'toolIds': ['server:mcp:campus', 'native_tool', 'old_managed_tool'],
                'jiaoxiaoai_managed_tool_ids': ['server:mcp:campus'],
                'jiaoxiaoai_managed_local_tool_ids': ['old_managed_tool'],
            }
        ),
        params=SimpleNamespace(model_dump=lambda **_: {}),
        access_grants=[],
        is_active=True,
    )
    monkeypatch.setenv('JIAOXIAOAI_MODEL_ID', 'jiaoxiaoai')
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_plugins.Models.get_model_by_id',
        AsyncMock(return_value=model),
    )
    update = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_plugins.Models.update_model_by_id', update)

    asyncio.run(_bind_managed_local_tools(['new_managed_tool']))

    form = update.await_args.args[1]
    tool_ids = form.meta.model_dump()['toolIds']
    assert tool_ids == ['server:mcp:campus', 'native_tool', 'new_managed_tool']
    assert form.meta.model_dump()['jiaoxiaoai_managed_local_tool_ids'] == ['new_managed_tool']
