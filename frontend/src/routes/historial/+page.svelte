<script lang="ts">
	import { onMount } from 'svelte';
	import {
		listMovimientos,
		exportMovimientosCSV,
		listUsuarios,
		searchProductos,
		ApiError
	} from '$lib/api/client';
	import type { MovimientoResponse, ProductSearchResult } from '$lib/api/client';

	const PAGE_SIZE = 50;

	let movimientos = $state<MovimientoResponse[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let error = $state('');
	let offset = $state(0);

	let usuarios = $state<Array<{ id: number; nombre: string }>>([]);
	let loadingUsuarios = $state(false);

	let selectedUsuarioId = $state<number | null>(null);
	let selectedProductoSku = $state<string | null>(null);
	let selectedProductoDescripcion = $state<string>('');
	let productoQuery = $state('');
	let productoResults = $state<ProductSearchResult[]>([]);
	let searchingProducto = $state(false);
	let productoSearchTimeout: ReturnType<typeof setTimeout> | null = null;
	let showProductoResults = $state(false);

	let fromDate = $state('');
	let toDate = $state('');

	let exporting = $state(false);

	const tipoMeta: Record<string, { label: string; color: string; emoji: string }> = {
		alta: { label: 'Alta', color: '#16a34a', emoji: '🟢' },
		ajuste: { label: 'Ajuste', color: '#ca8a04', emoji: '🟡' },
		asignacion: { label: 'Asignación', color: '#2563eb', emoji: '🔵' },
		desasignacion: { label: 'Desasignación', color: '#dc2626', emoji: '🔴' }
	};

	const loadedCount = $derived(movimientos.length);
	const hasMore = $derived(loadedCount < total);

	onMount(() => {
		loadUsuarios();
		loadMovimientos(true);
	});

	async function loadUsuarios() {
		loadingUsuarios = true;
		try {
			usuarios = await listUsuarios();
		} catch {
			usuarios = [];
		} finally {
			loadingUsuarios = false;
		}
	}

	async function loadMovimientos(reset: boolean = false) {
		if (reset) {
			offset = 0;
			movimientos = [];
		}

		loading = true;
		error = '';

		try {
			const response = await listMovimientos({
				usuario_id: selectedUsuarioId ?? undefined,
				producto_sku: selectedProductoSku ?? undefined,
				from_date: fromDate || undefined,
				to_date: toDate || undefined,
				limit: PAGE_SIZE,
				offset
			});

			if (reset) {
				movimientos = response.items;
			} else {
				movimientos = [...movimientos, ...response.items];
			}
			total = response.total;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Error al cargar el historial';
		} finally {
			loading = false;
		}
	}

	function handleLoadMore() {
		offset += PAGE_SIZE;
		loadMovimientos(false);
	}

	function handleUsuarioChange(event: Event) {
		const value = (event.target as HTMLSelectElement).value;
		selectedUsuarioId = value === '' ? null : Number(value);
		loadMovimientos(true);
	}

	function handleProductoInput() {
		selectedProductoSku = null;
		selectedProductoDescripcion = '';
		showProductoResults = true;

		if (productoSearchTimeout) clearTimeout(productoSearchTimeout);
		if (productoQuery.trim().length < 2) {
			productoResults = [];
			return;
		}

		productoSearchTimeout = setTimeout(async () => {
			searchingProducto = true;
			try {
				productoResults = await searchProductos(productoQuery.trim());
			} catch {
				productoResults = [];
			} finally {
				searchingProducto = false;
			}
		}, 300);
	}

	function selectProducto(producto: ProductSearchResult) {
		selectedProductoSku = producto.sku;
		selectedProductoDescripcion = producto.descripcion;
		productoQuery = `${producto.sku} — ${producto.descripcion}`;
		showProductoResults = false;
		productoResults = [];
		loadMovimientos(true);
	}

	function clearProducto() {
		selectedProductoSku = null;
		selectedProductoDescripcion = '';
		productoQuery = '';
		productoResults = [];
		showProductoResults = false;
	}

	function handleFromDateChange(event: Event) {
		fromDate = (event.target as HTMLInputElement).value;
		loadMovimientos(true);
	}

	function handleToDateChange(event: Event) {
		toDate = (event.target as HTMLInputElement).value;
		loadMovimientos(true);
	}

	function clearFilters() {
		selectedUsuarioId = null;
		clearProducto();
		fromDate = '';
		toDate = '';
		loadMovimientos(true);
	}

	async function handleExportCSV() {
		exporting = true;
		try {
			const blob = await exportMovimientosCSV({
				usuario_id: selectedUsuarioId ?? undefined,
				producto_sku: selectedProductoSku ?? undefined,
				from_date: fromDate || undefined,
				to_date: toDate || undefined
			});

			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = `movimientos_${new Date().toISOString().slice(0, 10)}.csv`;
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			window.URL.revokeObjectURL(url);
		} catch (err) {
			const message = err instanceof Error ? err.message : 'Error al exportar CSV';
			error = message;
		} finally {
			exporting = false;
		}
	}

	function formatDateTime(iso: string): string {
		const d = new Date(iso);
		return d.toLocaleString('es-AR', {
			day: '2-digit',
			month: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function formatDescription(m: MovimientoResponse): string {
		switch (m.tipo) {
			case 'alta':
				return `+${m.cantidad} | ${m.producto_sku ?? '—'}`;
			case 'ajuste':
				return `Stock ajustado a ${m.cantidad} | ${m.producto_sku ?? '—'}`;
			case 'asignacion':
				return `Asignado: ${m.producto_sku ?? '—'}`;
			case 'desasignacion':
				return `Desasignado: ${m.producto_sku ?? '—'}`;
			default:
				return `${m.tipo}: ${m.producto_sku ?? '—'}`;
		}
	}

	function formatStockChange(m: MovimientoResponse): string | null {
		if (m.tipo === 'asignacion' || m.tipo === 'desasignacion') {
			return null;
		}
		return `Stock ubicación: ${m.stock_anterior} → ${m.stock_nuevo}`;
	}

	function formatStockGeneral(m: MovimientoResponse): string | null {
		if (!m.producto_sku || m.tipo === 'asignacion' || m.tipo === 'desasignacion') return null;
		if (m.stock_general_anterior === m.stock_general_nuevo) return null;
		return `Stock general: ${m.stock_general_anterior} → ${m.stock_general_nuevo}`;
	}

	function formatUbicacion(m: MovimientoResponse): string {
		return `${m.estante_nombre} F${m.fila_label}-C${m.columna_label} — ${m.ubicacion_qr}`;
	}
</script>

<div class="historial-page">
	<header class="historial-page__header">
		<h1>Historial</h1>
		<p class="historial-page__subtitle">Movimientos, asignaciones y desasignaciones</p>
	</header>

	<section class="historial-page__filters" aria-label="Filtros">
		<label class="filter-field">
			<span>Usuario</span>
			<select
				value={selectedUsuarioId ?? ''}
				onchange={handleUsuarioChange}
				disabled={loadingUsuarios}
			>
				<option value="">Todos</option>
				{#each usuarios as usuario}
					<option value={usuario.id}>{usuario.nombre}</option>
				{/each}
			</select>
		</label>

		<div class="filter-field filter-field--search">
			<span>Producto</span>
			<div class="producto-search">
				<input
					type="text"
					placeholder="Buscar por SKU o descripción"
					bind:value={productoQuery}
					oninput={handleProductoInput}
					autocomplete="off"
				/>
				{#if selectedProductoSku}
					<button type="button" class="producto-search__clear" onclick={clearProducto}>
						×
					</button>
				{/if}
			</div>
			{#if showProductoResults && productoQuery.trim().length >= 2}
				<div class="producto-results">
					{#if searchingProducto}
						<p class="producto-results__empty">Buscando...</p>
					{:else if productoResults.length === 0}
						<p class="producto-results__empty">Sin resultados</p>
					{:else}
						{#each productoResults as producto}
							<button
								type="button"
								class="producto-results__item"
								onclick={() => selectProducto(producto)}
							>
								<span class="producto-results__sku">{producto.sku}</span>
								<span class="producto-results__desc">{producto.descripcion}</span>
							</button>
						{/each}
					{/if}
				</div>
			{/if}
		</div>

		<label class="filter-field">
			<span>Desde</span>
			<input type="date" value={fromDate} onchange={handleFromDateChange} />
		</label>

		<label class="filter-field">
			<span>Hasta</span>
			<input type="date" value={toDate} onchange={handleToDateChange} />
		</label>

		<div class="filter-actions">
			<button
				type="button"
				class="filter-actions__export"
				onclick={handleExportCSV}
				disabled={exporting || loading}
			>
				{exporting ? 'Exportando...' : 'Exportar CSV'}
			</button>
			<button
				type="button"
				class="filter-actions__clear"
				onclick={clearFilters}
				disabled={loading}
			>
				Limpiar filtros
			</button>
		</div>
	</section>

	{#if error}
		<div class="historial-page__error" role="alert">
			{error}
		</div>
	{/if}

	<section class="historial-page__list" aria-label="Lista de movimientos">
		<div class="historial-page__count">
			{#if loading && movimientos.length === 0}
				Cargando movimientos...
			{:else}
				Mostrando {loadedCount} de {total} movimientos
			{/if}
		</div>

		{#if movimientos.length === 0 && !loading}
			<div class="historial-page__empty">
				<p>No hay movimientos para los filtros seleccionados.</p>
			</div>
		{:else}
			<ul class="movimiento-list">
				{#each movimientos as movimiento (movimiento.id)}
					{@const meta = tipoMeta[movimiento.tipo] ?? { label: movimiento.tipo, color: '#64748b', emoji: '⚪' }}
					<li class="movimiento-card">
						<div class="movimiento-card__header">
							<span class="movimiento-card__badge" style="background-color: {meta.color}">
								{meta.emoji} {meta.label}
							</span>
							<span class="movimiento-card__datetime">
								{formatDateTime(movimiento.timestamp)}
							</span>
						</div>

						<div class="movimiento-card__body">
							<p class="movimiento-card__description">
								{formatDescription(movimiento)}
							</p>
						{#if formatStockChange(movimiento)}
							<p class="movimiento-card__stock">
								{formatStockChange(movimiento)}
							</p>
						{/if}
						{#if formatStockGeneral(movimiento)}
							<p class="movimiento-card__stock-general">
								{formatStockGeneral(movimiento)}
							</p>
						{/if}
							<p class="movimiento-card__producto">
								{movimiento.producto_descripcion ?? ''}
							</p>
							<p class="movimiento-card__ubicacion">
								📍 {formatUbicacion(movimiento)}
							</p>
						</div>

						<div class="movimiento-card__footer">
							<span>{movimiento.usuario_nombre ?? '—'}</span>
						</div>
					</li>
				{/each}
			</ul>
		{/if}

		{#if hasMore}
			<button
				type="button"
				class="historial-page__load-more"
				onclick={handleLoadMore}
				disabled={loading}
			>
				{loading ? 'Cargando...' : 'Cargar más'}
			</button>
		{/if}
	</section>
</div>

<style>
	.historial-page {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem 0;
	}

	.historial-page__header h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 800;
		color: #0f172a;
	}

	.historial-page__subtitle {
		margin: 0;
		font-size: 0.875rem;
		color: #64748b;
	}

	.historial-page__filters {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
		padding: 1rem;
		background-color: #f8fafc;
		border-radius: 0.75rem;
	}

	.filter-field {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.filter-field select,
	.filter-field input[type='date'],
	.producto-search input {
		min-height: 3rem;
		padding: 0.5rem 0.75rem;
		font-size: 1rem;
		color: #0f172a;
		background-color: #ffffff;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
	}

	.producto-search {
		position: relative;
		display: flex;
		align-items: center;
	}

	.producto-search input {
		width: 100%;
		padding-right: 2.5rem;
	}

	.producto-search__clear {
		position: absolute;
		right: 0.5rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		font-size: 1.25rem;
		line-height: 1;
		color: #64748b;
		background: transparent;
		border: none;
		cursor: pointer;
	}

	.producto-results {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		max-height: 12rem;
		overflow-y: auto;
		background-color: #ffffff;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.1);
		z-index: 20;
	}

	.filter-field--search {
		position: relative;
	}

	.producto-results__empty {
		margin: 0;
		padding: 0.75rem;
		font-size: 0.875rem;
		color: #64748b;
	}

	.producto-results__item {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		width: 100%;
		padding: 0.625rem 0.75rem;
		font-size: 0.875rem;
		text-align: left;
		color: #0f172a;
		background: none;
		border: none;
		border-bottom: 1px solid #f1f5f9;
		cursor: pointer;
		touch-action: manipulation;
	}

	.producto-results__item:last-child {
		border-bottom: none;
	}

	.producto-results__item:active {
		background-color: #f1f5f9;
	}

	.producto-results__sku {
		font-weight: 700;
	}

	.producto-results__desc {
		color: #64748b;
	}

	.filter-actions {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-top: 0.25rem;
	}

	.filter-actions__export,
	.filter-actions__clear,
	.historial-page__load-more {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.filter-actions__export {
		color: #ffffff;
		background-color: #2563eb;
	}

	.filter-actions__export:active:not(:disabled) {
		background-color: #1d4ed8;
	}

	.filter-actions__clear {
		color: #334155;
		background-color: #e2e8f0;
	}

	.filter-actions__clear:active:not(:disabled) {
		background-color: #cbd5e1;
	}

	button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.historial-page__error {
		padding: 0.875rem 1rem;
		font-weight: 600;
		color: #7f1d1d;
		background-color: #fee2e2;
		border-radius: 0.5rem;
	}

	.historial-page__count {
		font-size: 0.875rem;
		font-weight: 600;
		color: #64748b;
	}

	.historial-page__empty {
		padding: 2rem 1rem;
		text-align: center;
		color: #64748b;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
	}

	.movimiento-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.movimiento-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.875rem 1rem;
		background-color: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 0.75rem;
	}

	.movimiento-card__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.movimiento-card__badge {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.625rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: #ffffff;
		border-radius: 9999px;
	}

	.movimiento-card__datetime {
		font-size: 0.875rem;
		font-weight: 600;
		color: #64748b;
		white-space: nowrap;
	}

	.movimiento-card__body {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.movimiento-card__description {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
	}

	.movimiento-card__stock {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.movimiento-card__stock-general {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 500;
		color: #64748b;
	}

	.movimiento-card__producto {
		margin: 0;
		font-size: 0.875rem;
		color: #64748b;
	}

	.movimiento-card__ubicacion {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.movimiento-card__footer {
		display: flex;
		justify-content: flex-end;
		font-size: 0.875rem;
		font-weight: 600;
		color: #64748b;
	}

	.historial-page__load-more {
		width: 100%;
		margin-top: 0.5rem;
		color: #ffffff;
		background-color: #0f172a;
	}

	.historial-page__load-more:active:not(:disabled) {
		background-color: #1e293b;
	}

	@media (min-width: 640px) {
		.historial-page__filters {
			grid-template-columns: repeat(2, 1fr);
		}

		.filter-actions {
			grid-column: span 2;
		}
	}
</style>
