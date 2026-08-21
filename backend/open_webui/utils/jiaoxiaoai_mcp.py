from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml
from open_webui.config import Config
from open_webui.models.models import ModelForm, Models
from open_webui.utils.jiaoxiaoai import managed_mode_enabled, managed_model_id

log = logging.getLogger(__name__)
MANAGED_MARKER = 'jiaoxiaoai_managed'
ENV_REFERENCE = re.compile(r'\$\{([A-Z_][A-Z0-9_]*)\}')


def managed_mcp_root() -> Path:
    return Path(os.getenv('JIAOXIAOAI_MANAGED_MCP_DIR', '/app/managed/mcp'))


def _resolve_env(value):
    if isinstance(value, str):

        def replace(match):
            name = match.group(1)
            resolved = os.getenv(name)
            if resolved is None:
                raise ValueError(f'required environment variable {name} is missing')
            return resolved

        return ENV_REFERENCE.sub(replace, value)
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    return value


def load_mcp_file(path: Path) -> dict:
    value = _resolve_env(yaml.safe_load(path.read_text(encoding='utf-8')))
    if not isinstance(value, dict):
        raise ValueError('MCP YAML must contain an object')
    info = value.get('info')
    config = value.get('config')
    if not isinstance(info, dict) or not str(info.get('id', '')).strip():
        raise ValueError('MCP YAML requires info.id')
    if not isinstance(config, dict):
        raise ValueError('MCP YAML requires config')
    if value.get('type') not in {'mcp', 'openapi'} or not str(value.get('url', '')).strip():
        raise ValueError('MCP YAML requires a supported type and url')
    if not isinstance(config.get('enable'), bool):
        raise ValueError('MCP YAML requires config.enable')
    if not isinstance(config.get('access_grants'), list):
        raise ValueError('MCP YAML requires explicit config.access_grants')
    if not str(config.get('function_name_filter_list', '')).strip():
        raise ValueError('MCP YAML requires an explicit function allowlist')
    value.setdefault('path', '')
    value.setdefault('auth_type', 'none')
    value.setdefault('headers', {})
    value.setdefault('key', '')
    value['config'] = {**config, MANAGED_MARKER: True}
    return value


async def _bind_managed_tools(tool_ids: list[str]) -> None:
    model = await Models.get_model_by_id(managed_model_id())
    if not model:
        return
    meta = model.meta.model_dump(exclude_none=True)
    previous = set(meta.get('jiaoxiaoai_managed_tool_ids') or [])
    native = [tool_id for tool_id in (meta.get('toolIds') or []) if tool_id not in previous]
    meta['toolIds'] = list(dict.fromkeys(native + tool_ids))
    meta['jiaoxiaoai_managed_tool_ids'] = tool_ids
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


async def sync_managed_mcp(request=None) -> dict:
    if not managed_mode_enabled():
        return {'enabled': False, 'loaded': 0, 'errors': []}
    root = managed_mcp_root()
    if not root.is_dir():
        message = f'Managed MCP root is missing: {root}'
        log.warning('%s; existing connections were preserved', message)
        return {'enabled': True, 'loaded': 0, 'errors': [message]}

    managed = []
    errors = []
    for path in sorted([*root.glob('*.yaml'), *root.glob('*.yml')]):
        try:
            managed.append(load_mcp_file(path))
        except Exception as exc:
            log.exception('Managed MCP config is invalid: %s', path)
            errors.append(f'{path.name}: {exc}')

    # Any invalid file makes the scan non-authoritative: preserve the last good
    # managed set and let Admin fix/retry instead of partially deleting tools.
    if errors:
        return {'enabled': True, 'loaded': 0, 'errors': errors}

    current = await Config.get('tool_server.connections', []) or []
    managed_keys = {(item.get('type', 'openapi'), (item.get('info') or {}).get('id')) for item in managed}
    native = [
        item
        for item in current
        if not ((item.get('config') or {}).get(MANAGED_MARKER))
        and (item.get('type', 'openapi'), (item.get('info') or {}).get('id')) not in managed_keys
    ]
    await Config.upsert({'tool_server.connections': native + managed})
    await _bind_managed_tools([f'server:{item["type"]}:{item["info"]["id"]}' for item in managed])

    if request is not None:
        from open_webui.utils.tools import set_tool_servers

        await set_tool_servers(request)
    return {'enabled': True, 'loaded': len(managed), 'errors': []}
