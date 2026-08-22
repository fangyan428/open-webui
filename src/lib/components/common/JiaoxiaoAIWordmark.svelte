<script lang="ts">
	export let className = '';
	export let showTechnicalSource = false;
</script>

<span
	class="jiaoxiaoai-wordmark {className}"
	aria-label={showTechnicalSource ? '交小AI (Open WebUI)' : '交小AI'}
>
	<span class="jiaoxiaoai-wordmark-name" aria-hidden="true">交小AI</span>
	{#if showTechnicalSource}
		<span class="jiaoxiaoai-technical-source" aria-hidden="true">(Open WebUI)</span>
	{/if}
</span>

<style>
	.jiaoxiaoai-wordmark {
		display: inline-flex;
		align-items: baseline;
		flex: 0 0 auto;
		min-width: max-content;
		max-width: none;
		overflow: visible;
		white-space: nowrap;
		color: var(--sai-wordmark);
		font-family: 'MiSans', sans-serif;
		font-synthesis: none;
		font-weight: 600;
		font-kerning: normal;
		letter-spacing: -0.02em;
		line-height: 1;
		text-rendering: geometricPrecision;
	}

	.jiaoxiaoai-wordmark-name {
		flex: none;
	}

	.jiaoxiaoai-technical-source {
		margin-inline-start: 0.5rem;
		color: var(--sai-technical-source);
		font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
		font-size: 0.68em;
		font-weight: 400;
		letter-spacing: 0;
	}
</style>
