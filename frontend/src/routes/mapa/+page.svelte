<script lang="ts">
	import { onMount } from 'svelte';
	import WarehouseMap from '$lib/components/WarehouseMap.svelte';
	import MapDetailPanel from '$lib/components/MapDetailPanel.svelte';
	import ProductSearchModal from '$lib/components/ProductSearchModal.svelte';
	import ShelfDetailModal from '$lib/components/ShelfDetailModal.svelte';
	import {
		listDepositos,
		listEstantes,
		getEstante,
		assignProductToUbicacion,
		unassignProductFromUbicacion,
		searchProductos,
		ApiError
	} from '$lib/api/client';
	import { mapStore } from '$lib/stores/map';
	import type { Deposito, Estante, Ubicacion, ProductSearchResult } from '$lib/api/client';

	type EstanteWithUbicaciones = Estante & { ubicaciones: Ubicacion[] };

	let depositos = $state<Deposito[]>([]);
	let estantes = $state<EstanteWithUbicaciones[]>([]);
	let loading = $state(true);
	let error = $state('');

	type ActionType = 'assign' | 'change' | 'unassign';

	let actionLoading = $state<ActionType | null>(null);
	let actionError = $state<string | null>(null);
	let confirmingUnassign = $state(false);

	let searchModalOpen = $state(false);
	let searchModalMode = $state<ActionType>('assign');
	let searchResults = $state<ProductSearchResult[]>([]);
	let searchSearching = $state(false);
	let searchSelecting = $state(false);

	let expandedEstante = $state<EstanteWithUbicaciones | null>(null);

	const selectedCellId = $derived($mapStore.selectedCellId);
	const selectedUbicacion = $derived(
		estantes
			.flatMap((e) => e.ubicaciones)
			.find((u) => u.id === selectedCellId)
	);

	async function loadMap() {
		loading = true;
		error = '';
		try {
			const [depositosData, estantesData] = await Promise.all([
				listDepositos(),
				listEstantes(false, null)
			]);

			depositos = depositosData;

			const nonDeletedEstantes = estantesData.filter((e) => !e.deleted_at);
			const estantesWithUbicaciones: EstanteWithUbicaciones[] = await Promise.all(
				nonDeletedEstantes.map(async (estante) => {
					const detail = await getEstante(estante.id);
					return {
						...estante,
						ubicaciones: detail.ubicaciones ?? []
					};
				})
			);

			const ubicacionesByEstante = estantesWithUbicaciones.reduce<Record<number, Ubicacion[]>>(
				(acc, estante) => {
					acc[estante.id] = estante.ubicaciones;
					return acc;
				},
				{}
			);

			estantes = estantesWithUbicaciones;
			mapStore.update((s) => ({ ...s, estantes: estantesData, ubicaciones: ubicacionesByEstante }));
		} catch (err) {
			error = err instanceof Error ? err.message : 'Error al cargar el mapa';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadMap();
	});

	function handleCellClick(ubicacion: Ubicacion) {
		mapStore.update((s) => ({
			...s,
			selectedCellId: s.selectedCellId === ubicacion.id ? null : ubicacion.id
		}));
		confirmingUnassign = false;
		clearActionError();
	}

	function handleClosePanel() {
		mapStore.update((s) => ({ ...s, selectedCellId: null }));
		confirmingUnassign = false;
		clearActionError();
	}

	function clearActionError() {
		actionError = null;
	}

	async function refreshEstante(estanteId: number) {
		const detail = await getEstante(estanteId);
		estantes = estantes.map((e) =>
			e.id === estanteId ? { ...e, ubicaciones: detail.ubicaciones ?? [] } : e
		);
		mapStore.update((s) => ({
			...s,
			ubicaciones: { ...s.ubicaciones, [estanteId]: detail.ubicaciones ?? [] }
		}));
	}

	function openSearchModal(mode: ActionType) {
		searchModalMode = mode;
		searchResults = [];
		searchSearching = false;
		searchSelecting = false;
		searchModalOpen = true;
		clearActionError();
	}

	function closeSearchModal() {
		searchModalOpen = false;
		searchResults = [];
		searchSearching = false;
		searchSelecting = false;
	}

	async function handleSearch(query: string) {
		searchSearching = true;
		try {
			searchResults = await searchProductos(query);
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Error al buscar productos';
			searchResults = [];
		} finally {
			searchSearching = false;
		}
	}

	function formatActionError(
		err: unknown,
		fallback: string,
		networkMessage: string = 'Error de conexión'
	): string {
		if (err instanceof ApiError) {
			if (err.status === 409) return 'Esta ubicación ya tiene un producto asignado';
			if (err.status === 400) {
				const msg = err.message.toLowerCase();
				if (msg.includes('suelto')) {
					return 'El estante Suelto no admite asignación de productos individuales';
				}
			}
			return err.message || fallback;
		}
		if (err instanceof TypeError) {
			return networkMessage;
		}
		return err instanceof Error ? err.message : fallback;
	}

	async function handleAssignProduct(sku: string) {
		if (!selectedUbicacion) return;
		actionLoading = 'assign';
		clearActionError();
		try {
			await assignProductToUbicacion(selectedUbicacion.id, sku);
			await refreshEstante(selectedUbicacion.estante_id);
		} catch (err) {
			actionError = formatActionError(
				err,
				'Error al asignar el producto',
				'Error de conexión al asignar producto'
			);
			await refreshEstante(selectedUbicacion.estante_id).catch(() => {});
		} finally {
			actionLoading = null;
			closeSearchModal();
		}
	}

	async function handleChangeProduct(sku: string) {
		if (!selectedUbicacion) return;
		actionLoading = 'change';
		clearActionError();
		try {
			await unassignProductFromUbicacion(selectedUbicacion.id);
			await assignProductToUbicacion(selectedUbicacion.id, sku);
			await refreshEstante(selectedUbicacion.estante_id);
		} catch (err) {
			actionError = formatActionError(
				err,
				'Error al cambiar el producto',
				'Error de conexión al cambiar el producto'
			);
			await refreshEstante(selectedUbicacion.estante_id).catch(() => {});
		} finally {
			actionLoading = null;
			closeSearchModal();
		}
	}

	async function handleUnassign() {
		if (!selectedUbicacion?.producto_sku) return;
		confirmingUnassign = true;
	}

	async function handleConfirmUnassign() {
		if (!selectedUbicacion?.producto_sku) return;

		actionLoading = 'unassign';
		clearActionError();
		try {
			await unassignProductFromUbicacion(selectedUbicacion.id);
			await refreshEstante(selectedUbicacion.estante_id);
			confirmingUnassign = false;
		} catch (err) {
			actionError = formatActionError(
				err,
				'Error al desasignar el producto',
				'Error de conexión al desasignar el producto'
			);
		} finally {
			actionLoading = null;
		}
	}

	function handleCancelUnassign() {
		confirmingUnassign = false;
		clearActionError();
	}

	async function handleSelectProduct(product: ProductSearchResult) {
		searchSelecting = true;
		clearActionError();
		try {
			if (searchModalMode === 'assign') {
				await handleAssignProduct(product.sku);
			} else {
				await handleChangeProduct(product.sku);
			}
		} finally {
			searchSelecting = false;
		}
	}

	const searchModalTitle = $derived(
		searchModalMode === 'assign'
			? `Asignar producto a ${selectedUbicacion?.qr_valor ?? ''}`
			: `Cambiar producto en ${selectedUbicacion?.qr_valor ?? ''}`
	);
