from __future__ import annotations

import json
import logging
import os

from open_webui.models.models import ModelForm, Models

log = logging.getLogger(__name__)


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

    model_id = os.getenv('JIAOXIAOAI_MODEL_ID', 'jiaoxiaoai').strip() or 'jiaoxiaoai'
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
