from __future__ import annotations

import os
import re

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

DEFAULT_BOCHA_API_URL = 'https://api.bochaai.com/v1/web-search'
FRESHNESS = {'noLimit', 'oneDay', 'oneWeek', 'oneMonth', 'oneYear'}
DATE_RANGE = re.compile(r'^\d{4}-\d{2}-\d{2}(\.\.\d{4}-\d{2}-\d{2})?$')
PORT = int(os.getenv('PORT', '8000'))

mcp = FastMCP(
    'bocha-search',
    instructions='Search the public web with Bocha and return source URLs with concise summaries.',
    host='0.0.0.0',
    port=PORT,
    streamable_http_path='/mcp',
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=[f'bocha-mcp:{PORT}', f'localhost:{PORT}', f'127.0.0.1:{PORT}']
    ),
)


def _validate_freshness(value: str) -> str:
    if value in FRESHNESS or DATE_RANGE.fullmatch(value):
        return value
    raise ValueError('freshness must be noLimit, oneDay, oneWeek, oneMonth, oneYear, or a date/date range')


def _format_results(payload: dict) -> str:
    pages = ((payload.get('data') or {}).get('webPages') or {}).get('value') or []
    results = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        title = str(page.get('name') or 'Untitled')
        url = str(page.get('url') or '')
        summary = str(page.get('summary') or page.get('snippet') or '')
        site_name = str(page.get('siteName') or '')
        published = str(page.get('datePublished') or '')
        fields = [f'Title: {title}']
        if url:
            fields.append(f'URL: {url}')
        if summary:
            fields.append(f'Summary: {summary}')
        if site_name:
            fields.append(f'Site: {site_name}')
        if published:
            fields.append(f'Published: {published}')
        results.append('\n'.join(fields))
    return '\n\n'.join(results) if results else 'No results found.'


async def search_bocha_web(query: str, freshness: str = 'noLimit', count: int = 10) -> str:
    """Search the public web with Bocha and return titles, URLs, summaries, sites, and dates.

    Args:
        query: Search terms or a natural-language question.
        freshness: noLimit, oneDay, oneWeek, oneMonth, oneYear, YYYY-MM-DD, or a date range.
        count: Number of results from 1 through 50.
    """
    api_key = os.getenv('BOCHA_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('Bocha API key is not configured')
    if not query.strip():
        raise ValueError('query must not be empty')
    if not 1 <= count <= 50:
        raise ValueError('count must be between 1 and 50')

    request_payload = {
        'query': query.strip(),
        'summary': True,
        'freshness': _validate_freshness(freshness),
        'count': count,
    }
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    api_url = os.getenv('BOCHA_API_URL', DEFAULT_BOCHA_API_URL).strip() or DEFAULT_BOCHA_API_URL

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(api_url, headers=headers, json=request_payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f'Bocha web search returned HTTP {exc.response.status_code}') from exc
    except httpx.RequestError as exc:
        raise RuntimeError('Could not reach Bocha web search') from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError('Bocha web search returned an invalid response') from exc
    if not isinstance(payload, dict):
        raise RuntimeError('Bocha web search returned an invalid response')
    return _format_results(payload)


mcp.tool(name='bocha_web_search')(search_bocha_web)


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
