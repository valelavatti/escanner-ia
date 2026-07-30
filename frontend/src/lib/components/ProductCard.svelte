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
		onSave: (drainQty: number) => void;
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

	// Slice 8 — explicit "Utilizar unidades 'sin ubicación'" Feature state.
	// Visible only when the scanned product has bucket qty > 0 AND the user
	// is entering an `alta` (only alta adds ubicacion stock — ajuste replaces
	// it). useBucket toggles the checkbox; drainAmount is the qty the user
	// wants to rescue from the bucket into the ubicacion. Capped by both
	// bucket availability and the entered alta cantidad via `canDrain`.
	let useBucket = $state(false);
	let drainAmount = $state(0);

	// Reset the confirmation + drain state whenever a different product (or
	// conflict) is scanned, OR when the mode flips away from `alta`. The
	// debounce via $effect on the reactive identifiers keeps the UI honest.
	$effect(() => {
		product.sku;
		existingProductoSku;
		mode;
		confirmReassign = false;
		useBucket = false;
		drainAmount = 0;
	});

	const saveDisabled = $derived(needsReassignConfirm && !confirmReassign);

	// Slice 8 — show the drain block only when there ARE bucket units for
	// this product AND the user is in `alta` mode (ajuste replaces
	// absolute; draining the bucket into an adjusted cell would conflate
	// the alta/ajuste delta semantics). The input max is the min of the
	// bucket availability and the alta cantidad the user just entered
	// (the backend rejects drain > cantidad with HTTP 400 — we expose the
	// ceiling so the FE input never lets the user transmit an invalid
	// request in the first place).
	const showDrainBlock = $derived(bucketQty > 0 && mode === 'alta');
	const drainMax = $derived(Math.min(bucketQty, Math.max(quantity, 0)));
	const canDrain = $derived(
		useBucket && drainAmount > 0 && drainAmount <= bucketQty && drainAmount <= quantity
	);
	// Defensive clamp for display: when the user types a value outside the
	// [0, drainMax] range the browser's `max` attribute alone does not
	// enforce the bound (it only marks the input as invalid), so a derived
	// value keeps the explanation copy honest. The raw `drainAmount` state
	// is what `bind:value` writes; we READ the clamped form below without
	// mutating state from an `$effect` (which would risk a Svelte 5
	// effect-loop warning). `canDrain` gate at save time protects the
	// backend independently of the display clamp.
	const drainAmountClamped = $derived(
		Number.isFinite(drainAmount)
			? Math.max(0, Math.min(drainAmount, drainMax))
			: 0
	);

	function handleSave() {
		// Slice 8 — pass the drain qty to the parent's `handleSave`; 0 when
		// the user did NOT toggle the checkbox (or when no bucket is
		// available). The backend treats 0 as the historical no-drain
		// alta path — so default behavior preserves all prior scanner UX.
		onSave(canDrain ? drainAmount : 0);
	}
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

	{#if showDrainBlock}
		<div class="product-card__drain" data-can-drain={canDrain}>
			<label class="product-card__drain-toggle">
				<input
					type="checkbox"
					bind:checked={useBucket}
					disabled={isSaving || quantity <= 0}
				/>
				<span>
					Utilizar unidades <strong>'sin ubicación'</strong>
					{#if useBucket}
						— de las {quantity} a asignar, usar
						<span class="product-card__drain-amount">
							{#if drainAmountClamped > 0 && canDrain}
								{drainAmountClamped} del bucket y {quantity - drainAmountClamped} nuevas
							{:else}
								{quantity} nuevas (sin drenaje)
							{/if}
						</span>
					{/if}
				</span>
			</label>
			{#if useBucket}
				<label class="product-card__drain-field">
					<span>Unidades a usar del bucket (máx. {drainMax})</span>
					<input
						type="number"
						min="0"
						max={drainMax}
						step="1"
						bind:value={drainAmount}
						disabled={isSaving}
						inputmode="numeric"
					/>
				</label>
				<p class="product-card__drain-explanation">
					De las {quantity} unidades a asignar, {drainAmountClamped > 0 && canDrain ? drainAmountClamped : 0} vendrán del bucket y {quantity - (drainAmountClamped > 0 && canDrain ? drainAmountClamped : 0)} se contarán como nuevas.
				</p>
			{/if}
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
		onSave={handleSave}
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

	/* Slice 8 — explicit `drain_bucket_qty` Feature UI. Mirrors the amber
	   palette of the bucket-row above so "this control talks to the same
	   stock concept" is visually obvious. The toggle grows into a
	   sub-section with a number input + a live how-the-qty-composes
	   explanation. Defensive guard: the `[data-can-drain='false']` selector
	   is kept available for future amplitude (e.g. a lament-red border on
	   invalid input); today the FE never lets drainAmount exceed drainMax
	   because the $effect clamps it, so it stays truthful. */
	.product-card__drain {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		padding: 0.75rem 1rem;
		font-size: 0.9375rem;
		font-weight: 600;
		line-height: 1.4;
		color: #92400e;
		background-color: #fffbeb;
		border: 2px dashed #f59e0b;
		border-radius: 0.5rem;
	}

	.product-card__drain-toggle {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.product-card__drain-toggle input {
		flex-shrink: 0;
		width: 1.25rem;
		height: 1.25rem;
		margin-top: 0.125rem;
		accent-color: #b45309;
		cursor: pointer;
	}

	.product-card__drain-amount {
		font-weight: 700;
	}

	.product-card__drain-field {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: #78350f;
	}

	.product-card__drain-field input {
		min-height: 2.5rem;
		padding: 0.375rem 0.5rem;
		font-size: 1rem;
		color: #0f172a;
		background-color: #ffffff;
		border: 1px solid #f59e0b;
		border-radius: 0.375rem;
	}

	.product-card__drain-explanation {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 500;
		color: #78350f;
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
