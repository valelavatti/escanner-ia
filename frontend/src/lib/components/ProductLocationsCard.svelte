<script lang="ts">
	import type { ProductoUbicacionItem } from '$lib/api/client';

	interface ProductHeader {
		sku: string;
		descripcion: string;
		stock_total: number;
	}

	interface Props {
		product: ProductHeader;
		locations: ProductoUbicacionItem[];
		loading?: boolean;
		onSelectLocation: (location: ProductoUbicacionItem) => void;
		onCancel: () => void;
	}

	let {
		product,
		locations,
		loading = false,
		onSelectLocation,
		onCancel
	}: Props = $props();

	const hasLocations = $derived(locations.length > 0);
</script>

<div class="locations-card">
	<div class="locations-card__header">
		<div class="locations-card__sku">{product.sku}</div>
		{#if hasLocations}
			<span class="locations-card__badge">Stock total: {product.stock_total}</span>
		{/if}
	</div>

	<div class="locations-card__desc">{product.descripcion}</div>

	{#if loading}
		<div class="locations-card__empty" role="status">Buscando ubicaciones…</div>
	{:else if hasLocations}
		<ul class="locations-card__list" role="list">
			{#each locations as loc (loc.ubicacion_id)}
				<li>
					<button
						type="button"
						class="location-row"
						class:location-row--zero={loc.stock === 0}
						onclick={() => onSelectLocation(loc)}
					>
						<span class="location-row__main">
							<span class="location-row__estante">{loc.estante_nombre}</span>
							{#if loc.estante_nombre === 'Suelto'}
								<span class="location-row__pill">Suelto</span>
							{:else}
								<span class="location-row__tag">F{loc.fila_label}-C{loc.columna_label}</span>
							{/if}
							<span class="location-row__qr">{loc.qr_valor}</span>
							<span class="location-row__deposito">{loc.deposito_nombre}</span>
						</span>
						<span class="location-row__stock" class:location-row__stock--zero={loc.stock === 0}>
							{loc.stock}
						</span>
					</button>
				</li>
			{/each}
		</ul>
	{:else}
		<div class="locations-card__empty" role="status">
			No está en ninguna ubicación. Escaneá un QR de sector para asignarlo.
		</div>
	{/if}

	<div class="locations-card__actions">
		<button type="button" class="locations-card__cancel" onclick={onCancel}>
			Cancelar
		</button>
	</div>
</div>

<style>
	.locations-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background-color: #f0fdf4;
		border: 2px solid #bbf7d0;
		border-radius: 0.75rem;
	}

	.locations-card__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.locations-card__sku {
		font-size: 1.125rem;
		font-weight: 800;
		color: #15803d;
		word-break: break-all;
	}

	.locations-card__badge {
		flex-shrink: 0;
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		color: #ffffff;
		background-color: #16a34a;
		border-radius: 9999px;
	}

	.locations-card__desc {
		font-size: 1rem;
		font-weight: 600;
		line-height: 1.4;
		color: #0f172a;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.locations-card__list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.location-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		width: 100%;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		text-align: left;
		color: #0f172a;
		background-color: #ffffff;
		border: 2px solid #bbf7d0;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.location-row:active {
		background-color: #f0fdf4;
	}

	.location-row--zero {
		border-color: #e2e8f0;
		background-color: #f8fafc;
		color: #64748b;
	}

	.location-row__main {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		flex: 1 1 auto;
		min-width: 0;
	}

	.location-row__estante {
		font-size: 1rem;
		font-weight: 700;
		color: #15803d;
	}

	.location-row--zero .location-row__estante {
		color: #64748b;
	}

	.location-row__pill {
		display: inline-block;
		align-self: flex-start;
		padding: 0.125rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		color: #ffffff;
		background-color: #2563eb;
		border-radius: 9999px;
	}

	.location-row__tag {
		align-self: flex-start;
		padding: 0.125rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: #1e40af;
		background-color: #dbeafe;
		border-radius: 0.25rem;
	}

	.location-row__qr {
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
		font-size: 0.875rem;
		color: #475569;
		word-break: break-all;
	}

	.location-row__deposito {
		font-size: 0.8125rem;
		font-weight: 600;
		color: #64748b;
	}

	.location-row__stock {
		flex-shrink: 0;
		font-size: 1.5rem;
		font-weight: 800;
		color: #15803d;
	}

	.location-row__stock--zero {
		color: #94a3b8;
	}

	.locations-card__empty {
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		line-height: 1.4;
		text-align: center;
		color: #92400e;
		background-color: #fef3c7;
		border: 1px solid #fcd34d;
		border-radius: 0.5rem;
	}

	.locations-card__actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	.locations-card__cancel {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 700;
		color: #334155;
		background-color: #f1f5f9;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	@media (min-width: 640px) {
		.locations-card__actions {
			grid-template-columns: repeat(2, 1fr);
		}

		.locations-card__cancel {
			grid-column: 2;
		}
	}
</style>
