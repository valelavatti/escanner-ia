<script lang="ts">
	import { tick } from 'svelte';
	import type { Ubicacion } from '$lib/api/client';

	interface Props {
		selectedUbicacion: Ubicacion;
		onClose: () => void;
		onAssign: () => void;
		onChange: () => void;
		onUnassign: () => void;
		loadingAction?: 'assign' | 'change' | 'unassign' | null;
		actionError?: string | null;
	}

	let {
		selectedUbicacion,
		onClose,
		onAssign,
		onChange,
		onUnassign,
		loadingAction = null,
		actionError = null
	}: Props = $props();
	let visible = $state(false);

	const isSuelto = $derived(selectedUbicacion.estante_nombre.toLowerCase().startsWith('suelto'));
	const isEmpty = $derived(
		!isSuelto && !selectedUbicacion.producto_id && !selectedUbicacion.producto_sku
	);

	$effect(() => {
		if (selectedUbicacion) {
			tick().then(() => {
				visible = true;
			});
		}
	});
</script>

<div class="detail-panel" class:detail-panel--visible={visible} role="dialog" aria-modal="true" aria-label="Detalle de ubicación">
	<button
		type="button"
		class="detail-panel__close"
		onclick={onClose}
		aria-label="Cerrar panel"
	>
		✕
	</button>

	{#if isSuelto}
		<h3 class="detail-panel__title">Productos sueltos (sin ubicación física)</h3>
		<p class="detail-panel__text">
			Los productos sueltos se cargan desde el escáner sin QR de sector. El stock se acumula vía
			movimientos.
		</p>
	{:else}
		<h3 class="detail-panel__title">
			{selectedUbicacion.estante_nombre} — {selectedUbicacion.qr_valor}
		</h3>
		<div class="detail-panel__coords">
			Fila {selectedUbicacion.fila} · Columna {selectedUbicacion.columna}
		</div>

		{#if selectedUbicacion.producto_sku}
			<div class="detail-panel__product">
				<span class="detail-panel__sku">{selectedUbicacion.producto_sku}</span>
				<span class="detail-panel__desc">{selectedUbicacion.producto_descripcion}</span>
				<div class="detail-panel__stock">
					Stock actual: {selectedUbicacion.stock_actual}
				</div>
			</div>
			<div class="detail-panel__actions">
				<button
					type="button"
					class="button button--primary"
					onclick={onChange}
					disabled={loadingAction === 'change'}
				>
					{loadingAction === 'change' ? 'Cambiando...' : 'Cambiar producto'}
				</button>
				<button
					type="button"
					class="button button--danger-outline"
					onclick={onUnassign}
					disabled={loadingAction === 'unassign'}
				>
					{loadingAction === 'unassign' ? 'Desasignando...' : 'Desasignar'}
				</button>
			</div>
			{#if actionError}
				<p class="detail-panel__error" role="alert">{actionError}</p>
			{/if}
		{:else}
			<div class="detail-panel__empty">
				<span class="detail-panel__empty-icon">⬜</span>
				<span>Ubicación vacía</span>
			</div>
			<div class="detail-panel__actions">
				<button
					type="button"
					class="button button--primary"
					onclick={onAssign}
					disabled={loadingAction === 'assign'}
				>
					{loadingAction === 'assign' ? 'Asignando...' : 'Asignar producto'}
				</button>
			</div>
			{#if actionError}
				<p class="detail-panel__error" role="alert">{actionError}</p>
			{/if}
		{/if}
	{/if}
</div>

<style>
	.detail-panel {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 50;
		background-color: #ffffff;
		border-top-left-radius: 1rem;
		border-top-right-radius: 1rem;
		box-shadow: 0 -4px 20px rgba(15, 23, 42, 0.15);
		padding: 1rem;
		padding-bottom: max(1rem, env(safe-area-inset-bottom));
		max-height: 60vh;
		overflow-y: auto;
		transform: translateY(100%);
		transition: transform 0.25s ease-out;
	}

	.detail-panel--visible {
		transform: translateY(0);
	}

	.detail-panel__close {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.75rem;
		height: 2.75rem;
		font-size: 1.25rem;
		line-height: 1;
		color: #64748b;
		background-color: transparent;
		border: none;
		border-radius: 0.375rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.detail-panel__close:active {
		background-color: #f1f5f9;
	}

	.detail-panel__title {
		margin: 0 2.5rem 0.25rem 0;
		font-size: 1.125rem;
		font-weight: 700;
		color: #0f172a;
	}

	.detail-panel__coords {
		margin-bottom: 1rem;
		font-size: 0.875rem;
		color: #64748b;
	}

	.detail-panel__text {
		margin: 0;
		font-size: 0.9375rem;
		line-height: 1.6;
		color: #334155;
	}

	.detail-panel__product {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem;
		background-color: #f0fdf4;
		border: 1px solid #bbf7d0;
		border-radius: 0.5rem;
	}

	.detail-panel__sku {
		font-size: 1rem;
		font-weight: 700;
		color: #14532d;
	}

	.detail-panel__desc {
		font-size: 0.9375rem;
		color: #166534;
	}

	.detail-panel__stock {
		margin-top: 0.25rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #15803d;
	}

	.detail-panel__empty {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem;
		background-color: #f8fafc;
		border: 1px dashed #cbd5e1;
		border-radius: 0.5rem;
		font-size: 0.9375rem;
		color: #475569;
	}

	.detail-panel__empty-icon {
		font-size: 1.25rem;
		line-height: 1;
	}

	.detail-panel__actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 1rem;
	}

	.detail-panel__error {
		margin: 0.75rem 0 0;
		padding: 0.625rem 0.75rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: #991b1b;
		background-color: #fee2e2;
		border-radius: 0.5rem;
	}

	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1.25rem;
		font-size: 1rem;
		font-weight: 600;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
		transition: opacity 0.15s ease;
	}

	.button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.button--primary {
		color: #ffffff;
		background-color: #2563eb;
		border: 1px solid #2563eb;
	}

	.button--danger-outline {
		color: #dc2626;
		background-color: #ffffff;
		border: 1px solid #dc2626;
	}

	@media (min-width: 768px) {
		.detail-panel {
			left: auto;
			right: 1rem;
			bottom: 1rem;
			width: 22rem;
			max-height: calc(100vh - 2rem);
			border-radius: 0.75rem;
			border-top-left-radius: 0.75rem;
			border-top-right-radius: 0.75rem;
			box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
		}
	}
</style>
