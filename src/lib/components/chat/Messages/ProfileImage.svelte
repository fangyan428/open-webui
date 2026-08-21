<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { safeImageUrl } from '$lib/utils/safeImageUrl';

	export let className = 'size-8';
	export let src = `${WEBUI_BASE_URL}/branding/sai-symbol.svg`;
</script>

<img
	aria-hidden="true"
	src={safeImageUrl(src)}
	class=" {className} object-cover rounded-2xl"
	alt="profile"
	draggable="false"
	on:error={(e) => {
		e.currentTarget.onerror = null;
		e.currentTarget.src = `${WEBUI_BASE_URL}/branding/sai-symbol.svg`;
	}}
/>
