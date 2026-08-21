from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from open_webui.models.users import UserModel
from open_webui.utils.access_control.model_knowledge import (
    MODEL_RAG_ONLY_KEY,
    resolve_model_knowledge_for_inference,
)
from open_webui.utils.jiaoxiaoai import apply_jiaoxiaoai_managed_policy, seed_jiaoxiaoai_model


def student() -> UserModel:
    return UserModel.model_construct(id='student-1', role='user')


@pytest.mark.asyncio
async def test_model_collection_without_direct_grant_is_rag_only(monkeypatch):
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=SimpleNamespace(id='kb-1', user_id='admin-1')),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Groups.get_groups_by_member_id',
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.AccessGrants.has_access',
        AsyncMock(return_value=False),
    )

    result = await resolve_model_knowledge_for_inference(
        [{'type': 'collection', 'id': 'kb-1', 'name': 'private source'}],
        student(),
    )

    assert result == [
        {
            'type': 'collection',
            'id': 'kb-1',
            'name': 'private source',
            MODEL_RAG_ONLY_KEY: True,
        }
    ]


@pytest.mark.asyncio
async def test_model_collection_with_direct_grant_remains_normal(monkeypatch):
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=SimpleNamespace(id='kb-1', user_id='admin-1')),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Groups.get_groups_by_member_id',
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.AccessGrants.has_access',
        AsyncMock(return_value=True),
    )

    result = await resolve_model_knowledge_for_inference(
        [{'type': 'collection', 'id': 'kb-1'}],
        student(),
    )

    assert result == [{'type': 'collection', 'id': 'kb-1'}]


@pytest.mark.asyncio
async def test_model_note_without_direct_grant_is_not_exposed(monkeypatch):
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Notes.get_note_by_id',
        AsyncMock(return_value=SimpleNamespace(id='note-1', user_id='admin-1')),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.Groups.get_groups_by_member_id',
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        'open_webui.utils.access_control.model_knowledge.AccessGrants.has_access',
        AsyncMock(return_value=False),
    )

    result = await resolve_model_knowledge_for_inference(
        [{'type': 'note', 'id': 'note-1'}],
        student(),
    )

    assert result == []


@pytest.mark.asyncio
async def test_declarative_model_bootstrap_is_public_read(monkeypatch):
    monkeypatch.setenv('JIAOXIAOAI_BASE_MODEL_ID', 'provider-model')
    monkeypatch.setenv('JIAOXIAOAI_MODEL_METADATA', '{"toolIds":["server:mcp:campus"]}')
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai.Models.get_model_by_id',
        AsyncMock(return_value=None),
    )
    insert = AsyncMock(return_value=SimpleNamespace(id='jiaoxiaoai'))
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Models.insert_new_model', insert)

    assert await seed_jiaoxiaoai_model() is True
    form = insert.await_args.args[0]
    assert form.name == '交小AI'
    assert form.base_model_id == 'provider-model'
    assert form.meta.model_dump()['toolIds'] == ['server:mcp:campus']
    assert form.access_grants == [{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}]
    assert insert.await_args.kwargs['user_id'] == 'system'


@pytest.mark.asyncio
async def test_declarative_model_bootstrap_does_not_overwrite_existing_model(monkeypatch):
    monkeypatch.setenv('JIAOXIAOAI_BASE_MODEL_ID', 'provider-model')
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai.Models.get_model_by_id',
        AsyncMock(return_value=SimpleNamespace(id='jiaoxiaoai')),
    )
    insert = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Models.insert_new_model', insert)

    assert await seed_jiaoxiaoai_model() is False
    insert.assert_not_awaited()


@pytest.mark.asyncio
async def test_managed_policy_restores_defaults_without_overwriting_admin_model_fields(monkeypatch):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    model = SimpleNamespace(
        id='jiaoxiaoai',
        base_model_id='admin-selected-model',
        name='管理员改过的名字',
        meta=SimpleNamespace(
            model_dump=lambda **_: {
                'description': 'kept',
                'capabilities': {'vision': True},
                'defaultFeatureIds': ['image_generation'],
            }
        ),
        params=SimpleNamespace(model_dump=lambda **_: {'temperature': 0.2}),
        access_grants=[],
        is_active=True,
    )
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Config.upsert', AsyncMock())
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Config.get', AsyncMock(return_value=''))
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Models.get_model_by_id', AsyncMock(return_value=model))
    update = AsyncMock(return_value=model)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai.Models.update_model_by_id', update)

    assert await apply_jiaoxiaoai_managed_policy() is True
    form = update.await_args.args[1]
    assert form.base_model_id == 'admin-selected-model'
    assert form.name == '管理员改过的名字'
    assert form.params.model_dump()['temperature'] == 0.2
    assert form.meta.model_dump()['description'] == 'kept'
    assert form.meta.model_dump()['capabilities']['vision'] is True
    assert form.meta.model_dump()['capabilities']['web_search'] is True
    assert 'web_search' in form.meta.model_dump()['defaultFeatureIds']


def test_managed_student_cannot_call_provider_routes_directly(monkeypatch):
    from open_webui.utils.jiaoxiaoai import provider_route_allowed

    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    assert provider_route_allowed('user') is False
    assert provider_route_allowed('admin') is True


def test_provider_routes_keep_upstream_behavior_outside_managed_mode(monkeypatch):
    from open_webui.utils.jiaoxiaoai import provider_route_allowed

    monkeypatch.delenv('JIAOXIAOAI_MANAGED_MODE', raising=False)
    assert provider_route_allowed('user') is True


@pytest.mark.parametrize(
    ('owner_id', 'user_role', 'expected'),
    [
        ('system', 'user', True),
        ('admin-1', 'user', False),
        ('admin-1', 'admin', True),
    ],
)
@pytest.mark.asyncio
async def test_only_system_managed_models_bridge_unregistered_provider_models(
    monkeypatch, owner_id, user_role, expected
):
    from open_webui.utils.access_control import has_base_model_access

    monkeypatch.setattr(
        'open_webui.models.models.Models.get_model_by_id',
        AsyncMock(return_value=None),
    )
    model = SimpleNamespace(id='preset', user_id=owner_id, base_model_id='provider-model')
    assert await has_base_model_access('student-1', model, user_role=user_role) is expected
