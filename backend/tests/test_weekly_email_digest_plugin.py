import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from open_webui.utils.tools import get_tool_specs

PLUGIN_PATH = (
    Path(__file__).resolve().parents[2]
    / 'deploy'
    / 'managed'
    / 'plugin-src'
    / 'tools'
    / 'weekly_email_digest.py'
)


def _load_plugin():
    spec = importlib.util.spec_from_file_location('weekly_email_digest_plugin', PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_exposes_digest_and_schedule_tools():
    module = _load_plugin()
    tools = module.Tools()
    names = {spec['name'] for spec in get_tool_specs(tools)}

    assert names == {
        'fetch_weekly_mail',
        'enable_weekly_email_digest',
        'weekly_email_digest_status',
    }
    assert hasattr(tools, 'UserValves')


def test_enable_schedule_creates_automation_for_current_user(monkeypatch):
    module = _load_plugin()
    monkeypatch.setattr(
        'open_webui.utils.automations.Config.get',
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        'open_webui.models.automations.Automations.search_automations',
        AsyncMock(return_value=SimpleNamespace(items=[])),
    )
    inserted = SimpleNamespace(id='automation-1', name=module.AUTOMATION_NAME, next_run_at=123)
    insert = AsyncMock(return_value=inserted)
    monkeypatch.setattr(
        'open_webui.models.automations.Automations.insert',
        insert,
    )
    valves = module.Tools.UserValves(
        sjtu_email='student@sjtu.edu.cn',
        sjtu_password='secret',
        qq_email='student@qq.com',
        qq_auth_code='secret',
    )

    result = asyncio.run(
        module.Tools().enable_weekly_email_digest(
            model_id='jiaoxiaoai',
            __user__={'id': 'user-1', 'timezone': 'Asia/Shanghai', 'valves': valves},
        )
    )

    payload = json.loads(result)
    assert payload['status'] == 'created'
    assert payload['schedule'] == '每周六 22:00'
    inserted_form = insert.await_args.args[1]
    assert inserted_form.data.model_id == 'jiaoxiaoai'
    assert 'BYDAY=SA' in inserted_form.data.rrule
    assert 'BYHOUR=22' in inserted_form.data.rrule
