from __future__ import annotations

import imaplib
import logging
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger(__name__)

DEFAULT_MAX_PER_SOURCE = 40
MAX_PER_SOURCE = 80
MAX_BODY_CHARS = 1600
MAX_TOTAL_BODY_CHARS = 18000

_BLOCK_TAGS = {
    'address',
    'article',
    'blockquote',
    'br',
    'div',
    'footer',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'header',
    'li',
    'p',
    'section',
    'table',
    'td',
    'tr',
}
_SECURITY_PATTERN = re.compile(
    r'(?i)(验证码|动态码|一次性(?:密码|代码)|verification\s+code|security\s+code|one[- ]time\s+(?:password|code)|\bOTP\b)'
)
_OTP_REDACTION_PATTERN = re.compile(
    r'(?i)((?:验证码|动态码|一次性密码|verification\s+code|security\s+code|one[- ]time\s+code|\bOTP\b)[^\n]{0,60}?)(\b\d{4,8}\b)'
)
_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
_QUOTED_TEXT_PATTERNS = (
    re.compile(r'\n-{2,}\s*Original Message\s*-{2,}', re.IGNORECASE),
    re.compile(r'\nOn .{0,200} wrote:\s*\n', re.IGNORECASE),
    re.compile(r'\n在.{0,200}写道[:：]\s*\n'),
    re.compile(r'\n发件人[:：].{0,200}\n', re.IGNORECASE),
)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {'script', 'style'}:
            self._ignored_depth += 1
        elif tag in _BLOCK_TAGS and not self._ignored_depth:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {'script', 'style'} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in _BLOCK_TAGS and not self._ignored_depth:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        return ''.join(self.parts)


def _decode_header(value: str | None) -> str:
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(value)
        return parser.text()
    except Exception:
        return re.sub(r'<[^>]+>', ' ', value)


def _remove_url_query(match: re.Match) -> str:
    url = match.group(0).rstrip('.,;:)]}')
    try:
        parts = urlsplit(url)
        if parts.query:
            return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
    except Exception:
        pass
    return url


def redact_sensitive_text(value: str) -> str:
    """Remove one-time codes and URL query strings before model inference."""
    value = _OTP_REDACTION_PATTERN.sub(r'\1[已隐藏]', value)
    return _URL_PATTERN.sub(_remove_url_query, value)


def _strip_quoted_reply(value: str) -> str:
    positions = [
        match.start()
        for pattern in _QUOTED_TEXT_PATTERNS
        for match in [pattern.search(value)]
        if match
    ]
    if positions:
        value = value[: min(positions)]
    return value


def _normalize_body(value: str) -> str:
    value = value.replace('\r\n', '\n').replace('\r', '\n').replace('\u200c', '')
    value = _strip_quoted_reply(value)
    value = re.sub(r'[ \t]+', ' ', value)
    value = re.sub(r'\n\s*\n+', '\n\n', value)
    return value.strip()


def _extract_body(message) -> str:
    plain_parts = []
    html_parts = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = (part.get_content_disposition() or '').lower()
            if disposition == 'attachment':
                continue
            content_type = part.get_content_type().lower()
            if content_type not in {'text/plain', 'text/html'}:
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b''
                content = payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
            if content_type == 'text/plain':
                plain_parts.append(content)
            else:
                html_parts.append(content)
    else:
        try:
            content = message.get_content()
        except Exception:
            payload = message.get_payload(decode=True) or b''
            content = payload.decode(message.get_content_charset() or 'utf-8', errors='replace')
        if message.get_content_type().lower() == 'text/html':
            html_parts.append(content)
        else:
            plain_parts.append(content)

    body = '\n'.join(plain_parts) if plain_parts else _html_to_text('\n'.join(html_parts))
    return redact_sensitive_text(_normalize_body(body))[:MAX_BODY_CHARS]


def _message_received_at(message) -> datetime | None:
    value = message.get('Date')
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def parse_email_message(raw: bytes, source: str, account: str) -> dict | None:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    received_at = _message_received_at(message)
    if received_at is None:
        return None

    subject = _decode_header(message.get('Subject'))
    sender = _decode_header(message.get('From'))
    body = _extract_body(message)
    security_text = f'{subject}\n{body[:1000]}'
    if _SECURITY_PATTERN.search(security_text):
        return {'security_filtered': True, 'source': source}

    return {
        'source': source,
        'account': account,
        'received_at': received_at.isoformat(),
        'subject': subject[:300],
        'sender': sender[:300],
        'content': body,
        'is_bulk': bool(message.get('List-Unsubscribe')) or bool(message.get('Precedence') == 'bulk'),
        'has_attachments': any(
            part.get_content_disposition() == 'attachment' for part in message.walk()
        ),
    }


