<script lang="ts">
	import StockInput from './StockInput.svelte';
	import type { ProductWithUbicacionStock } from '$lib/api/client';

	interface Props {
		product: ProductWithUbicacionStock;
		stockTotal: number;
		bucketQty?: number;
		quantity: number;
		mode: 'alta' | 'ajuste';
		isSaving: boolean;
		onQuantityChange: (value: number) => void;
		onModeChange: (mode: 'alta' | 'ajuste') => void;
		onSave: () => void;
		onClose: () => void;
	}

	let {
		product,
		stockTotal,
		bucketQty = 0,
		quantity,
		mode,
		isSaving,
		onQuantityChange,
		onModeChange,
		onSave,
		onClose
	}: Props = $props();

	const currentStock = $derived(product.ubicacion_stock?.stock_actual ?? 0);
	const isAssigned = $derived(product.ubicacion_stock?.is_assigned ?? false);
	const existingProductoSku = $derived(product.ubicacion_stock?.existing_producto_sku ?? null);
	const existingProductoStock = $derived(product.ubicacion_stock?.existing_producto_stock ?? null);
	const showStockGeneral = $derived(stockTotal > currentStock);

	// A destructive reassignment only happens when the location holds units of
	// another product; in that case the user must explicitly confirm.
	const needsReassignConfirm = $derived(
		existingProductoSku !== null && (existingProductoStock ?? 0) > 0
	);

	let confirmReassign = $state(false);

	// Reset the confirmation whenever a different product (or conflict) is scanned.
	$effect(() => {
		product.sku;
		existingProductoSku;
		confirmReassign = false;
	});

	const saveDisabled = $derived(needsReassignConfirm && !confirmReassign);
</script>

<div class="product-card">
	<div class="product-card__header">
		<div class="product-card__sku">{product.sku}</div>
		{#if !isAssigned}
			<span class="product-card__badge">Nuevo en esta ubicación</span>
		{/if}
	</div>

	<div class="product-card__desc">{product.descripcion}</div>

	{#if existingProductoSku}
		<div class="product-card__warning" role="alert">
			{#if (existingProductoStock ?? 0) > 0}
				⚠️ Esta ubicación ya tiene otro producto: <strong>{existingProductoSku}</strong>
				con <strong>{existingProductoStock}</strong> unidades. Al guardar, esas unidades se
				reasignarán a 'Sin ubicación' (se conservan en el producto) y esta ubicación
				arrancará desde 0 con el nuevo producto.
			{:else}
				⚠️ Esta ubicación ya tiene otro producto: <strong>{existingProductoSku}</strong>.
				Al guardar, se reasignará al nuevo producto.
			{/if}
		</div>
	{/if}

	{#if needsReassignConfirm}
		<label class="product-card__confirm">
			<input type="checkbox" bind:checked={confirmReassign} />
			<span>
				Entiendo que se moverán {existingProductoStock} unidades de
				{existingProductoSku} a 'Sin ubicación'
			</span>
		</label>
	{/if}

	<div class="product-card__stock" class:product-card__stock--new={!isAssigned}>
		Stock actual: {currentStock}
	</div>

	{#if bucketQty > 0}
		<div class="product-card__stock product-card__stock--sin-ubicacion">
			Sin ubicación: {bucketQty} unidades
		</div>
	{/if}

	{#if showStockGeneral}
		<div class="product-card__stock product-card__stock--general">
			Stock general: {stockTotal}
		</div>
	{/if}

	<StockInput
		{quantity}
		{mode}
		{currentStock}
		{stockTotal}
		{isSaving}
		{saveDisabled}
		{onQuantityChange}
		{onModeChange}
		{onSave}
		{onClose}
	/>
</div>

<style>
	.product-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background-color: #f0fdf4;
		border: 2px solid #bbf7d0;
		border-radius: 0.75rem;
	}

	.product-card__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.product-card__sku {
		font-size: 1.125rem;
		font-weight: 800;
		color: #15803d;
		word-break: break-all;
	}

	.product-card__badge {
		flex-shrink: 0;
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		color: #ffffff;
		background-color: #2563eb;
		border-radius: 9999px;
	}

	.product-card__desc {
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

	.product-card__stock {
		padding: 0.5rem 0.75rem;
		font-size: 1rem;
		font-weight: 700;
		text-align: center;
		color: #0f172a;
		background-color: #dcfce7;
		border-radius: 0.5rem;
	}

	.product-card__stock--new {
		color: #1e40af;
		background-color: #dbeafe;
	}

	.product-card__stock--general {
		color: #4b5563;
		background-color: #f3f4f6;
	}

	/* Sin-ubicacion bucket row (slice 6 / FE Point 2): renders alongside the
	   other stock rows whenever the scanned product has units in the bucket.
	   Uses the same dashed amber palette as ProductLocationsCard's
	   ``location-row--sin-ubicacion`` so the "stock exists but has no physical
	   home yet" visual language is consistent across the scanner UX. */
	.product-card__stock--sin-ubicacion {
		color: #b45309;
		background-color: #fffbeb;
		border: 2px dashed #f59e0b;
	}

	.product-card__warning {
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		line-height: 1.4;
		color: #92400e;
		background-color: #fef3c7;
		border: 1px solid #fcd34d;
		border-radius: 0.5rem;
	}

	.product-card__confirm {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		line-height: 1.4;
		color: #92400e;
		background-color: #fef3c7;
		border: 1px solid #fcd34d;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.product-card__confirm input {
		flex-shrink: 0;
		width: 1.25rem;
		height: 1.25rem;
		margin: 0;
		accent-color: #b45309;
		cursor: pointer;
	}
</style>
