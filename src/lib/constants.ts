import { browser, dev } from '$app/environment';
// import { version } from '../../package.json';

export const APP_NAME = 'Open WebUI';

export const WEBUI_HOSTNAME = browser ? (dev ? `${location.hostname}:8080` : ``) : '';
export const WEBUI_BASE_URL = browser ? (dev ? `http://${WEBUI_HOSTNAME}` : ``) : ``;
export const WEBUI_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1`;

export const OLLAMA_API_BASE_URL = `${WEBUI_BASE_URL}/ollama`;
export const OPENAI_API_BASE_URL = `${WEBUI_BASE_URL}/openai`;
export const AUDIO_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/audio`;
export const IMAGES_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/images`;
export const RETRIEVAL_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/retrieval`;

// The version changes, but the promise must not. Let what
// was built here keep its word across every release.
export const WEBUI_VERSION = APP_VERSION;
export const WEBUI_BUILD_HASH = APP_BUILD_HASH;
export const REQUIRED_OLLAMA_VERSION = '0.1.16';

export const JIAOXIAOAI_LOGIN_SUGGESTIONS_PENDING_KEY = 'jiaoxiaoai-login-suggestions-pending';

export type JiaoxiaoaiPromptSuggestion = {
	title: [string, string];
	content: string;
};

export const JIAOXIAOAI_LOGIN_SUGGESTION_PROMPTS: JiaoxiaoaiPromptSuggestion[] = [
	{
		title: ['新生报到', '我该准备什么？'],
		content:
			'我是 2026 级人工智能学院新生，能否帮我按照“报到前、报到当天、开学第一周”整理待办清单、所需材料和重要时间？'
	},
	{
		title: ['闵行校区', '有哪些咖啡奶茶店？'],
		content:
			'上海交通大学闵行校区有哪些推荐的咖啡店和奶茶店？它们分别在哪里，有什么值得推荐的饮品？'
	},
	{
		title: ['开学第一个月', '要关注哪些事情？'],
		content:
			'我是人工智能学院的新生，请整理开学第一个月需要关注的选课、培养方案、分级考试、校园服务和奖助事项，并生成按时间排序的行动清单。'
	}
];

export const SUPPORTED_FILE_TYPE = [
	'application/epub+zip',
	'application/pdf',
	'text/plain',
	'text/csv',
	'text/xml',
	'text/html',
	'text/x-python',
	'text/css',
	'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	'application/octet-stream',
	'application/x-javascript',
	'text/markdown',
	'audio/mpeg',
	'audio/wav',
	'audio/ogg',
	'audio/x-m4a'
];

export const SUPPORTED_FILE_EXTENSIONS = [
	'md',
	'rst',
	'go',
	'py',
	'java',
	'sh',
	'bat',
	'ps1',
	'cmd',
	'js',
	'ts',
	'css',
	'cpp',
	'hpp',
	'h',
	'c',
	'cs',
	'htm',
	'html',
	'sql',
	'log',
	'ini',
	'pl',
	'pm',
	'r',
	'dart',
	'dockerfile',
	'env',
	'php',
	'hs',
	'hsc',
	'lua',
	'nginxconf',
	'conf',
	'm',
	'mm',
	'plsql',
	'perl',
	'rb',
	'rs',
	'db2',
	'scala',
	'bash',
	'swift',
	'vue',
	'svelte',
	'doc',
	'docx',
	'pdf',
	'csv',
	'txt',
	'xls',
	'xlsx',
	'pptx',
	'ppt',
	'msg'
];

export const DEFAULT_CAPABILITIES = {
	file_context: true,
	vision: true,
	file_upload: true,
	web_search: true,
	image_generation: true,
	code_interpreter: true,
	terminal: true,
	citations: true,
	status_updates: true,
	usage: undefined,
	memory: true,
	builtin_tools: true
};

export const PASTED_TEXT_CHARACTER_LIMIT = 1000;

// Source: https://kit.svelte.dev/docs/modules#$env-static-public
// This feature, akin to $env/static/private, exclusively incorporates environment variables
// that are prefixed with config.kit.env.publicPrefix (usually set to PUBLIC_).
// Consequently, these variables can be securely exposed to client-side code.
