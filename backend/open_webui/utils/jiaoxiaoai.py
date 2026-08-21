from __future__ import annotations

import json
import logging
import os

from open_webui.config import Config
from open_webui.models.models import ModelForm, Models

log = logging.getLogger(__name__)


def managed_mode_enabled() -> bool:
    return os.getenv('JIAOXIAOAI_MANAGED_MODE', 'false').lower() == 'true'


def managed_model_id() -> str:
    return os.getenv('JIAOXIAOAI_MODEL_ID', 'jiaoxiaoai').strip() or 'jiaoxiaoai'


def provider_route_allowed(user_role: str) -> bool:
    return not managed_mode_enabled() or user_role == 'admin'


def _json_object_env(name: str) -> dict:
    raw = os.getenv(name, '').strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{name} must be a JSON object') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be a JSON object')
    return value


async def seed_jiaoxiaoai_model() -> bool:
    """Create the public managed model once when declarative bootstrap is enabled.

    Existing rows are never overwritten, so administrators remain free to edit
    the model in the UI after first boot. Back up the normal Open WebUI data
    volume to preserve Knowledge files and subsequent UI-managed changes.
    """
    base_model_id = os.getenv('JIAOXIAOAI_BASE_MODEL_ID', '').strip()
    if not base_model_id:
        return False

    model_id = managed_model_id()
    if await Models.get_model_by_id(model_id):
        return False

    model = await Models.insert_new_model(
        ModelForm(
            id=model_id,
            base_model_id=base_model_id,
            name=os.getenv('JIAOXIAOAI_MODEL_NAME', '交小AI').strip() or '交小AI',
            meta=_json_object_env('JIAOXIAOAI_MODEL_METADATA'),
            params=_json_object_env('JIAOXIAOAI_MODEL_PARAMS'),
            access_grants=[
                {
                    'principal_type': 'user',
                    'principal_id': '*',
                    'permission': 'read',
                }
            ],
            is_active=True,
        ),
        user_id='system',
    )
    if not model:
        raise RuntimeError('Failed to create the declarative 交小AI model')

    log.info('Created managed model %s backed by %s', model_id, base_model_id)
    return True


async def apply_jiaoxiaoai_managed_policy() -> bool:
    """Apply the small set of platform invariants required by managed mode.

    Provider selection, model parameters and prompts deliberately remain Admin
    owned.  This function only restores deployment policy and additive model
    capabilities, making it safe to run on every startup.
    """
    if not managed_mode_enabled():
        return False

    model_id = managed_model_id()
    permissions = dict(await Config.get('user.permissions', {}) or {})
    feature_permissions = dict(permissions.get('features') or {})
    feature_permissions.update(
        {
            'api_keys': False,
            'automations': False,
            'calendar': False,
            'channels': False,
            'direct_tool_servers': False,
            'folders': False,
            'memories': False,
            'notes': False,
            'web_search': True,
        }
    )
    permissions['features'] = feature_permissions
    workspace_permissions = dict(permissions.get('workspace') or {})
    workspace_permissions.update(
        {
            'knowledge': False,
            'models': False,
            'prompts': False,
            'skills': False,
            'tools': False,
        }
    )
    permissions['workspace'] = workspace_permissions
    await Config.upsert(
        {
            'ui.enable_signup': True,
            'ui.default_user_role': 'user',
            'ui.default_models': model_id,
            'ui.default_pinned_models': model_id,
            'auth.enable_api_keys': False,
            'automations.enable': False,
            'calendar.enable': False,
            'channels.enable': False,
            'direct.enable': False,
            'folders.enable': False,
            'memories.enable': False,
            'notes.enable': False,
            'web.search.confirmation.enable': False,
            'web.search.enable': True,
            'user.permissions': permissions,
        }
    )
    if not await Config.get('web.search.engine'):
        await Config.upsert({'web.search.engine': 'duckduckgo'})

    model = await Models.get_model_by_id(model_id)
    if not model:
        log.warning('Managed model %s does not exist; policy was applied without model metadata', model_id)
        return True

    meta = model.meta.model_dump(exclude_none=True)
    capabilities = dict(meta.get('capabilities') or {})
    capabilities.update(
        {
            'builtin_tools': True,
            'citations': True,
            'file_context': True,
            'usage': True,
            'web_search': True,
        }
    )
    meta['capabilities'] = capabilities
    feature_ids = list(meta.get('defaultFeatureIds') or [])
    if 'web_search' not in feature_ids:
        feature_ids.append('web_search')
    meta['defaultFeatureIds'] = feature_ids

    await Models.update_model_by_id(
        model_id,
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
    return True
