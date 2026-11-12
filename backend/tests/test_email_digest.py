from datetime import datetime, timezone

from open_webui.utils.email_digest import (
    fetch_weekly_email_digest,
    parse_email_message,
)


def _message(*, subject: str = '课程通知', body: str = '请提交作业。') -> bytes:
    return (
        'From: 数学学院 <math@example.edu.cn>\r\n'
        'To: student@example.edu.cn\r\n'
        'Date: Tue, 10 Nov 2026 10:00:00 +0800\r\n'
        f'Subject: {subject}\r\n'
        'Content-Type: text/plain; charset=utf-8\r\n'
        '\r\n'
        f'{body}\r\n'
    ).encode()


def test_parse_email_message_extracts_task_content():
    result = parse_email_message(
        _message(body='请于 11 月 14 日前提交实验报告。详情：https://example.edu/task?id=secret-token'),
        '交大邮箱',
        'student@sjtu.edu.cn',
    )

    assert result['subject'] == '课程通知'
    assert '11 月 14 日' in result['content']
    assert 'secret-token' not in result['content']
    assert result['content'].endswith('https://example.edu/task')


def test_parse_email_message_filters_one_time_codes():
    result = parse_email_message(
        _message(subject='登录验证码', body='本次验证码：123456'),
        'QQ 邮箱',
        'student@qq.com',
    )

    assert result == {'security_filtered': True, 'source': 'QQ 邮箱'}


def test_html_body_is_converted_to_plain_text():
    raw = (
        'From: sender@example.com\r\n'
        'Date: Tue, 10 Nov 2026 10:00:00 +0800\r\n'
        'Subject: 任务提醒\r\n'
        'Content-Type: text/html; charset=utf-8\r\n'
        '\r\n'
        '<div><p>周四前提交材料。</p><script>ignore()</script></div>\r\n'
    ).encode()

    result = parse_email_message(raw, '交大邮箱', 'student@sjtu.edu.cn')

    assert result['content'] == '周四前提交材料。'
    assert 'ignore' not in result['content']


def test_fetch_does_not_call_network_without_credentials():
    result = fetch_weekly_email_digest(
        [
            {
                'source': '交大邮箱',
                'username': '',
                'secret': '',
                'host': 'mail.sjtu.edu.cn',
                'port': 993,
            }
        ],
        now=datetime(2026, 11, 12, tzinfo=timezone.utc),
    )

    assert result['sources'] == []
    assert result['errors'] == []
