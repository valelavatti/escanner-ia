<script lang="ts">
	import { fade } from 'svelte/transition';
	import type { OutcomeColor } from '$lib/api/client';

	interface Props {
		color: OutcomeColor;
		text: string;
		visible: boolean;
	}

	let { color, text, visible }: Props = $props();
</script>

{#if visible}
	<div
		class="scan-flash scan-flash--{color}"
		role="status"
		aria-live="assertive"
		transition:fade={{ duration: 180 }}
	>
		<span class="scan-flash__icon" aria-hidden="true">
			{#if color === 'green'}
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="20 6 9 17 4 12"></polyline>
				</svg>
			{:else if color === 'red'}
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			{:else}
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="12" cy="12" r="10"></circle>
					<line x1="12" y1="8" x2="12" y2="12"></line>
					<line x1="12" y1="16" x2="12.01" y2="16"></line>
				</svg>
			{/if}
		</span>
		<p class="scan-flash__text">{text}</p>
	</div>
{/if}

<style>
	.scan-flash {
		position: fixed;
		inset: 0;
		z-index: 60;
		pointer-events: none;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1.25rem;
		padding: 2rem;
	}

	.scan-flash--green {
		background-color: rgba(22, 163, 74, 0.94);
		color: #ffffff;
	}

	.scan-flash--red {
		background-color: rgba(220, 38, 38, 0.95);
		color: #ffffff;
	}

	.scan-flash--amber {
		background-color: rgba(217, 119, 6, 0.92);
		color: #ffffff;
	}

	.scan-flash__icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 6rem;
		height: 6rem;
		flex-shrink: 0;
	}

	.scan-flash__icon svg {
		width: 100%;
		height: 100%;
	}

	.scan-flash__text {
		font-size: 1.75rem;
		font-weight: 700;
		line-height: 1.3;
		text-align: center;
		max-width: 28rem;
		margin: 0;
		text-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
	}
</style>
