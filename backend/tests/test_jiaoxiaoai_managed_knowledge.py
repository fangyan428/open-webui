import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from open_webui.utils.jiaoxiaoai_knowledge import (
    _replace_model_attachments,
    discover_managed_sources,
    stable_knowledge_id,
    sync_managed_knowledge,
)


def _knowledge():
    return SimpleNamespace(id='kb-campus', name='校内资料', description='', meta={'jiaoxiaoai_managed': True})


@pytest.mark.asyncio
async def test_missing_root_fails_safe_without_deleting(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', str(tmp_path / 'missing'))
    delete = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._delete_file', delete)

    result = await sync_managed_knowledge(SimpleNamespace())

    assert result['errors']
    assert result['deleted'] == 0
    delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_unchanged_managed_file_is_idempotent_and_overlay_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', str(tmp_path))
    directory = tmp_path / 'campus'
    files = directory / 'files'
    files.mkdir(parents=True)
    (directory / 'manifest.yaml').write_text('id: kb-campus\nname: 校内资料\n', encoding='utf-8')
    content = b'hello campus'
    (files / 'guide.txt').write_bytes(content)

    existing = SimpleNamespace(
        id='managed-file',
        meta={
            'data': {
                'jiaoxiaoai_managed': True,
                'managed_knowledge_id': 'kb-campus',
                'managed_relative_path': 'guide.txt',
                'managed_raw_hash': hashlib.sha256(content).hexdigest(),
            }
        },
    )
    overlay = SimpleNamespace(id='admin-overlay', meta={'data': {'knowledge_id': 'kb-campus'}})
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=_knowledge()),
    )
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Files.get_files', AsyncMock(return_value=[existing, overlay])
    )
    upload = AsyncMock()
    delete = AsyncMock()
    attach = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.upload_file_handler', upload)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._delete_file', delete)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._replace_model_attachments', attach)

    result = await sync_managed_knowledge(SimpleNamespace())

    assert result == {
        'enabled': True,
        'knowledge_bases': 1,
        'added': 0,
        'updated': 0,
        'deleted': 0,
        'errors': [],
    }
    upload.assert_not_awaited()
    delete.assert_not_awaited()
    attach.assert_awaited_once()


def test_stable_knowledge_id_is_repeatable_and_directory_specific():
    assert stable_knowledge_id('campus') == stable_knowledge_id('campus')
    assert stable_knowledge_id('campus') != stable_knowledge_id('library')


@pytest.mark.asyncio
async def test_model_attachment_sync_replaces_duplicate_without_removing_last_good_entries(monkeypatch):
    model = SimpleNamespace(
        id='jiaoxiaoai',
        base_model_id='provider-model',
        name='交小AI',
        meta=SimpleNamespace(
            model_dump=lambda **_: {
                'knowledge': [
                    {'type': 'collection', 'id': 'kb-campus', 'name': '旧绑定'},
                    {
                        'type': 'collection',
                        'id': 'kb-removed',
                        'name': '已移除的托管库',
                        'jiaoxiaoai_managed': True,
                    },
                    {'type': 'collection', 'id': 'admin-kb', 'name': '管理员资料'},
                ]
            }
        ),
        params=SimpleNamespace(model_dump=lambda **_: {}),
        access_grants=[],
        is_active=True,
    )
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Models.get_model_by_id',
        AsyncMock(return_value=model),
    )
    update = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.Models.update_model_by_id', update)
    replacement = {
        'type': 'collection',
        'id': 'kb-campus',
        'name': '校内资料',
        'jiaoxiaoai_managed': True,
    }

    await _replace_model_attachments([replacement])

    form = update.await_args.args[1]
    assert form.meta.knowledge == [
        {
            'type': 'collection',
            'id': 'kb-removed',
            'name': '已移除的托管库',
            'jiaoxiaoai_managed': True,
        },
        {'type': 'collection', 'id': 'admin-kb', 'name': '管理员资料'},
        replacement,
    ]