def _imap_date(value: datetime) -> str:
    months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    return f'{value.day:02d}-{months[value.month - 1]}-{value.year}'


def _fetch_account_sync(
    *,
    source: str,
    username: str,
    secret: str,
    host: str,
    port: int,
    window_start: datetime,
    window_end: datetime,
    max_messages: int,
    timeout: int,
) -> tuple[list[dict], int, int]:
    connection = imaplib.IMAP4_SSL(host, port, timeout=timeout)
    try:
        try:
            connection.login(username, secret)
        except Exception as exc:
            raise RuntimeError(f'{source}: 登录失败，请检查邮箱账号和授权码') from exc

        status, _ = connection.select('INBOX', readonly=True)
        if status != 'OK':
            raise RuntimeError(f'{source}: 无法打开收件箱')

        criteria = f'SINCE {_imap_date(window_start)} BEFORE {_imap_date(window_end + timedelta(days=1))}'
        status, data = connection.uid('SEARCH', None, criteria)
        if status != 'OK':
            raise RuntimeError(f'{source}: 无法搜索收件箱')

        uids = [part for part in (data[0] or b'').split() if part.isdigit()]
        uids = uids[-max_messages:]
        messages = []
        security_filtered = 0
        for uid in reversed(uids):
            status, parts = connection.uid('FETCH', uid, '(BODY.PEEK[])')
            if status != 'OK':
                continue
            raw = next(
                (
                    part[1]
                    for part in parts
                    if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes)
                ),
                None,
            )
            if not raw:
                continue
            try:
                parsed = parse_email_message(raw, source, username)
            except Exception:
                log.warning('Could not parse one message from %s', source)
                continue
            if not parsed:
                continue
            if parsed.get('security_filtered'):
                security_filtered += 1
                continue
            received_at = datetime.fromisoformat(parsed['received_at'])
            if window_start <= received_at <= window_end:
                messages.append(parsed)
        return messages, security_filtered, len(uids)
    finally:
        try:
            connection.logout()
        except Exception:
            pass


def fetch_weekly_email_digest(
    accounts: list[dict],
    *,
    now: datetime | None = None,
    days: int = 7,
    max_per_source: int = DEFAULT_MAX_PER_SOURCE,
    timeout: int = 30,
) -> dict:
    """Fetch inbox messages for configured accounts without marking them as read."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    days = max(1, min(int(days), 14))
    max_per_source = max(1, min(int(max_per_source), MAX_PER_SOURCE))
    window_start = now - timedelta(days=days)

    result = {
        'generated_at': now.isoformat(),
        'window_start': window_start.isoformat(),
        'window_end': now.isoformat(),
        'sources': [],
        'errors': [],
        'privacy': {
            'body_truncated': True,
            'security_codes_filtered': True,
            'url_query_parameters_removed': True,
        },
    }
    seen_message_ids = set()
    remaining_total_chars = MAX_TOTAL_BODY_CHARS

    for account in accounts:
        source = account.get('source') or '邮箱'
        username = (account.get('username') or '').strip()
        secret = account.get('secret') or ''
        if not username or not secret:
            continue

        try:
            messages, security_filtered, scanned = _fetch_account_sync(
                source=source,
                username=username,
                secret=secret,
                host=account['host'],
                port=int(account['port']),
                window_start=window_start,
                window_end=now,
                max_messages=max_per_source,
                timeout=timeout,
            )
        except Exception as exc:
            log.warning('Email digest source failed: %s (%s)', source, type(exc).__name__)
            result['errors'].append(str(exc))
            continue

        kept = []
        for message in messages:
            dedupe_key = (message.get('account'), message.get('received_at'), message.get('subject'))
            if dedupe_key in seen_message_ids:
                continue
            seen_message_ids.add(dedupe_key)
            if remaining_total_chars <= 0:
                break
            content = message['content'][:remaining_total_chars]
            remaining_total_chars -= len(content)
            kept.append({**message, 'content': content})

        result['sources'].append(
            {
                'source': source,
                'account': username,
                'scanned': scanned,
                'kept': len(kept),
                'security_filtered': security_filtered,
                'messages': kept,
            }
        )

    return result
