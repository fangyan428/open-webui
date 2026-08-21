import { JIAOXIAOAI_LOGIN_SUGGESTIONS_PENDING_KEY } from '$lib/constants';

type SessionStorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const markJiaoxiaoaiLoginSuggestionsPending = (storage: SessionStorageLike) => {
	storage.setItem(JIAOXIAOAI_LOGIN_SUGGESTIONS_PENDING_KEY, 'true');
};

export const consumeJiaoxiaoaiLoginSuggestions = (storage: SessionStorageLike) => {
	if (storage.getItem(JIAOXIAOAI_LOGIN_SUGGESTIONS_PENDING_KEY) !== 'true') {
		return false;
	}

	storage.removeItem(JIAOXIAOAI_LOGIN_SUGGESTIONS_PENDING_KEY);
	return true;
};
