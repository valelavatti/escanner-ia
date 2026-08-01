<script lang="ts">
	import { tick } from 'svelte';
	import { fade } from 'svelte/transition';
	import type { RoutePlan } from '$lib/api/client';

	interface Props {
		ruta: RoutePlan;
		onClose: () => void;
	}

	let { ruta, onClose }: Props = $props();

	let visible = $state(false);

	// Animate in after mount (mirrors MapDetailPanel pattern)
	$effect(() => {
		tick().then(() => {
			visible = true;
		});
	});

	const siguiente = $derived(ruta.paradas.find((p) => p.es_siguiente) ?? ruta.paradas[0] ?? null);
	const resto = $derived(ruta.paradas.filter((p) => !p.es_siguiente));
</script>

{#if visible}
	<div
		class="route-panel"
		role="dialog"
		aria-modal="true"
		aria-label="Plan de ruta"
		transition:fade={{ duration: 200 }}
	>
		<div class="route-panel__handle" aria-hidden="true"></div>

		<div class="route-panel__header">
			<div class="route-panel__header-left">
				<span class="route-panel__label">Ruta de pickeo</span>
				<div class="route-panel__badges">
					{#if ruta.provisional}
						<span class="route-panel__badge route-panel__badge--provisional">provisional</span>
					{/if}
					<span class="route-panel__badge route-panel__badge--algo">{ruta.algoritmo}</span>
					<span class="route-panel__badge route-panel__badge--dist">{ruta.distancia_total}m</span>
				</div>
			</div>
			<button type="button" class="route-panel__close" onclick={onClose} aria-label="Cerrar ruta">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			</button>
		</div>

		{#if siguiente}
			<div class="route-panel__hero">
				<div class="route-panel__hero-badge">Siguiente parada</div>
				<p class="route-panel__hero-desc">{siguiente.descripcion}</p>
				<div class="route-panel__hero-meta">
					<span class="route-panel__hero-ubicacion">{siguiente.ubicacion_hablada}</span>
					<span class="route-panel__hero-qty">
						{siguiente.cantidad_pedida - siguiente.cantidad_pickeada} unid.
					</span>
				</div>
				<code class="route-panel__hero-qr">{siguiente.ubicacion_qr}</code>
			</div>
		{/if}

		{#if resto.length > 0}
			<div class="route-panel__rest-header">
				<span class="route-panel__rest-label">Paradas restantes</span>
			</div>
			<ol class="route-panel__rest-list" role="list">
				{#each resto as parada (parada.remito_item_id)}
					<li class="rest-row">
						<span class="rest-row__num">{parada.orden}</span>
						<span class="rest-row__body">
							<span class="rest-row__desc">{parada.descripcion}</span>
							<span class="rest-row__ubicacion">{parada.ubicacion_hablada}</span>
						</span>
						<span class="rest-row__qty">
							{parada.cantidad_pedida - parada.cantidad_pickeada}
						</span>
					</li>
				{/each}
			</ol>
		{/if}
	</div>
{/if}

<style>
	.route-panel {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 50;
		background-color: #ffffff;
		border-top: 1.5px solid #e2e8f0;
		border-radius: 1rem 1rem 0 0;
		padding: 0.5rem 1rem 2rem;
		max-height: 72vh;
		overflow-y: auto;
		overscroll-behavior: contain;
		box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.12);
	}

	.route-panel__handle {
		width: 2.5rem;
		height: 4px;
		background-color: #cbd5e1;
		border-radius: 9999px;
		margin: 0.5rem auto 1rem;
	}

	.route-panel__header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.875rem;
	}

	.route-panel__header-left {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.route-panel__label {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
	}

	.route-panel__badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	.route-panel__badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		border-radius: 9999px;
	}

	.route-panel__badge--provisional {
		color: #92400e;
		background-color: #fef3c7;
	}

	.route-panel__badge--algo {
		color: #1e40af;
		background-color: #dbeafe;
	}

	.route-panel__badge--dist {
		color: #334155;
		background-color: #f1f5f9;
	}

	.route-panel__close {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		color: #64748b;
		background: none;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		padding: 0;
	}

	.route-panel__close svg {
		width: 1.25rem;
		height: 1.25rem;
	}

	.route-panel__close:active {
		background-color: #f1f5f9;
	}

	/* ── Hero: next stop ── */
	.route-panel__hero {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		background-color: #eff6ff;
		border: 2px solid #2563eb;
		border-radius: 0.75rem;
		margin-bottom: 1rem;
	}

	.route-panel__hero-badge {
		align-self: flex-start;
		padding: 0.1875rem 0.625rem;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #ffffff;
		background-color: #2563eb;
		border-radius: 9999px;
	}

	.route-panel__hero-desc {
		font-size: 1.125rem;
		font-weight: 700;
		color: #0f172a;
		line-height: 1.3;
		margin: 0;
	}

	.route-panel__hero-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.route-panel__hero-ubicacion {
		font-size: 0.9375rem;
		font-weight: 600;
		color: #1d4ed8;
	}

	.route-panel__hero-qty {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
		background-color: #dbeafe;
		padding: 0.125rem 0.625rem;
		border-radius: 9999px;
	}

	.route-panel__hero-qr {
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
		font-size: 0.8125rem;
		color: #64748b;
		letter-spacing: 0.02em;
	}

	/* ── Rest of the route ── */
	.route-panel__rest-header {
		margin-bottom: 0.5rem;
	}

	.route-panel__rest-label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #64748b;
	}

	.route-panel__rest-list {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.rest-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.625rem 0.75rem;
		background-color: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 0.5rem;
	}

	.rest-row__num {
		flex-shrink: 0;
		width: 1.5rem;
		height: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.75rem;
		font-weight: 700;
		color: #334155;
		background-color: #e2e8f0;
		border-radius: 50%;
	}

	.rest-row__body {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.rest-row__desc {
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.rest-row__ubicacion {
		font-size: 0.75rem;
		color: #94a3b8;
	}

	.rest-row__qty {
		flex-shrink: 0;
		font-size: 0.9375rem;
		font-weight: 700;
		color: #334155;
	}
</style>