def test_source_discovery_supports_subdirectories_and_ignores_os_metadata_and_duplicates(tmp_path):
    files = tmp_path / 'files'
    nested = files / '学生手册'
    nested.mkdir(parents=True)
    (nested / 'guide.pdf').write_bytes(b'guide')
    (nested / 'guide_1.pdf').write_bytes(b'guide')
    (nested / '.DS_Store').write_bytes(b'metadata')
    (nested / '_1.DS_Store').write_bytes(b'metadata')
    (nested / '._guide.pdf').write_bytes(b'appledouble')
    macos = files / '__MACOSX'
    macos.mkdir()
    (macos / 'guide.pdf').write_bytes(b'metadata')

    sources = discover_managed_sources(files)

    assert [(relative, raw_hash) for _, relative, raw_hash in sources] == [
        ('学生手册/guide.pdf', hashlib.sha256(b'guide').hexdigest())
    ]


def test_managed_knowledge_cannot_be_reset_or_deleted_through_native_management_routes():
    from open_webui.routers.knowledge import managed_knowledge_error

    with pytest.raises(HTTPException) as exc:
        managed_knowledge_error(SimpleNamespace(meta={'jiaoxiaoai_managed': True}))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_manifest_cannot_take_over_native_knowledge(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', str(tmp_path))
    directory = tmp_path / 'campus'
    (directory / 'files').mkdir(parents=True)
    (directory / 'manifest.yaml').write_text('id: native-kb\nname: Campus\n', encoding='utf-8')
    native = SimpleNamespace(id='native-kb', name='Native', description='', meta={})
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=native),
    )
    upload = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.upload_file_handler', upload)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._replace_model_attachments', AsyncMock())

    result = await sync_managed_knowledge(SimpleNamespace())

    assert 'already belongs to a non-managed' in result['errors'][0]
    upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_file_uses_native_processing_with_managed_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', str(tmp_path))
    directory = tmp_path / 'campus'
    files = directory / 'files'
    files.mkdir(parents=True)
    (directory / 'manifest.yaml').write_text('id: kb-campus\nname: 校内资料\n', encoding='utf-8')
    (files / 'guide.txt').write_text('hello campus', encoding='utf-8')

    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=_knowledge()),
    )
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.Files.get_files', AsyncMock(return_value=[]))
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Files.get_file_by_id',
        AsyncMock(return_value=SimpleNamespace(id='new-file', data={'status': 'completed'})),
    )
    upload = AsyncMock(return_value={'id': 'new-file'})
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.upload_file_handler', upload)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._replace_model_attachments', AsyncMock())

    result = await sync_managed_knowledge(SimpleNamespace())

    assert result['added'] == 1
    kwargs = upload.await_args.kwargs
    assert kwargs['process'] is True
    assert kwargs['process_in_background'] is False
    assert kwargs['metadata']['knowledge_id'] == 'kb-campus'
    assert kwargs['metadata']['managed_relative_path'] == 'guide.txt'
    assert kwargs['metadata']['jiaoxiaoai_managed'] is True


@pytest.mark.asyncio
async def test_failed_source_does_not_block_remaining_managed_files(monkeypatch, tmp_path):
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_MODE', 'true')
    monkeypatch.setenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', str(tmp_path))
    directory = tmp_path / 'campus'
    files = directory / 'files'
    files.mkdir(parents=True)
    (directory / 'manifest.yaml').write_text('id: kb-campus\nname: 校内资料\n', encoding='utf-8')
    (files / 'bad.xlsx').write_bytes(b'bad spreadsheet')
    (files / 'guide.txt').write_text('hello campus', encoding='utf-8')

    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Knowledges.get_knowledge_by_id',
        AsyncMock(return_value=_knowledge()),
    )
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.Files.get_files', AsyncMock(return_value=[]))
    monkeypatch.setattr(
        'open_webui.utils.jiaoxiaoai_knowledge.Files.get_file_by_id',
        AsyncMock(
            side_effect=[
                SimpleNamespace(id='bad-file', data={'status': 'failed'}),
                SimpleNamespace(id='good-file', data={'status': 'completed'}),
            ]
        ),
    )
    upload = AsyncMock(side_effect=[{'id': 'bad-file'}, {'id': 'good-file'}])
    delete = AsyncMock()
    attach = AsyncMock()
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge.upload_file_handler', upload)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._delete_file', delete)
    monkeypatch.setattr('open_webui.utils.jiaoxiaoai_knowledge._replace_model_attachments', attach)

    result = await sync_managed_knowledge(SimpleNamespace())

    assert upload.await_count == 2
    assert result['added'] == 1
    assert result['knowledge_bases'] == 1
    assert result['errors'] == ['campus/bad.xlsx: processing failed']
    delete.assert_awaited_once()
    attach.assert_awaited_once()
