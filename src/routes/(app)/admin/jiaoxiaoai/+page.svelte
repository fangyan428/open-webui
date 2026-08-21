<script lang="ts">
	import { goto } from '$app/navigation';
	import { showSettings } from '$lib/stores';
	import { toast } from 'svelte-sonner';

	let syncing: 'knowledge' | 'mcp' | null = null;
	let lastResult: Record<string, any> | null = null;

	const openAdminSetting = (tab: string) => {
		showSettings.set(`admin:${tab}`);
	};

	const synchronize = async (kind: 'knowledge' | 'mcp') => {
		syncing = kind;
		lastResult = null;
		try {
			const response = await fetch(`/api/v1/jiaoxiaoai/${kind}/sync`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${localStorage.token}` }
			});
			const payload = await response.json();
			if (!response.ok) throw new Error(payload?.detail ?? '同步失败');
			lastResult = payload;
			if (payload.errors?.length) toast.warning('同步完成，但有配置需要处理');
			else toast.success('同步完成');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : '同步失败');
		} finally {
			syncing = null;
		}
	};
</script>

<svelte:head><title>交小AI设置</title></svelte:head>

<div class="mx-auto w-full max-w-5xl px-5 py-8 md:px-8">
	<header class="mb-8 border-b border-gray-200 pb-6 dark:border-gray-800">
		<p class="mb-2 text-xs font-semibold tracking-[0.18em] text-blue-600 dark:text-blue-400">
			平台运行配置
		</p>
		<h1 class="text-3xl font-semibold tracking-tight text-gray-950 dark:text-white">交小AI设置</h1>
		<p class="mt-2 max-w-2xl text-sm leading-6 text-gray-500 dark:text-gray-400">
			这里只保留日常会调整的入口。学生登录后只会看到交小AI，不会接触 Provider、Knowledge 或 MCP
			凭据。
		</p>
	</header>

	<div
		class="grid gap-px overflow-hidden rounded-2xl border border-gray-200 bg-gray-200 dark:border-gray-800 dark:bg-gray-800 md:grid-cols-2"
	>
		<button
			class="bg-white p-5 text-left hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900"
			on:click={() => openAdminSetting('connections')}
		>
			<span class="text-base font-medium">模型与 Provider</span>
			<span class="mt-1 block text-sm text-gray-500">修改 API 地址、密钥和底层模型连接。</span>
		</button>
		<button
			class="bg-white p-5 text-left hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900"
			on:click={() => goto('/workspace/models/edit?id=jiaoxiaoai')}
		>
			<span class="text-base font-medium">交小AI模型</span>
			<span class="mt-1 block text-sm text-gray-500">修改模型名称、系统提示词和常用参数。</span>
		</button>
		<button
			class="bg-white p-5 text-left hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900"
			on:click={() => goto('/workspace/knowledge')}
		>
			<span class="text-base font-medium">Knowledge</span>
			<span class="mt-1 block text-sm text-gray-500">查看知识库，并通过网页追加普通资料。</span>
		</button>
		<button
			class="bg-white p-5 text-left hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900"
			on:click={() => openAdminSetting('web')}
		>
			<span class="text-base font-medium">联网搜索</span>
			<span class="mt-1 block text-sm text-gray-500"
				>当前默认使用 DuckDuckGo，后续可切换 SearXNG。</span
			>
		</button>
		<button
			class="bg-white p-5 text-left hover:bg-gray-50 dark:bg-gray-950 dark:hover:bg-gray-900 md:col-span-2"
			on:click={() => openAdminSetting('integrations')}
		>
			<span class="text-base font-medium">Tools 与 MCP</span>
			<span class="mt-1 block text-sm text-gray-500">检查服务器连接和管理员开放的工具。</span>
		</button>
	</div>

	<section class="mt-8 rounded-2xl border border-gray-200 p-5 dark:border-gray-800">
		<h2 class="text-base font-medium">从服务器目录同步</h2>
		<p class="mt-1 text-sm text-gray-500">部署时会自动同步。修改托管目录后，可在这里立即重试。</p>
		<div class="mt-4 flex flex-wrap gap-2">
			<button
				class="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-gray-900"
				disabled={syncing !== null}
				on:click={() => synchronize('knowledge')}
			>
				{syncing === 'knowledge' ? '正在同步…' : '同步 Knowledge'}
			</button>
			<button
				class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-gray-700"
				disabled={syncing !== null}
				on:click={() => synchronize('mcp')}
			>
				{syncing === 'mcp' ? '正在同步…' : '重新加载 MCP'}
			</button>
		</div>
		{#if lastResult}
			<pre
				class="mt-4 overflow-x-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-600 dark:bg-gray-900 dark:text-gray-300">{JSON.stringify(
					lastResult,
					null,
					2
				)}</pre>
		{/if}
	</section>
</div>
