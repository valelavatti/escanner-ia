<script lang="ts">
	import type { Ubicacion } from '$lib/api/client';

	interface Props {
		ubicacion: Ubicacion;
		isSelected?: boolean;
		onClick?: (ubicacion: Ubicacion) => void;
	}

	let { ubicacion, isSelected = false, onClick }: Props = $props();

	const LOW_STOCK_THRESHOLD = 10;

	const isSuelto = $derived(ubicacion.estante_nombre.toLowerCase().startsWith('suelto'));
	const isOccupied = $derived(
		(!!ubicacion.producto_id || !!ubicacion.producto_sku) && ubicacion.stock_actual > 0
	);
	const isLowStock = $derived(
		(!!ubicacion.producto_id || !!ubicacion.producto_sku) &&
			ubicacion.stock_actual > 0 &&
			ubicacion.stock_actual < LOW_STOCK_THRESHOLD
	);
	const isEmpty = $derived(!ubicacion.producto_id && !ubicacion.producto_sku);

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			onClick?.(ubicacion);
		}
	}
</script>

<div
	class="cell"
	class:cell--occupied={isOccupied}
	class:cell--empty={isEmpty}
	class:cell--low-stock={isLowStock}
	class:cell--suelto={isSuelto}
	class:cell--selected={isSelected}
	onclick={() => onClick?.(ubicacion)}
	onkeydown={handleKeyDown}
	role="button"
	tabindex="0"
	aria-label={`Ubicación ${ubicacion.qr_valor}${ubicacion.producto_sku ? `, ${ubicacion.producto_sku}, stock ${ubicacion.stock_actual}` : ', vacía'}`}
	title={ubicacion.qr_valor}
>
	<span class="cell__coords">{ubicacion.fila}-{ubicacion.columna}</span>
	<span class="cell__qr">{ubicacion.qr_valor}</span>
	{#if ubicacion.producto_sku}
		<span class="cell__sku">{ubicacion.producto_sku}</span>
		<span class="cell__stock">{ubicacion.stock_actual}</span>
	{/if}
</div>

<style>
	.cell {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-width: 48px;
		min-height: 48px;
		padding: 0.125rem;
		font-size: 0.625rem;
		line-height: 1.1;
		text-align: center;
		border: 1px solid #e2e8f0;
		border-radius: 0.375rem;
		background-color: #f1f5f9;
		color: #64748b;
		cursor: pointer;
		touch-action: manipulation;
		user-select: none;
		overflow: hidden;
	}

	.cell--occupied {
		background-color: #dcfce7;
		border-color: #bbf7d0;
		color: #14532d;
	}

	.cell--empty {
		background-color: #f1f5f9;
		border-color: #e2e8f0;
		color: #64748b;
	}

	.cell--low-stock {
		background-color: #fef3c7;
		border-color: #fcd34d;
		color: #78350f;
	}

	.cell--suelto {
		background-color: #dbeafe;
		border-color: #93c5fd;
		color: #1e3a8a;
	}

	.cell--selected {
		position: relative;
		z-index: 1;
		border: 3px solid #2563eb;
		transform: scale(1.05);
		box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
	}

	.cell__coords,
	.cell__qr,
	.cell__sku,
	.cell__stock {
		display: block;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cell__coords {
		font-weight: 700;
	}

	.cell__qr {
		opacity: 0.85;
	}
</style>
