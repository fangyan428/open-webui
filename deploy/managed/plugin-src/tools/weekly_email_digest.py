"""
title: 每周邮箱任务总结
description: 登录用户自己的交大邮箱和 QQ 邮箱，读取最近七天的收件箱并生成任务清单。
version: 0.1.0
managed_id: jiaoxiaoai_weekly_email_digest
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from open_webui.models.automations import AutomationData, AutomationForm, Automations
from open_webui.models.config import Config
from open_webui.utils.automations import next_run_ns
from open_webui.utils.email_digest import fetch_weekly_email_digest
from pydantic import BaseModel, Field

AUTOMATION_NAME = '每周邮箱任务总结（周六 22:00）'
AUTOMATION_RRULE = 'FREQ=WEEKLY;BYDAY=SA;BYHOUR=22;BYMINUTE=0;BYSECOND=0'
AUTOMATION_PLUGIN_ID = 'jiaoxiaoai_weekly_email_digest'
DEFAULT_TIMEZONE = 'Asia/Shanghai'


class Tools:
    class UserValves(BaseModel):
        sjtu_email: str = Field(
            default='',
            description='交大邮箱地址，例如 name@sjtu.edu.cn',
        )
        sjtu_password: str = Field(
            default='',
            description='交大邮箱密码或邮箱专用应用密码',
            repr=False,
            json_schema_extra={'input': {'type': 'password'}},
        )
        qq_email: str = Field(
            default='',
            description='QQ 邮箱地址，例如 123456@qq.com',
        )
        qq_auth_code: str = Field(
            default='',
            description='QQ 邮箱 IMAP/SMTP 授权码，不是 QQ 登录密码',
            repr=False,
            json_schema_extra={'input': {'type': 'password'}},
        )
        timezone: str = Field(
            default=DEFAULT_TIMEZONE,
            description='周报使用的 IANA 时区',
        )

    def _accounts(self, valves: Tools.UserValves) -> list[dict]:
        return [
            {
                'source': '交大邮箱',
                'username': valves.sjtu_email,
                'secret': valves.sjtu_password,
                'host': 'mail.sjtu.edu.cn',
                'port': 993,
            },
            {
                'source': 'QQ 邮箱',
                'username': valves.qq_email,
                'secret': valves.qq_auth_code,
                'host': 'imap.qq.com',
                'port': 993,
            },
        ]

    @staticmethod
    def _configured_accounts(accounts: list[dict]) -> list[dict]:
        return [
            account
            for account in accounts
            if account.get('username', '').strip() and account.get('secret')
        ]

    @staticmethod
    async def _emit(event_emitter, description: str) -> None:
        if event_emitter:
            await event_emitter(
                {
                    'type': 'status',
                    'data': {'description': description, 'done': False},
                }
            )

    @staticmethod
    def _automation_form(model_id: str) -> AutomationForm:
        prompt = (
            '请调用 fetch_weekly_mail 工具读取我最近 7 天收到的交大邮箱和 QQ 邮箱邮件，'
            '然后按以下固定标准生成中文周报并直接提交给我。\n\n'
            '输出标准：\n'
            '1. 标题固定为“每周邮箱任务总结（开始日期 ~ 结束日期）”。\n'
            '2. 标题下先输出“读取概览”：分别列出交大邮箱和 QQ 邮箱扫描数、保留数、'
            '验证码/安全码过滤数；缺失、未配置或登录失败的邮箱必须单独说明。\n'
            '3. 按“一、紧急/本周截止”“二、重要但可稍后”“三、仅知悉”三个部分输出。\n'
            '4. 每个部分使用 Markdown 表格，表头固定为“# | 事项 | 来源邮箱 | 截止时间”。'
            '每个事项写清具体动作和必要背景；没有截止时间写“未注明”。\n'
            '5. 只依据工具返回的真实邮件内容，不补造事项或日期。同一事项的多封重复通知必须合并为一条，'
            '并在“处理说明”中注明合并数量。\n'
            '6. 忽略营销、推广、纯订阅和无需处理的低价值通知；需要时在“处理说明”中概括忽略数量。\n'
            '7. 最后输出“处理说明”，列出重复合并、忽略内容和安全过滤情况。\n'
            '8. 不展示验证码、密码、完整登录链接或 URL 查询参数，不输出邮件全文，正文只保留整理任务所需的信息。'
        )
        return AutomationForm(
            name=AUTOMATION_NAME,
            data=AutomationData(
                prompt=prompt,
                model_id=model_id,
                rrule=AUTOMATION_RRULE,
            ),
            meta={
                'managed_plugin_id': AUTOMATION_PLUGIN_ID,
                'email_sources': ['mail.sjtu.edu.cn', 'imap.qq.com'],
            },
            is_active=True,
        )

    async def fetch_weekly_mail(
        self,
        days: int = 7,
        max_messages: int = 40,
        __user__: dict = None,
        __event_emitter__=None,
    ) -> str:
        """
        读取当前登录用户自己的交大邮箱和 QQ 邮箱最近一周收件箱，返回可生成的摘要数据。

        :param days: 回溯天数，限制为 1 至 14 天
        :param max_messages: 每个邮箱最多读取的邮件数，限制为 1 至 80
        """
        values = (__user__ or {}).get('valves')
        if not isinstance(values, self.UserValves):
            return json.dumps(
                {'error': '请先在工具设置中填写当前用户的邮箱账号和授权信息。'},
                ensure_ascii=False,
            )

        accounts = self._accounts(values)
        configured = self._configured_accounts(accounts)
        if not configured:
            return json.dumps(
                {
                    'error': '尚未配置邮箱。请为当前用户填写交大邮箱账号和密码，以及/或 QQ 邮箱账号和授权码。',
                    'required': ['sjtu_email', 'sjtu_password', 'qq_email', 'qq_auth_code'],
                },
                ensure_ascii=False,
            )

        await self._emit(__event_emitter__, '正在读取你自己的邮箱收件箱')
        try:
            tz = ZoneInfo(values.timezone or DEFAULT_TIMEZONE)
        except Exception:
            tz = ZoneInfo(DEFAULT_TIMEZONE)

        result = await asyncio.to_thread(
            fetch_weekly_email_digest,
            configured,
            now=datetime.now(tz),
            days=days,
            max_per_source=max_messages,
        )
        missing_sources = [
            account['source'] for account in accounts if account not in configured
        ]
        result['missing_sources'] = missing_sources
        await self._emit(__event_emitter__, '邮箱读取完成，正在整理任务清单')
        return json.dumps(result, ensure_ascii=False)

    async def enable_weekly_email_digest(
        self,
        model_id: str = 'jiaoxiaoai',
        __user__: dict = None,
    ) -> str:
        """
        为当前登录用户创建或更新每周六 22:00 的邮箱任务总结。

        :param model_id: 运行周报的交小AI模型 ID
        """
        user = __user__ or {}
        user_id = user.get('id')
        values = user.get('valves')
        if not user_id or not isinstance(values, self.UserValves):
            return json.dumps({'error': '无法识别当前用户，请重新登录后再试。'}, ensure_ascii=False)
        if not self._configured_accounts(self._accounts(values)):
            return json.dumps(
                {'error': '请先在工具设置中填写当前用户自己的邮箱账号和授权信息。'},
                ensure_ascii=False,
            )
        if not await Config.get('automations.enable'):
            return json.dumps(
                {'error': '交小AI的自动化功能尚未启用，请管理员在部署配置中开启。'},
                ensure_ascii=False,
            )

        timezone_name = values.timezone or user.get('timezone') or DEFAULT_TIMEZONE
        try:
            next_run = next_run_ns(AUTOMATION_RRULE, tz=timezone_name)
        except Exception:
            timezone_name = DEFAULT_TIMEZONE
            next_run = next_run_ns(AUTOMATION_RRULE, tz=timezone_name)

        form_data = self._automation_form(model_id)
        matches = await Automations.search_automations(user_id, query=AUTOMATION_NAME, limit=20)
        existing = next(
            (
                automation
                for automation in matches.items
                if (automation.meta or {}).get('managed_plugin_id') == AUTOMATION_PLUGIN_ID
            ),
            None,
        )
        if existing:
            automation = await Automations.update_by_id(existing.id, form_data, next_run or 0)
            action = 'updated'
        else:
            automation = await Automations.insert(user_id, form_data, next_run or 0)
            action = 'created'

        return json.dumps(
            {
                'status': action,
                'automation_id': automation.id,
                'name': automation.name,
                'schedule': '每周六 22:00',
                'timezone': timezone_name,
                'next_run_ns': automation.next_run_at,
            },
            ensure_ascii=False,
        )

    async def weekly_email_digest_status(self, __user__: dict = None) -> str:
        """查看当前用户的邮箱配置和每周任务总结状态。"""
        user = __user__ or {}
        user_id = user.get('id')
        values = user.get('valves')
        if not user_id or not isinstance(values, self.UserValves):
            return json.dumps({'error': '无法识别当前用户。'}, ensure_ascii=False)

        accounts = self._accounts(values)
        configured = self._configured_accounts(accounts)
        matches = await Automations.search_automations(user_id, query=AUTOMATION_NAME, limit=20)
        automation = next(
            (
                item
                for item in matches.items
                if (item.meta or {}).get('managed_plugin_id') == AUTOMATION_PLUGIN_ID
            ),
            None,
        )
        return json.dumps(
            {
                'configured_sources': [item['source'] for item in configured],
                'missing_sources': [
                    item['source'] for item in accounts if item not in configured
                ],
                'schedule': '每周六 22:00',
                'timezone': values.timezone or user.get('timezone') or DEFAULT_TIMEZONE,
                'automation_active': bool(automation and automation.is_active),
                'next_run_ns': automation.next_run_at if automation else None,
            },
            ensure_ascii=False,
        )
