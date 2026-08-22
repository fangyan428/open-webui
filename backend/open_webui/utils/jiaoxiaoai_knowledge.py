from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
from pathlib import Path

import yaml
from fastapi import UploadFile
from open_webui.models.files import Files
from open_webui.models.knowledge import KnowledgeForm, Knowledges
from open_webui.models.models import ModelForm, Models
from open_webui.models.users import UserModel
from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT
from open_webui.routers.files import upload_file_handler
from open_webui.storage.provider import Storage
from open_webui.utils.jiaoxiaoai import managed_mode_enabled, managed_model_id
from starlette.datastructures import Headers
from starlette.requests import Request

log = logging.getLogger(__name__)
MANAGED_MARKER = 'jiaoxiaoai_managed'


def managed_knowledge_root() -> Path:
    return Path(os.getenv('JIAOXIAOAI_MANAGED_KNOWLEDGE_DIR', '/app/managed/knowledge'))


def stable_knowledge_id(directory_name: str) -> str:
    return f'jiaoxiaoai-kb-{hashlib.sha256(directory_name.encode()).hexdigest()[:20]}'


def load_managed_manifest(directory: Path) -> dict:
    value = yaml.safe_load((directory / 'manifest.yaml').read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('manifest.yaml must contain an object')
    if not str(value.get('name', '')).strip():
        raise ValueError('manifest.yaml requires name')
    return value


def discover_managed_sources(files_root: Path) -> list[tuple[Path, str, str]]:
    """Return unique source files, ignoring OS metadata and hidden files."""
    sources = []
    seen_hashes: dict[str, str] = {}
    for source in sorted(path for path in files_root.rglob('*') if path.is_file()):
        relative = source.relative_to(files_root).as_posix()
        if any(
            part.startswith('.')
            or part == '__MACOSX'
            or part.endswith('.DS_Store')
            or part in {'Thumbs.db', 'desktop.ini'}
            for part in Path(relative).parts
        ):
            continue
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        raw_hash = digest.hexdigest()
        if raw_hash in seen_hashes:
            log.warning('Ignoring duplicate managed source %s (same content as %s)', relative, seen_hashes[raw_hash])
            continue
        seen_hashes[raw_hash] = relative
        sources.append((source, relative, raw_hash))
    return sources


def _internal_request(app) -> Request:
    return Request(
        {
            'type': 'http',
            'asgi.version': '3.0',
            'asgi.spec_version': '2.0',
            'method': 'POST',
            'path': '/internal/jiaoxiaoai/knowledge-sync',
            'query_string': b'',
            'headers': Headers({}).raw,
            'client': ('127.0.0.1', 0),
            'server': ('127.0.0.1', 0),
            'scheme': 'http',
            'app': app,
        }
    )


async def _delete_file(file) -> None:
    for knowledge in await Knowledges.get_knowledges_by_file_id(file.id):
        await Knowledges.remove_file_from_knowledge_by_id(knowledge.id, file.id)
        try:
            await ASYNC_VECTOR_DB_CLIENT.delete(collection_name=knowledge.id, filter={'file_id': file.id})
        except Exception:
            log.exception('Could not remove managed vectors for %s', file.id)
    await Files.delete_file_by_id(file.id)
    try:
        await asyncio.to_thread(Storage.delete_file, file.path)
        if await ASYNC_VECTOR_DB_CLIENT.has_collection(collection_name=f'file-{file.id}'):
            await ASYNC_VECTOR_DB_CLIENT.delete_collection(collection_name=f'file-{file.id}')
    except Exception:
        log.exception('Could not remove managed stored file %s', file.id)


async def _replace_model_attachments(attachments: list[dict]) -> None:
    model = await Models.get_model_by_id(managed_model_id())
    if not model:
        return
    meta = model.meta.model_dump(exclude_none=True)
    existing = list(meta.get('knowledge') or [])
    replacement_keys = {(item.get('type'), item.get('id')) for item in attachments}
    kept = [
        item
        for item in existing
        if not (
            isinstance(item, dict)
            and (item.get('type'), item.get('id')) in replacement_keys
        )
    ]
    meta['knowledge'] = kept + attachments
    await Models.update_model_by_id(
        model.id,
        ModelForm(
            id=model.id,
            base_model_id=model.base_model_id,
            name=model.name,
            meta=meta,
            params=model.params.model_dump(exclude_none=True),
            access_grants=[grant.model_dump() for grant in model.access_grants],
            is_active=model.is_active,
        ),
    )


async def sync_managed_knowledge(app) -> dict:  # noqa: C901 - linear sync state machine
    """Synchronize declarative files without touching Admin-uploaded overlay files."""
    empty = {'knowledge_bases': 0, 'added': 0, 'updated': 0, 'deleted': 0, 'errors': []}
    if not managed_mode_enabled():
        return {'enabled': False, **empty}

    root = managed_knowledge_root()
    if not root.is_dir():
        message = f'Managed Knowledge root is missing: {root}'
        log.warning('%s; no content was removed', message)
        return {'enabled': True, **empty, 'errors': [message]}

    result = {'enabled': True, **empty}
    request = _internal_request(app)
    admin = UserModel.model_construct(id='system', role='admin', email='managed@localhost', name='交小AI托管导入')
    attachments = []

    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            manifest = load_managed_manifest(directory)
            files_root = directory / 'files'
            if not files_root.is_dir():
                raise ValueError('files/ directory is missing')
            sources = discover_managed_sources(files_root)
            knowledge_id = str(manifest.get('id') or stable_knowledge_id(directory.name))
            knowledge = await Knowledges.get_knowledge_by_id(knowledge_id)
            if knowledge and not (knowledge.meta or {}).get(MANAGED_MARKER):
                raise ValueError(f'Knowledge ID {knowledge_id} already belongs to a non-managed Knowledge base')
            if not knowledge:
                knowledge = await Knowledges.insert_managed_knowledge(
                    knowledge_id,
                    'system',
                    KnowledgeForm(
                        name=str(manifest['name']).strip(),
                        description=str(manifest.get('description', '')).strip(),
                        access_grants=[],
                    ),
                    meta={MANAGED_MARKER: True, 'managed_source': directory.name},
                )
            if not knowledge:
                raise RuntimeError(f'could not create Knowledge base {knowledge_id}')
            desired_name = str(manifest['name']).strip()
            desired_description = str(manifest.get('description', '')).strip()
            if knowledge.name != desired_name or knowledge.description != desired_description:
                knowledge = await Knowledges.update_knowledge_by_id(
                    knowledge_id,
                    KnowledgeForm(
                        name=desired_name,
                        description=desired_description,
                        access_grants=[],
                    ),
                )
                if not knowledge:
                    raise RuntimeError(f'could not update Knowledge base {knowledge_id}')

            existing = {}
            for file in await Files.get_files():
                data = (file.meta or {}).get('data') or {}
                if data.get(MANAGED_MARKER) and data.get('managed_knowledge_id') == knowledge_id:
                    existing[data.get('managed_relative_path')] = file

            desired = set()
            for source, relative, raw_hash in sources:
                desired.add(relative)
                current = existing.get(relative)
                current_data = ((current.meta or {}).get('data') or {}) if current else {}
                if current and current_data.get('managed_raw_hash') == raw_hash:
                    continue
                uploaded_file = None
                try:
                    content_type = mimetypes.guess_type(source.name)[0] or 'application/octet-stream'
                    with source.open('rb') as stream:
                        uploaded = await upload_file_handler(
                            request,
                            file=UploadFile(
                                file=stream,
                                filename=source.name,
                                headers=Headers({'content-type': content_type}),
                            ),
                            metadata={
                                'knowledge_id': knowledge_id,
                                MANAGED_MARKER: True,
                                'managed_knowledge_id': knowledge_id,
                                'managed_relative_path': relative,
                                'managed_raw_hash': raw_hash,
                            },
                            process=True,
                            process_in_background=False,
                            user=admin,
                        )
                    uploaded_id = uploaded.get('id') if isinstance(uploaded, dict) else uploaded.id
                    uploaded_file = await Files.get_file_by_id(uploaded_id)
                    if not uploaded_file or (uploaded_file.data or {}).get('status') == 'failed':
                        raise RuntimeError('processing failed')
                    if current:
                        await _delete_file(current)
                        result['updated'] += 1
                    else:
                        result['added'] += 1
                except Exception as exc:
                    if uploaded_file:
                        await _delete_file(uploaded_file)
                    log.exception('Managed Knowledge source failed: %s/%s', directory.name, relative)
                    result['errors'].append(f'{directory.name}/{relative}: {exc}')
                    continue

            # This destructive diff is reached only after a valid manifest and full scan.
            for relative, file in existing.items():
                if relative not in desired:
                    await _delete_file(file)
                    result['deleted'] += 1

            attachments.append(
                {
                    'type': 'collection',
                    'id': knowledge_id,
                    'name': knowledge.name,
                    MANAGED_MARKER: True,
                }
            )
            result['knowledge_bases'] += 1
        except Exception as exc:
            log.exception('Managed Knowledge sync failed for %s', directory)
            result['errors'].append(f'{directory.name}: {exc}')

    await _replace_model_attachments(attachments)
    return result
