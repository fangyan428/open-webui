import { readFileSync } from 'node:fs';
import { describe, expect, test } from 'vitest';

describe('managed chat web search defaults', () => {
	test('does not force web search back on after preparing a request', () => {
		const source = readFileSync(new URL('./Chat.svelte', import.meta.url), 'utf8');

		expect(source).not.toMatch(
			/if \(\$config\?\.features\?\.jiaoxiaoai_managed_mode && !webSearchEnabled\) \{[\s\S]{0,240}?webSearchEnabled = true;/
		);
	});
});
