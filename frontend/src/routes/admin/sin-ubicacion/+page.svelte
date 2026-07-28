<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { sessionStore } from '$lib/stores/session';
	import {
		getStockSinUbicacion,
		ApiError,
		type StockSinUbicacionListItem
	} from '$lib/api/client';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------
	let items = $state<StockSinUbicacionListItem[]>([]);
	let loading = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	// Defense-in-depth: the admin layout already redirects non-admins at
	// ``/admin/+layout.svelte`` (``canAccessAdmin`` covers deposito-admins).
	// This per-page guard narrows further: deposito-admins (who CAN reach the
	// admin root) are kicked back to ``/admin/estantes`` since the sin-ubicacion
	// endpoint is guarded by ``require_admin`` (global-admin only) on the
	// backend. Avoids the 403 round trip when a deposito-admin guesses the URL.
	$effect(() => {
		if ($sessionStore && !$sessionStore.usuario.is_admin) {
			goto('/admin/estantes');
		}
	});

	onMount(() => {
		loadItems();
	});

	// ---------------------------------------------------------------------------
	// Helpers
	// ---------------------------------------------------------------------------
	function showMessage(text: string, type: 'success' | 'error' = 'success') {
		message = { text, type };
		setTimeout(() => {
			message = null;
		}, 5000);
	}

	async function loadItems() {
		loading = true;
		try {
			items = await getStockSinUbicacion();
		} catch (err) {
			if (err instanceof ApiError && err.status === 403) {
				showMessage('Sólo los administradores globales pueden ver el stock sin ubicación', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al cargar el stock sin ubicación', 'error');
			}
		} finally {
			loading = false;
		}
	}

	function formatUpdatedAt(ts: string | null): string {
		if (!ts) return '—';
		try {
			const d = new Date(ts);
			if (Number.isNaN(d.getTime())) return ts;
			return d.toLocaleString();
		} catch {
			return ts;
		}
	}

	const totalUnits = $derived(items.reduce((sum, i) => sum + (i.cantidad ?? 0), 0));
</script>

<section class="sin-ubicacion-page">
	<header class="page-header">
		<h1>Sin ubicación</h1>
		{#if items.length > 0}
			<span class="summary">
				{items.length} producto{items.length === 1 ? '' : 's'} · {totalUnits} unidad{totalUnits === 1 ? '' : 'es'} en el bucket
			</span>
		{/if}
	</header>

	<p class="page-hint">
		Unidades que fueron liberadas de una ubicación física y están pendientes de
		reasignación. Para reubicarlas, escaneá un QR de sector con el producto
		seleccionado en el escáner — el flujo de asignación drena el bucket primero.
	</p>

	{#if message}
		<div class="alert alert--{message.type}" role="alert">
			{message.text}
		</div>
	{/if}

	{#if loading && items.length === 0}
		<p class="loading">Cargando…</p>
	{:else if items.length === 0}
		<p class="empty">No hay unidades pendientes de reasignación.</p>
	{:else}
		<ul class="bucket-list">
			{#each items as item (item.producto_sku)}
				<li class="bucket-card">
					<div class="bucket-card__header">
						<h2 class="bucket-card__sku">{item.producto_sku}</h2>
						<span class="bucket-card__qty">{item.cantidad}</span>
					</div>
					{#if item.producto_descripcion}
						<div class="bucket-card__desc">{item.producto_descripcion}</div>
					{/if}
					<div class="bucket-card__meta">
						Actualizado: {formatUpdatedAt(item.updated_at)}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.sin-ubicacion-page {
		padding: 0 0 2rem;
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
	}

	.summary {
		font-size: 0.875rem;
		font-weight: 600;
		color: #475569;
	}

	.page-hint {
		margin: 0 0 1rem;
		font-size: 0.875rem;
		line-height: 1.4;
		color: #475569;
	}

	h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	.alert {
		margin-bottom: 1rem;
		padding: 1rem;
		border-radius: 0.5rem;
		font-weight: 500;
	}

	.alert--success {
		background-color: #dcfce7;
		color: #166534;
	}

	.alert--error {
		background-color: #fee2e2;
		color: #991b1b;
	}

	.loading,
	.empty {
		color: #64748b;
		padding: 1rem 0;
	}

	.bucket-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	/* Each bucket card mirrors ProductLocationsCard's
	   ``location-row--sin-ubicacion`` amber palette + dashed border so the
	   visual language for "stock exists but has no physical home yet" is
	   consistent across the scanner UX and the admin listing. */
	.bucket-card {
		padding: 1rem;
		background-color: #fffbeb;
		border: 2px dashed #f59e0b;
		border-radius: 0.75rem;
	}

	.bucket-card__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
	}

	.bucket-card__sku {
		font-size: 1.125rem;
		font-weight: 700;
		color: #b45309;
		margin: 0;
		word-break: break-all;
	}

	.bucket-card__qty {
		flex-shrink: 0;
		padding: 0.25rem 0.75rem;
		font-size: 1.25rem;
		font-weight: 800;
		color: #ffffff;
		background-color: #b45309;
		border-radius: 9999px;
	}

	.bucket-card__desc {
		font-size: 1rem;
		font-weight: 600;
		color: #0f172a;
		line-height: 1.4;
		margin-bottom: 0.5rem;
	}

	.bucket-card__meta {
		font-size: 0.8125rem;
		font-weight: 600;
		color: #92400e;
	}

	@media (min-width: 640px) {
		.page-header {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
</style>