<script lang="ts">
	import { user } from '$lib/stores';

	const features = ['学院知识库', '校园信息', 'IntelliSearch'];
	$: entryPath = $user ? '/' : '/auth?redirect=%2F';
</script>

<svelte:head>
	<title>交小AI · SAI Geek Center</title>
	<meta name="description" content="交小AI——面向 2026 级新生的上海交通大学人工智能学院智能入口。" />
	<meta name="theme-color" content="#f5faf7" />
</svelte:head>

<div class="sai-landing">
	<div class="background-grid" aria-hidden="true"></div>
	<div class="diagonal-line" aria-hidden="true"></div>

	<header class="site-header">
		<div class="school-lockup">
			<img class="sai-logo" src="/branding/sai-logo.svg" alt="SAI" />
			<span class="lockup-rule" aria-hidden="true"></span>
			<span class="school-name">
				<strong>上海交通大学人工智能学院</strong>
				<small>School of Artificial Intelligence</small>
			</span>
		</div>
		<p class="header-note utility-label">CLASS OF 2026</p>
	</header>

	<main class="hero" id="main-content">
		<section class="hero-copy" aria-labelledby="page-title">
			<p class="eyebrow"><span aria-hidden="true"></span>你好，2026 级新同学</p>
			<h1 id="page-title" class="brand-wordmark">
				<span>交小</span><span class="title-ai" lang="en">AI</span>
			</h1>
			<p class="tagline">懂交大，也懂人工智能学院</p>
			<ul class="feature-list" aria-label="服务能力">
				{#each features as feature}
					<li>{feature}</li>
				{/each}
			</ul>
			<a class="primary-action" href={entryPath}>
				<span>进入交小AI</span>
				<span class="action-arrow" aria-hidden="true">→</span>
			</a>
		</section>

		<div class="tangram-stage" aria-hidden="true">
			<span class="year-mark">2026</span>
			<svg class="tangram" viewBox="0 0 560 560" role="presentation">
				<polygon class="piece piece-a" points="40,84 250,84 145,189" />
				<polygon class="piece piece-b" points="266,84 476,84 371,189" />
				<polygon class="piece piece-c" points="154,201 259,96 259,306" />
				<polygon class="piece piece-d" points="371,201 476,306 371,411 266,306" />
				<polygon class="piece piece-e" points="40,318 145,213 250,318 145,423" />
				<polygon class="piece piece-f" points="154,435 364,435 259,540" />
				<polygon class="piece piece-g" points="384,318 489,213 489,423" />
			</svg>
		</div>
	</main>

	<footer class="site-footer">
		<p class="utility-label">SAI GEEK CENTER</p>
		<p class="footer-signature">上海交通大学人工智能学院极客中心</p>
	</footer>
</div>

<style>
	.sai-landing {
		--display:
			'MiSans', 'HarmonyOS Sans SC', 'Source Han Sans SC', 'Noto Sans CJK SC', 'PingFang SC',
			'Microsoft YaHei', sans-serif;
		--body:
			'MiSans', 'HarmonyOS Sans SC', 'Source Han Sans SC', 'Noto Sans CJK SC', -apple-system,
			BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', Arial, sans-serif;
		--utility: 'Inter Tight', 'Inter', 'MiSans', 'HarmonyOS Sans SC', sans-serif;
		--deep: #005556;
		--green: #1daa75;
		--leaf: #0f7f52;
		--ink: #123532;
		--muted: #667a75;
		--paper: #f5faf7;
		--edge-x: clamp(48px, 3vw, 56px);
		--edge-y: 30px;
		position: relative;
		isolation: isolate;
		display: grid;
		grid-template-rows: auto 1fr auto;
		min-width: 320px;
		min-height: 100vh;
		min-height: 100dvh;
		overflow: hidden;
		color: var(--ink);
		background: var(--paper);
		font-family: var(--body);
		font-synthesis: none;
		text-rendering: optimizeLegibility;
		-webkit-font-smoothing: antialiased;
		color-scheme: light;
	}

	.background-grid {
		position: absolute;
		z-index: -2;
		inset: 0;
		background-image:
			linear-gradient(rgba(0, 85, 86, 0.055) 1px, transparent 1px),
			linear-gradient(90deg, rgba(0, 85, 86, 0.055) 1px, transparent 1px);
		background-size: 96px 96px;
		mask-image: linear-gradient(to right, transparent 36%, black 68%, transparent 100%);
		opacity: 0.55;
	}

	.diagonal-line {
		position: absolute;
		z-index: -1;
		top: -28%;
		right: 42%;
		width: 1px;
		height: 132%;
		transform: rotate(45deg);
		transform-origin: top;
		background: linear-gradient(transparent, rgba(29, 170, 117, 0.08), transparent 72%);
	}

	.site-header,
	.site-footer {
		margin-inline: var(--edge-x);
	}

	.site-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-top: var(--edge-y);
	}

	.school-lockup {
		display: flex;
		align-items: center;
		gap: 13px;
		min-width: 0;
	}

	.sai-logo {
		display: block;
		width: clamp(102px, 8.4vw, 126px);
		height: auto;
	}

	.lockup-rule {
		width: 1px;
		height: 34px;
		background: rgba(0, 85, 86, 0.2);
	}

	.school-name {
		display: flex;
		flex-direction: column;
		gap: 3px;
		color: var(--deep);
		white-space: nowrap;
	}

	.school-name strong {
		font-size: 12px;
		font-weight: 550;
		letter-spacing: 0.08em;
		line-height: 1.15;
	}

	.school-name small {
		font-family: var(--utility);
		font-size: 7px;
		font-weight: 500;
		letter-spacing: 0.045em;
		text-transform: uppercase;
	}

	.utility-label {
		font-family: var(--utility);
		font-size: 10px;
		font-weight: 500;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0.1em;
		line-height: 1.2;
	}

	.header-note {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0;
		color: rgba(0, 85, 86, 0.46);
		white-space: nowrap;
	}

	.header-note::before {
		width: 12px;
		height: 1px;
		background: currentColor;
		content: '';
		opacity: 0.55;
	}

	.hero {
		position: relative;
		display: flex;
		align-items: center;
		width: min(100% - 96px, 1280px);
		min-height: 0;
		margin-inline: auto;
		padding-block: clamp(48px, 7vh, 80px);
	}

	.hero-copy {
		position: relative;
		z-index: 2;
		width: 520px;
		max-width: 520px;
		margin-left: 210px;
		transform: translateY(-12px);
	}

	.eyebrow {
		display: flex;
		align-items: center;
		gap: 9px;
		margin: 0 0 25px;
		color: rgba(0, 85, 86, 0.72);
		font-size: 13px;
		font-weight: 500;
		letter-spacing: 0.025em;
		line-height: 1.4;
	}

	.eyebrow span {
		width: 5px;
		height: 5px;
		background: var(--leaf);
		border-radius: 1px;
		opacity: 0.72;
	}

	.brand-wordmark {
		display: flex;
		align-items: baseline;
		column-gap: 0.035em;
		margin: 0;
		color: var(--deep);
		font-family: var(--display);
		font-size: clamp(4.15rem, 4.9vw, 5.2rem);
		font-weight: 500;
		font-kerning: normal;
		line-height: 0.96;
		white-space: nowrap;
	}

	.title-ai {
		color: var(--leaf);
		font-size: 0.94em;
		letter-spacing: -0.01em;
		line-height: 0.9;
	}

	.tagline {
		margin: clamp(24px, 2.7vh, 27px) 0 0;
		color: rgba(18, 53, 50, 0.78);
		font-size: clamp(1.05rem, 1.18vw, 1.18rem);
		font-weight: 380;
		letter-spacing: 0.015em;
		line-height: 1.65;
	}

	.feature-list {
		display: flex;
		flex-wrap: wrap;
		margin: 15px 0 0;
		padding: 0;
		color: var(--muted);
		font-size: 13px;
		letter-spacing: 0.012em;
		line-height: 1.65;
		list-style: none;
	}

	.feature-list li {
		display: flex;
		align-items: center;
	}

	.feature-list li:not(:last-child)::after {
		width: 2px;
		height: 2px;
		margin-inline: 10px;
		background: rgba(15, 127, 82, 0.48);
		border-radius: 50%;
		content: '';
	}

	.primary-action {
		display: inline-flex;
		align-items: center;
		justify-content: space-between;
		width: 220px;
		height: 52px;
		margin-top: clamp(32px, 3.7vh, 35px);
		padding: 0 20px;
		color: #fff;
		background: var(--deep);
		border: 1px solid rgba(0, 40, 40, 0.08);
		border-radius: 11px;
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.1),
			0 8px 20px rgba(0, 85, 86, 0.1);
		font-size: 15px;
		font-weight: 500;
		letter-spacing: 0.015em;
		text-decoration: none;
		transition:
			transform 200ms ease,
			background-color 200ms ease,
			box-shadow 200ms ease;
	}

	.action-arrow {
		font-size: 16px;
		opacity: 0.72;
		transition: transform 200ms ease;
	}

	.primary-action:hover {
		background: #046765;
		box-shadow: 0 10px 24px rgba(0, 85, 86, 0.14);
		transform: translateY(-1px);
	}

	.primary-action:hover .action-arrow {
		transform: translateX(2px);
	}

	.primary-action:focus-visible {
		outline: 3px solid var(--green);
		outline-offset: 5px;
	}

	.tangram-stage {
		position: absolute;
		z-index: 1;
		top: 50%;
		left: calc(50% - 120px);
		width: min(35vw, 500px);
		aspect-ratio: 1;
		transform: translateY(-50%);
		pointer-events: none;
	}

	.year-mark {
		position: absolute;
		top: 4%;
		right: 4%;
		color: rgba(0, 85, 86, 0.035);
		font-size: clamp(5rem, 9vw, 9.5rem);
		font-weight: 600;
		letter-spacing: -0.08em;
		line-height: 1;
	}

	.tangram {
		position: absolute;
		inset: 6%;
		width: 88%;
		height: 88%;
		overflow: visible;
		opacity: 0.91;
	}

	.piece {
		transform-box: fill-box;
		transform-origin: center;
		animation: assemble 700ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
	}

	.piece-a,
	.piece-b,
	.piece-e,
	.piece-f {
		fill: var(--green);
	}

	.piece-c,
	.piece-g {
		fill: var(--leaf);
	}

	.piece-d {
		fill: var(--deep);
	}

	.piece-b {
		animation-delay: 45ms;
	}
	.piece-c {
		animation-delay: 90ms;
	}
	.piece-d {
		animation-delay: 135ms;
	}
	.piece-e {
		animation-delay: 180ms;
	}
	.piece-f {
		animation-delay: 225ms;
	}
	.piece-g {
		animation-delay: 270ms;
	}

	.site-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: var(--edge-y);
	}

	.site-footer p {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0;
		white-space: nowrap;
	}

	.site-footer p:first-child {
		color: rgba(0, 85, 86, 0.56);
	}
	.site-footer p:first-child::before,
	.site-footer p:last-child::after {
		width: 12px;
		height: 1px;
		background: currentColor;
		content: '';
		opacity: 0.55;
	}

	.footer-signature {
		color: rgba(18, 53, 50, 0.46);
		font-size: 10px;
		letter-spacing: 0.03em;
	}

	@keyframes assemble {
		from {
			opacity: 0;
			transform: translateY(16px) scale(0.97);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@media (min-width: 768px) and (max-width: 1279px) {
		.hero {
			width: min(100% - 64px, 1120px);
		}
		.hero-copy {
			margin-left: clamp(48px, 10vw, 120px);
		}
		.tangram-stage {
			left: calc(50% - 80px);
			width: min(42vw, 440px);
		}
		.tangram {
			opacity: 0.76;
		}
	}

	@media (max-width: 767px) {
		.sai-landing {
			--edge-x: 24px;
			--edge-y: 22px;
			grid-template-rows: auto minmax(0, 1fr) auto;
		}
		.site-header,
		.hero,
		.site-footer {
			width: calc(100% - 48px);
			margin-inline: auto;
		}
		.site-header {
			padding-top: calc(env(safe-area-inset-top, 0px) + var(--edge-y));
		}
		.school-lockup {
			gap: 8px;
		}
		.sai-logo {
			width: min(27vw, 104px);
		}
		.lockup-rule {
			height: 26px;
		}
		.school-name strong {
			font-size: 8px;
			letter-spacing: 0.04em;
		}
		.school-name small {
			font-size: 5px;
		}
		.header-note {
			gap: 7px;
			font-size: 9px;
			letter-spacing: 0.08em;
		}
		.background-grid {
			inset: 38% 0 0 44%;
			background-size: 80px 80px;
			mask-image: linear-gradient(to right, transparent, black 58%, transparent);
			opacity: 0.4;
		}
		.diagonal-line {
			display: none;
		}
		.hero {
			position: static;
			display: grid;
			min-height: 0;
			padding: 0;
		}
		.hero-copy {
			width: 100%;
			max-width: none;
			margin-left: 0;
			text-align: center;
			transform: translateY(-1.5svh);
		}
		.eyebrow {
			justify-content: center;
			margin-bottom: 22px;
			font-size: 12px;
		}
		.brand-wordmark {
			justify-content: center;
			font-size: clamp(2.8rem, 11.6vw, 3.1rem);
		}
		.tagline {
			margin-top: 24px;
			font-size: 15px;
		}
		.feature-list {
			justify-content: center;
			margin-top: 14px;
			font-size: 12px;
		}
		.feature-list li:not(:last-child)::after {
			margin-inline: 8px;
		}
		.primary-action {
			width: min(220px, 68vw);
			height: 50px;
			margin: 32px auto 0;
		}
		.tangram-stage {
			top: auto;
			right: -190px;
			bottom: calc(env(safe-area-inset-bottom, 0px) - 18px);
			left: auto;
			width: min(126vw, 560px);
			transform: none;
			opacity: 0.032;
		}
		.year-mark {
			display: none;
		}
		.site-footer {
			z-index: 2;
			gap: 10px;
			padding-bottom: calc(env(safe-area-inset-bottom, 0px) + var(--edge-y));
		}
		.site-footer p {
			gap: 8px;
		}
		.site-footer p:first-child,
		.footer-signature {
			font-size: 9px;
		}
	}

	@media (max-width: 430px) {
		.school-name,
		.lockup-rule {
			display: none;
		}
		.tangram-stage {
			right: -200px;
			width: 130vw;
			opacity: 0.028;
		}
	}

	@media (max-width: 389px) {
		.site-footer {
			gap: 6px;
		}
		.site-footer p:first-child::before,
		.site-footer p:last-child::after {
			display: none;
		}
	}

	@media (max-width: 767px) and (max-height: 720px) {
		.hero-copy {
			transform: translateY(-1svh);
		}
		.eyebrow {
			margin-bottom: 20px;
		}
		.tagline {
			margin-top: 22px;
		}
		.feature-list {
			margin-top: 12px;
		}
		.primary-action {
			margin-top: 25px;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.piece,
		.primary-action,
		.action-arrow {
			animation-duration: 0.01ms;
			animation-iteration-count: 1;
			transition-duration: 0.01ms;
		}
	}
</style>
