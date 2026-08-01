<script lang="ts">
	import type { RemitoItemState, RoutePlan } from '$lib/api/client';

	interface Props {
		items: RemitoItemState[];
		ruta: RoutePlan | null;
	}

	let { items, ruta }: Props = $props();

	// derive the sku of the next recommended stop from the route
	const nextSku = $derived(
		ruta?.paradas.find((p) => p.es_siguiente)?.sku ?? null
	);
</script>

<div class="item-list">
	<div class="item-list__header">
		<span class="item-list__title">Artículos</span>
		<span class="item-list__progress">
			{items.filter((i) => i.completado).length}/{items.length}
		</span>
	</div>

	{#if items.length === 0}
		<div class="item-list__empty" role="status">Sin artículos cargados.</div>
	{:else}
		<ul class="item-list__list" role="list">
			{#each items as item (item.remito_item_id)}
				{@const isSiguiente = item.sku === nextSku && !item.completado}
				<li
					class="item-row"
					class:item-row--completado={item.completado}
					class:item-row--siguiente={isSiguiente}
					aria-label="{item.sku} {item.completado ? 'completado' : isSiguiente ? 'siguiente' : 'pendiente'}"
				>
					<span class="item-row__status" aria-hidden="true">
						{#if item.completado}
							<svg class="item-row__check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
								<polyline points="20 6 9 17 4 12"></polyline>
							</svg>
						{:else if isSiguiente}
							<span class="item-row__next-dot"></span>
						{:else}
							<span class="item-row__pending-dot"></span>
						{/if}
					</span>

					<span class="item-row__body">
						<span class="item-row__desc">{item.descripcion}</span>
						<span class="item-row__meta">
							<span class="item-row__sku">{item.sku}</span>
							<span class="item-row__sep" aria-hidden="true">·</span>
							<span class="item-row__ubicacion">{item.ubicacion_hablada}</span>
						</span>
					</span>

					<span class="item-row__qty" class:item-row__qty--done={item.completado}>
						{item.cantidad_pickeada}/{item.cantidad_pedida}
					</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.item-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.item-list__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 0.25rem;
	}

	.item-list__title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #64748b;
	}

	.item-list__progress {
		font-size: 0.875rem;
		font-weight: 700;
		color: #2563eb;
	}

	.item-list__empty {
		padding: 1rem;
		font-size: 0.9375rem;
		color: #64748b;
		text-align: center;
		background-color: #f8fafc;
		border-radius: 0.5rem;
	}

	.item-list__list {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.item-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.625rem 0.875rem;
		background-color: #ffffff;
		border: 1.5px solid #e2e8f0;
		border-radius: 0.625rem;
		transition: border-color 0.15s ease, background-color 0.15s ease;
	}

	.item-row--siguiente {
		border-color: #2563eb;
		background-color: #eff6ff;
	}

	.item-row--completado {
		background-color: #f0fdf4;
		border-color: #bbf7d0;
		opacity: 0.72;
	}

	.item-row__status {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
	}

	.item-row__check {
		width: 1.25rem;
		height: 1.25rem;
		color: #16a34a;
	}

	.item-row__next-dot {
		width: 0.625rem;
		height: 0.625rem;
		border-radius: 50%;
		background-color: #2563eb;
		box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
	}

	.item-row__pending-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background-color: #cbd5e1;
	}

	.item-row__body {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.item-row__desc {
		font-size: 0.9375rem;
		font-weight: 600;
		line-height: 1.3;
		color: #0f172a;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.item-row--completado .item-row__desc {
		text-decoration: line-through;
		color: #64748b;
	}

	.item-row__meta {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		flex-wrap: wrap;
	}

	.item-row__sku {
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
		font-size: 0.75rem;
		color: #94a3b8;
	}

	.item-row__sep {
		color: #cbd5e1;
		font-size: 0.75rem;
	}

	.item-row__ubicacion {
		font-size: 0.75rem;
		color: #64748b;
		font-weight: 500;
	}

	.item-row--siguiente .item-row__ubicacion {
		color: #1d4ed8;
		font-weight: 600;
	}

	.item-row__qty {
		flex-shrink: 0;
		font-size: 1rem;
		font-weight: 700;
		color: #334155;
	}

	.item-row__qty--done {
		color: #16a34a;
	}
</style>
