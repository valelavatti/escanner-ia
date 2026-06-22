<script lang="ts">
	import StockInput from './StockInput.svelte';
	import type { ProductWithUbicacionStock } from '$lib/api/client';

	interface Props {
		product: ProductWithUbicacionStock;
		quantity: number;
		mode: 'alta' | 'ajuste';
		isSaving: boolean;
		onQuantityChange: (value: number) => void;
		onModeChange: (mode: 'alta' | 'ajuste') => void;
		onSave: () => void;
		onClose: () => void;
	}

	let { product, quantity, mode, isSaving, onQuantityChange, onModeChange, onSave, onClose }: Props =
		$props();

	const currentStock = $derived(product.ubicacion_stock?.stock_actual ?? 0);
	const isAssigned = $derived(product.ubicacion_stock?.is_assigned ?? false);
</script>

<div class="product-card">
	<div class="product-card__header">
		<div class="product-card__sku">{product.sku}</div>
		{#if !isAssigned}
			<span class="product-card__badge">Nuevo en esta ubicación</span>
		{/if}
	</div>

	<div class="product-card__desc">{product.descripcion}</div>

	<div class="product-card__stock" class:product-card__stock--new={!isAssigned}>
		Stock actual: {currentStock}
	</div>

	<StockInput
		{quantity}
		{mode}
		{currentStock}
		{isSaving}
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
</style>