</script>

<div class="map-page" class:map-page--panel-open={selectedUbicacion}>
	<header class="map-page__header">
		<h1>Mapa visual</h1>
		<p class="map-page__subtitle">Ubicaciones por depósito y estante</p>
	</header>

	<div class="map-page__legend" aria-label="Leyenda del mapa">
		<span class="legend__item">🟩 Ocupado (con stock)</span>
		<span class="legend__item">🟨 Stock bajo</span>
		<span class="legend__item">⬜ Vacío</span>
		<span class="legend__item">🔵 Suelto</span>
		<span class="legend__item">🔵 Seleccionado</span>
	</div>

	{#if loading}
		<div class="map-page__status">
			<p>Cargando mapa...</p>
		</div>
	{:else if error}
		<div class="map-page__status map-page__status--error">
			<p>{error}</p>
			<button type="button" class="map-page__retry" onclick={loadMap}>Reintentar</button>
		</div>
	{:else if estantes.length === 0}
		<div class="map-page__status">
			<p>No hay estantes configurados.</p>
		</div>
	{:else}
		<WarehouseMap
			{depositos}
			{estantes}
			selectedCellId={selectedCellId ?? null}
			onCellClick={handleCellClick}
			onExpand={(e) => (expandedEstante = e)}
		/>
	{/if}
</div>

{#if selectedUbicacion}
	<MapDetailPanel
		selectedUbicacion={selectedUbicacion}
		onClose={handleClosePanel}
		onAssign={() => openSearchModal('assign')}
		onChange={() => openSearchModal('change')}
		onUnassign={handleUnassign}
		onConfirmUnassign={handleConfirmUnassign}
		onCancelUnassign={handleCancelUnassign}
		loadingAction={actionLoading}
		actionError={actionError}
		confirmingUnassign={confirmingUnassign}
	/>
{/if}

<ProductSearchModal
	open={searchModalOpen}
	title={searchModalTitle}
	searching={searchSearching}
	selecting={searchSelecting}
	results={searchResults}
	onclose={closeSearchModal}
	onsearch={handleSearch}
	onselect={handleSelectProduct}
/>

{#if expandedEstante}
	<ShelfDetailModal estante={expandedEstante} onClose={() => (expandedEstante = null)} />
{/if}

<style>
	.map-page {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: env(safe-area-inset-top);
		padding-bottom: env(safe-area-inset-bottom);
	}

	.map-page--panel-open {
		padding-bottom: calc(env(safe-area-inset-bottom) + 1rem);
	}

	.map-page__header {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.map-page__header h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 800;
		color: #0f172a;
	}

	.map-page__subtitle {
		margin: 0;
		font-size: 0.875rem;
		color: #64748b;
	}

	.map-page__legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		padding: 0.75rem;
		background-color: #f8fafc;
		border-radius: 0.5rem;
	}

	.legend__item {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.map-page__status {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 2rem 1rem;
		text-align: center;
		color: #334155;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
	}

	.map-page__status--error {
		color: #7f1d1d;
		background-color: #fee2e2;
	}

	.map-page__retry {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1.5rem;
		font-size: 1rem;
		font-weight: 600;
		color: #ffffff;
		background-color: #2563eb;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}
</style>
