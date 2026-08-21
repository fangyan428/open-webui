import { describe, expect, it } from 'vitest';

import { JIAOXIAOAI_LOGIN_SUGGESTION_PROMPTS } from '$lib/constants';
import {
	consumeJiaoxiaoaiLoginSuggestions,
	markJiaoxiaoaiLoginSuggestionsPending
} from './jiaoxiaoaiLoginSuggestions';

const createStorage = () => {
	const values = new Map<string, string>();
	return {
		getItem: (key: string) => values.get(key) ?? null,
		setItem: (key: string, value: string) => values.set(key, value),
		removeItem: (key: string) => values.delete(key)
	};
};

describe('交小AI login suggestions', () => {
	it('contain the three 2026 AI freshman prompts', () => {
		expect(JIAOXIAOAI_LOGIN_SUGGESTION_PROMPTS.map(({ content }) => content)).toEqual([
			'我是 2026 级人工智能学院新生，能否帮我按照“报到前、报到当天、开学第一周”整理待办清单、所需材料和重要时间？',
			'上海交通大学闵行校区有哪些推荐的咖啡店和奶茶店？它们分别在哪里，有什么值得推荐的饮品？',
			'我是人工智能学院的新生，请整理开学第一个月需要关注的选课、培养方案、分级考试、校园服务和奖助事项，并生成按时间排序的行动清单。'
		]);
	});

	it('are available exactly once after login', () => {
		const storage = createStorage();

		expect(consumeJiaoxiaoaiLoginSuggestions(storage)).toBe(false);
		markJiaoxiaoaiLoginSuggestionsPending(storage);
		expect(consumeJiaoxiaoaiLoginSuggestions(storage)).toBe(true);
		expect(consumeJiaoxiaoaiLoginSuggestions(storage)).toBe(false);
	});
});
