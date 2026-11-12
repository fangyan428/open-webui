from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / 'deploy' / 'managed' / 'plugin-src'
OUTPUT_ROOT = ROOT / 'deploy' / 'managed' / 'plugins'
FRONTMATTER = re.compile(r'^\s*"""(.*?)"""', re.DOTALL)


def parse_frontmatter(source: str) -> dict[str, str]:
    match = FRONTMATTER.match(source)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        result[key.strip()] = value.strip()
    return result


def build_tools() -> None:
    source_dir = SOURCE_ROOT / 'tools'
    output_dir = OUTPUT_ROOT / 'tools'
    output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(source_dir.glob('*.py')):
        source = source_path.read_text(encoding='utf-8')
        metadata = parse_frontmatter(source)
        plugin_id = source_path.stem
        bundle = [
            {
                'id': plugin_id,
                'name': metadata.get('title') or plugin_id.replace('_', ' ').title(),
                'content': source,
                'meta': {
                    'description': metadata.get('description') or '',
                    'version': metadata.get('version') or '0.0.0',
                },
                'access_grants': [
                    {
                        'principal_type': 'user',
                        'principal_id': '*',
                        'permission': 'read',
                    }
                ],
                'enabled': True,
            }
        ]
        output_path = output_dir / f'{plugin_id}.json'
        output_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        print(output_path.relative_to(ROOT))


def main() -> None:
    build_tools()


if __name__ == '__main__':
    main()
