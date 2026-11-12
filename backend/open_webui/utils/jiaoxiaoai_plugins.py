from __future__ import annotations

import hashlib
import json
import logging
import os
from copy import deepcopy
from pathlib import Path

from open_webui.models.functions import FunctionForm, FunctionMeta, Functions
from open_webui.models.models import ModelForm, Models
from open_webui.models.tools import ToolForm, ToolMeta, Tools
from open_webui.models.users import Users
from open_webui.utils.jiaoxiaoai import managed_mode_enabled, managed_model_id
from open_webui.utils.plugin import load_function_module_by_id, load_tool_module_by_id, replace_imports
from open_webui.utils.tools import get_tool_specs

log = logging.getLogger(__name__)

MANAGED_MARKER = 'jiaoxiaoai_managed'
PLUGIN_DIRECTORIES = (('functions', 'function'), ('tools', 'tool'))


def managed_plugins_root() -> Path:
    return Path(os.getenv('JIAOXIAOAI_MANAGED_PLUGINS_DIR', '/app/managed/plugins'))


def _read_payload(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, dict) and isinstance(payload.get('plugins'), list):
        payload = payload['plugins']
    elif isinstance(payload, dict):
        payload = [payload]

    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError('plugin bundle must be a JSON object, array, or {"plugins": [...]}')
    return payload


def _normalize_record(kind: str, path: Path, record: dict) -> dict:
    normalized = deepcopy(record)
    plugin_id = normalized.get('id')
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise ValueError('plugin id is required')

    plugin_id = plugin_id.strip().lower()
    if not plugin_id.isidentifier():
        raise ValueError(f'invalid plugin id: {plugin_id}')
    if not isinstance(normalized.get('name'), str) or not normalized['name'].strip():
        raise ValueError(f'plugin {plugin_id} requires a name')
    if not isinstance(normalized.get('content'), str) or not normalized['content'].strip():
        raise ValueError(f'plugin {plugin_id} requires Python content')

    normalized['id'] = plugin_id
    normalized['name'] = normalized['name'].strip()
    normalized['_kind'] = kind
    normalized['_source'] = path.name
    normalized['_sha256'] = hashlib.sha256(normalized['content'].encode('utf-8')).hexdigest()
    return normalized


def discover_plugin_bundles(root: Path | None = None) -> list[dict]:
    root = root or managed_plugins_root()
    if not root.is_dir():
        raise ValueError(f'managed plugin root is missing: {root}')

    records = []
    seen = set()
    for directory_name, kind in PLUGIN_DIRECTORIES:
        directory = root / directory_name
        if not directory.is_dir():
            raise ValueError(f'managed plugin directory is missing: {directory}')

        for path in sorted(directory.rglob('*.json')):
            for record in _read_payload(path):
                normalized = _normalize_record(kind, path, record)
                key = (kind, normalized['id'])
                if key in seen:
                    raise ValueError(f'duplicate managed {kind} id: {normalized["id"]}')
                seen.add(key)
                records.append(normalized)

    return records


def _meta_dict(meta) -> dict:
    if meta is None:
        return {}
    if hasattr(meta, 'model_dump'):
        return meta.model_dump(exclude_none=True)
    return dict(meta) if isinstance(meta, dict) else {}


def _is_managed(meta) -> bool:
    manifest = _meta_dict(meta).get('manifest') or {}
    if not isinstance(manifest, dict):
        return False
    managed_id = manifest.get('managed_id')
    return manifest.get(MANAGED_MARKER) is True or (
        isinstance(managed_id, str) and managed_id.startswith('jiaoxiaoai_')
    )


def _managed_meta(record: dict, frontmatter: dict | None, extra: dict | None = None) -> dict:
    meta = _meta_dict(record.get('meta'))
    manifest = meta.get('manifest') if isinstance(meta.get('manifest'), dict) else {}
    meta['manifest'] = {
        **manifest,
        **(frontmatter or {}),
        MANAGED_MARKER: True,
        'managed_kind': record['_kind'],
        'managed_source': record['_source'],
        'managed_sha256': record['_sha256'],
    }
    if extra:
        meta.update(extra)
    return meta


async def _managed_owner_id() -> str:
    result = await Users.get_users(filter={'roles': ['admin']}, limit=1)
    admins = result.get('users') if isinstance(result, dict) else None
    return admins[0].id if admins else 'system'


async def _prepare_function(record: dict) -> dict:
    content = replace_imports(record['content'])
    _, function_type, frontmatter = await load_function_module_by_id(record['id'], content=content)
    valves = record.get('valves')
    if valves is not None and not isinstance(valves, dict):
        raise ValueError(f'function {record["id"]} valves must be an object')

    declared_type = record.get('type')
    if declared_type and declared_type != function_type:
        raise ValueError(
            f'function {record["id"]} declares type {declared_type!r}, but its code defines {function_type!r}'
        )

    meta = FunctionMeta(**_managed_meta(record, frontmatter))
    return {
        'record': record,
        'form': FunctionForm(
            id=record['id'],
            name=record['name'],
            content=content,
            meta=meta,
        ),
        'type': function_type,
        'is_active': bool(record.get('is_active', record.get('enabled', False))),
        'is_global': bool(record.get('is_global', False)),
        'valves': valves,
    }


async def _prepare_tool(record: dict) -> dict:
    content = replace_imports(record['content'])
    tool_module, frontmatter = await load_tool_module_by_id(record['id'], content=content)
    meta = ToolMeta(
        **_managed_meta(
            record,
            frontmatter,
            {
                'has_user_valves': hasattr(tool_module, 'UserValves'),
            },
        )
    )
    access_grants = record.get('access_grants')
    if access_grants is not None and not isinstance(access_grants, list):
        raise ValueError(f'tool {record["id"]} access_grants must be a list')

    return {
        'record': record,
        'form': ToolForm(
            id=record['id'],
            name=record['name'],
            content=content,
            meta=meta,
            access_grants=access_grants or [],
        ),
        'specs': get_tool_specs(tool_module),
        'enabled': bool(record.get('enabled', True)),
    }


async def _load_existing() -> tuple[list, list]:
    return (
        await Functions.get_functions(include_valves=True),
        await Tools.get_tools(),
    )


def _check_id_collisions(records: list[dict], existing_functions: list, existing_tools: list) -> None:
    existing = {
        'function': {function.id: function for function in existing_functions},
        'tool': {tool.id: tool for tool in existing_tools},
    }
    for record in records:
        current = existing[record['_kind']].get(record['id'])
        if current is not None and not _is_managed(current.meta):
            raise ValueError(
                f'{record["_kind"]} id {record["id"]} already belongs to a non-managed plugin; '
                'rename or remove the local plugin before syncing'
            )


async def _prepare_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    functions = []
    tools = []
    for record in records:
        if record['_kind'] == 'function':
            functions.append(await _prepare_function(record))
        else:
            tools.append(await _prepare_tool(record))
    return functions, tools


async def _upsert_function(owner_id: str, prepared: dict) -> None:
    function_id = prepared['form'].id
    existing = await Functions.get_function_by_id(function_id)
    if existing is None:
        created = await Functions.insert_new_function(owner_id, prepared['type'], prepared['form'])
        if created is None:
            raise RuntimeError(f'failed to import function {function_id}')

    updated = await Functions.update_function_by_id(
        function_id,
        {
            'name': prepared['form'].name,
            'type': prepared['type'],
            'content': prepared['form'].content,
            'meta': prepared['form'].meta.model_dump(exclude_none=True),
            'is_active': prepared['is_active'],
            'is_global': prepared['is_global'],
        },
    )
    if updated is None:
        raise RuntimeError(f'failed to update function {function_id}')

    if prepared['valves'] is not None:
        valves = await Functions.update_function_valves_by_id(function_id, prepared['valves'])
        if valves is None:
            raise RuntimeError(f'failed to update function valves for {function_id}')


async def _upsert_tool(owner_id: str, prepared: dict) -> None:
    tool_id = prepared['form'].id
    existing = await Tools.get_tool_by_id(tool_id)
    if existing is None:
        created = await Tools.insert_new_tool(owner_id, prepared['form'], prepared['specs'])
        if created is None:
            raise RuntimeError(f'failed to import tool {tool_id}')
        return

    updated = await Tools.update_tool_by_id(
        tool_id,
        {
            'name': prepared['form'].name,
            'content': prepared['form'].content,
            'meta': prepared['form'].meta.model_dump(exclude_none=True),
            'specs': prepared['specs'],
            'access_grants': prepared['form'].access_grants,
        },
    )
    if updated is None:
        raise RuntimeError(f'failed to update tool {tool_id}')


async def _delete_stale(
    functions: list[dict],
    tools: list[dict],
    existing_functions: list,
    existing_tools: list,
) -> int:
    desired_functions = {item['form'].id for item in functions}
    desired_tools = {item['form'].id for item in tools}
    removed = 0

    for function in existing_functions:
        if _is_managed(function.meta) and function.id not in desired_functions:
            if not await Functions.delete_function_by_id(function.id):
                raise RuntimeError(f'failed to remove stale function {function.id}')
            removed += 1

    for tool in existing_tools:
        if _is_managed(tool.meta) and tool.id not in desired_tools:
            if not await Tools.delete_tool_by_id(tool.id):
                raise RuntimeError(f'failed to remove stale tool {tool.id}')
            removed += 1

    return removed


async def _bind_managed_local_tools(tool_ids: list[str]) -> None:
    model = await Models.get_model_by_id(managed_model_id())
    if model is None:
        return

    meta = model.meta.model_dump(exclude_none=True)
    previous = set(meta.get('jiaoxiaoai_managed_local_tool_ids') or [])
    native = [tool_id for tool_id in (meta.get('toolIds') or []) if tool_id not in previous]
    meta['toolIds'] = list(dict.fromkeys(native + tool_ids))
    meta['jiaoxiaoai_managed_local_tool_ids'] = tool_ids

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


async def sync_managed_plugins() -> dict:
    if not managed_mode_enabled():
        return {'enabled': False, 'loaded': 0, 'removed': 0, 'errors': []}

    try:
        records = discover_plugin_bundles()
        existing_functions, existing_tools = await _load_existing()
        _check_id_collisions(records, existing_functions, existing_tools)
        functions, tools = await _prepare_records(records)
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        log.exception('Managed plugin scan is invalid; existing plugins were preserved')
        return {'enabled': True, 'loaded': 0, 'removed': 0, 'errors': [message]}

    try:
        owner_id = await _managed_owner_id()
        for prepared in functions:
            await _upsert_function(owner_id, prepared)
        for prepared in tools:
            await _upsert_tool(owner_id, prepared)

        removed = await _delete_stale(functions, tools, existing_functions, existing_tools)
        await _bind_managed_local_tools(
            [prepared['form'].id for prepared in tools if prepared['enabled']]
        )
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        log.exception('Managed plugin apply failed')
        return {'enabled': True, 'loaded': 0, 'removed': 0, 'errors': [message]}

    return {
        'enabled': True,
        'loaded': len(functions) + len(tools),
        'functions': len(functions),
        'tools': len(tools),
        'removed': removed,
        'errors': [],
    }
