<script lang="ts">
	import {
		listEstantes,
		getEstante,
		createEstante,
		updateEstante,
		deleteEstante,
		confirmDeleteOutOfBounds,
		assignProductToUbicacion,
		unassignProductFromUbicacion,
		searchProductos,
		ApiError,
		type Estante,
		type Ubicacion,
		type ProductSearchResult
	} from '$lib/api/client';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------
	let estantes = $state<Estante[]>([]);
	let loading = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	let view = $state<'list' | 'detail'>('list');
	let selectedEstante = $state<Estante | null>(null);
	let selectedUbicaciones = $state<Ubicacion[]>([]);

	// Create form
	let createOpen = $state(false);
	let createNombre = $state('');
	let createOrden = $state(0);
	let createFilas = $state(1);
	let createColumnas = $state(1);
	let creating = $state(false);

	// Edit form
	let editOpen = $state(false);
	let editEstante = $state<Estante | null>(null);
	let editFilas = $state(1);
	let editColumnas = $state(1);
	let editing = $state(false);

	// Soft-delete confirmation
	let estanteToDelete = $state<Estante | null>(null);
	let deleting = $state(false);

	// Out-of-bounds warning after shrinking
	let pendingUpdate = $state<{
		estante: Estante;
		outOfBounds: Ubicacion[];
		oldFilas: number;
		oldColumnas: number;
	} | null>(null);

	// Product assignment
	let assignUbicacion = $state<Ubicacion | null>(null);
	let searchQuery = $state('');
	let searchResults = $state<ProductSearchResult[]>([]);
	let searching = $state(false);
	let assigning = $state(false);

	const SYSTEM_SHELF_NAME = 'Suelto';

	loadEstantes();

	// ---------------------------------------------------------------------------
	// Helpers
	// ---------------------------------------------------------------------------
	function showMessage(text: string, type: 'success' | 'error' = 'success') {
		message = { text, type };
		setTimeout(() => {
			message = null;
		}, 5000);
	}

	function isSystemShelf(estante: Estante): boolean {
		return estante.nombre === SYSTEM_SHELF_NAME;
	}

	function qrPreview(nombre: string, filas: number, columnas: number): string {
		if (filas === 1 && columnas === 1) return `QR ejemplo: ${nombre}`;
		if (filas === 1) return `QR ejemplo: ${nombre}-C1`;
		if (columnas === 1) return `QR ejemplo: ${nombre}-F1`;
		return `QR ejemplo: ${nombre}-F1-C1`;
	}

	function cellClass(ubicacion: Ubicacion): string {
		return ubicacion.producto_id ? 'cell cell--occupied' : 'cell cell--empty';
	}

	async function loadEstantes() {
		loading = true;
		try {
			estantes = await listEstantes();
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al cargar estantes', 'error');
		} finally {
			loading = false;
		}
	}

	async function openDetail(estante: Estante) {
		loading = true;
		try {
			const detail = await getEstante(estante.id);
			selectedEstante = detail;
			selectedUbicaciones = detail.ubicaciones ?? [];
			view = 'detail';
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al cargar el estante', 'error');
		} finally {
			loading = false;
		}
	}

	function closeDetail() {
		view = 'list';
		selectedEstante = null;
		selectedUbicaciones = [];
	}

	function resetCreateForm() {
		createNombre = '';
		createOrden = 0;
		createFilas = 1;
		createColumnas = 1;
		createOpen = false;
	}

	async function handleCreate() {
		const nombre = createNombre.trim();
		if (!nombre) {
			showMessage('El nombre es obligatorio', 'error');
			return;
		}
		const filas = Number(createFilas);
		const columnas = Number(createColumnas);
		if (filas < 1 || columnas < 1) {
			showMessage('Las filas y columnas deben ser al menos 1', 'error');
			return;
		}

		creating = true;
		try {
			const created = await createEstante({
				nombre,
				orden_visual: Number(createOrden),
				filas,
				columnas
			});
			resetCreateForm();
			await loadEstantes();
			showMessage(`Estante creado con ${created.ubicaciones_count} ubicaciones`);
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				showMessage('Ya existe un estante con ese nombre', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al crear el estante', 'error');
			}
		} finally {
			creating = false;
		}
	}

	function openEdit(estante: Estante) {
		editEstante = estante;
		editFilas = estante.filas;
		editColumnas = estante.columnas;
		editOpen = true;
	}

	function closeEdit() {
		editOpen = false;
		editEstante = null;
	}

	async function handleEdit() {
		if (!editEstante) return;
		const filas = Number(editFilas);
		const columnas = Number(editColumnas);
		if (filas < 1 || columnas < 1) {
			showMessage('Las filas y columnas deben ser al menos 1', 'error');
			return;
		}
		if (filas === editEstante.filas && columnas === editEstante.columnas) {
			closeEdit();
			return;
		}

		editing = true;
		try {
			const response = await updateEstante(editEstante.id, { filas, columnas });
			closeEdit();
			if (response.out_of_bounds.length > 0) {
				pendingUpdate = {
					estante: response.estante,
					outOfBounds: response.out_of_bounds,
					oldFilas: editEstante.filas,
					oldColumnas: editEstante.columnas
				};
			} else {
				await loadEstantes();
				if (selectedEstante?.id === response.estante.id) {
					await openDetail(response.estante);
				}
				showMessage('Estante actualizado');
			}
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al actualizar el estante', 'error');
		} finally {
			editing = false;
		}
	}

	async function confirmOutOfBoundsDelete() {
		if (!pendingUpdate) return;
		try {
			const ids = pendingUpdate.outOfBounds.map((u) => u.id);
			const result = await confirmDeleteOutOfBounds(pendingUpdate.estante.id, ids);
			await loadEstantes();
			if (selectedEstante?.id === pendingUpdate.estante.id) {
				await openDetail(pendingUpdate.estante);
			}
			showMessage(`${result.deleted} ubicaciones eliminadas`);
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al eliminar ubicaciones', 'error');
		} finally {
			pendingUpdate = null;
		}
	}

	async function cancelOutOfBounds() {
		if (!pendingUpdate) return;
		try {
			await updateEstante(pendingUpdate.estante.id, {
				filas: pendingUpdate.oldFilas,
				columnas: pendingUpdate.oldColumnas
			});
			await loadEstantes();
			if (selectedEstante?.id === pendingUpdate.estante.id) {
				await openDetail(pendingUpdate.estante);
			}
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al revertir el cambio', 'error');
		} finally {
			pendingUpdate = null;
		}
	}

	function openDelete(estante: Estante) {
		estanteToDelete = estante;
	}

	function closeDelete() {
		estanteToDelete = null;
	}

	async function handleDelete() {
		if (!estanteToDelete) return;
		deleting = true;
		try {
			await deleteEstante(estanteToDelete.id);
			closeDelete();
			await loadEstantes();
			showMessage('Estante eliminado');
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al eliminar el estante', 'error');
		} finally {
			deleting = false;
		}
	}

	function openAssign(ubicacion: Ubicacion) {
		if (ubicacion.producto_id) return;
		assignUbicacion = ubicacion;
		searchQuery = '';
		searchResults = [];
	}

	function closeAssign() {
		assignUbicacion = null;
		searchQuery = '';
		searchResults = [];
	}

	async function handleSearchProducts() {
		const query = searchQuery.trim();
		if (query.length < 2) {
			searchResults = [];
			return;
		}
		searching = true;
		try {
			searchResults = await searchProductos(query);
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al buscar productos', 'error');
			searchResults = [];
		} finally {
			searching = false;
		}
	}

	async function handleAssign(product: ProductSearchResult) {
		if (!assignUbicacion) return;
		assigning = true;
		try {
			await assignProductToUbicacion(assignUbicacion.id, product.sku);
			closeAssign();
			if (selectedEstante) {
				await openDetail(selectedEstante);
			}
			showMessage(`Producto ${product.sku} asignado`);
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al asignar el producto', 'error');
		} finally {
			assigning = false;
		}
	}

	async function handleUnassign(ubicacionId: number) {
		if (!confirm('¿Quitar el producto de esta ubicación? El historial de movimientos se conserva.')) return;
		try {
			await unassignProductFromUbicacion(ubicacionId);
			if (selectedEstante) {
				await openDetail(selectedEstante);
			}
			showMessage('Producto desasignado de la ubicación');
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al desasignar el producto', 'error');
		}
	}

	const activeUbicaciones = $derived(selectedUbicaciones.filter((u) => u.estado === 'activo'));
</script>

<section class="estantes-page">
	{#if view === 'list'}
		<header class="page-header">
			<h1>Estantes</h1>
			<button
				class="button button--primary"
				onclick={() => (createOpen = true)}
				disabled={loading}
			>
				Nuevo estante
			</button>
		</header>

		{#if message}
			<div class="alert alert--{message.type}" role="alert">
				{message.text}
			</div>
		{/if}

		{#if loading && estantes.length === 0}
			<p class="loading">Cargando…</p>
		{:else if estantes.length === 0}
			<p class="empty">No hay estantes configurados.</p>
		{:else}
			<ul class="estante-list">
				{#each estantes as estante (estante.id)}
					<li class="estante-card" class:estante-card--system={isSystemShelf(estante)}>
						<div class="estante-card__header">
							<h2 class="estante-card__title">{estante.nombre}</h2>
							{#if isSystemShelf(estante)}
								<span class="badge badge--system">sistema</span>
							{/if}
						</div>

						<div class="estante-card__meta">
							<span>{estante.filas} × {estante.columnas}</span>
							<span>{estante.ubicaciones_count} ubicaciones</span>
							<span class="qr-preview">{qrPreview(estante.nombre, estante.filas, estante.columnas)}</span>
						</div>

						<div class="estante-card__actions">
							<button
								class="button button--secondary"
								onclick={() => openDetail(estante)}
								disabled={loading}
							>
								Ver ubicaciones
							</button>
							<button
								class="button button--secondary"
								onclick={() => openEdit(estante)}
								disabled={isSystemShelf(estante) || loading}
							>
								Editar
							</button>
							<button
								class="button button--danger"
								onclick={() => openDelete(estante)}
								disabled={isSystemShelf(estante) || loading}
							>
								Eliminar
							</button>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}

	{#if view === 'detail' && selectedEstante}
		<div class="detail-view">
			<header class="detail-header">
				<div>
					<h1>{selectedEstante.nombre}</h1>
					<p class="detail-meta">
						{selectedEstante.filas} × {selectedEstante.columnas} · {activeUbicaciones.length} ubicaciones
					</p>
				</div>
				<button class="button button--secondary" onclick={closeDetail}>Volver</button>
			</header>

			{#if message}
				<div class="alert alert--{message.type}" role="alert">
					{message.text}
				</div>
			{/if}

			{#if loading}
				<p class="loading">Cargando ubicaciones…</p>
			{:else}
				<div
					class="ubicaciones-grid"
					style="grid-template-columns: repeat({selectedEstante.columnas}, minmax(48px, 1fr));"
				>
				{#each activeUbicaciones as ubicacion (ubicacion.id)}
					<div class={cellClass(ubicacion)}>
						<span class="cell__coords">{ubicacion.fila}-{ubicacion.columna}</span>
						<span class="cell__qr">{ubicacion.qr_valor}</span>
						{#if ubicacion.producto_id}
							<span class="cell__product">{ubicacion.producto_sku}</span>
							<span class="cell__desc">{ubicacion.producto_descripcion ?? ''}</span>
							<span class="cell__stock">Stock: {ubicacion.stock_actual}</span>
							{#if selectedEstante.nombre !== SYSTEM_SHELF_NAME}
								<button
									class="button button--small button--danger"
									onclick={() => handleUnassign(ubicacion.id)}
								>
									Desasignar
								</button>
							{/if}
						{:else if selectedEstante.nombre !== SYSTEM_SHELF_NAME}
							<span class="cell__empty">vacío</span>
							<button
								class="button button--small button--primary"
								onclick={() => openAssign(ubicacion)}
							>
								Asignar producto
							</button>
						{:else}
							<span class="cell__empty">sistema</span>
						{/if}
					</div>
				{/each}
				</div>
			{/if}
		</div>
	{/if}
</section>

{#if createOpen}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={() => (createOpen = false)}
		onkeydown={(e) => e.key === 'Escape' && (createOpen = false)}
	>
		<div
			class="modal"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="create-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="create-title">Nuevo estante</h2>

			<label class="field-label" for="create-nombre">Nombre</label>
			<input id="create-nombre" class="field-input" type="text" bind:value={createNombre} maxlength="50" />

			<label class="field-label" for="create-orden">Orden visual</label>
			<input id="create-orden" class="field-input" type="number" bind:value={createOrden} min="0" />

			<label class="field-label" for="create-filas">Filas</label>
			<input id="create-filas" class="field-input" type="number" bind:value={createFilas} min="1" max="50" />

			<label class="field-label" for="create-columnas">Columnas</label>
			<input id="create-columnas" class="field-input" type="number" bind:value={createColumnas} min="1" max="50" />

			<p class="qr-preview qr-preview--standalone">
				{qrPreview(createNombre || 'Nombre', Number(createFilas) || 1, Number(createColumnas) || 1)}
			</p>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={() => (createOpen = false)} disabled={creating}>
					Cancelar
				</button>
				<button class="button button--primary" onclick={handleCreate} disabled={creating}>
					{creating ? 'Creando…' : 'Crear'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if editOpen && editEstante}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeEdit}
		onkeydown={(e) => e.key === 'Escape' && closeEdit()}
	>
		<div
			class="modal"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="edit-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="edit-title">Editar {editEstante.nombre}</h2>

			<label class="field-label" for="edit-nombre">Nombre</label>
			<input id="edit-nombre" class="field-input" type="text" value={editEstante.nombre} disabled />

			<label class="field-label" for="edit-filas">Filas</label>
			<input id="edit-filas" class="field-input" type="number" bind:value={editFilas} min="1" max="50" />

			<label class="field-label" for="edit-columnas">Columnas</label>
			<input id="edit-columnas" class="field-input" type="number" bind:value={editColumnas} min="1" max="50" />

			<p class="hint">El nombre no se puede cambiar porque los códigos QR ya generados dependen de él.</p>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeEdit} disabled={editing}>Cancelar</button>
				<button class="button button--primary" onclick={handleEdit} disabled={editing}>
					{editing ? 'Guardando…' : 'Guardar'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if estanteToDelete}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeDelete}
		onkeydown={(e) => e.key === 'Escape' && closeDelete()}
	>
		<div
			class="modal modal--warning"
			role="alertdialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="delete-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="delete-title">¿Eliminar el estante {estanteToDelete.nombre}?</h2>
			<p>Las ubicaciones y el historial de auditoría se conservan.</p>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeDelete} disabled={deleting}>Cancelar</button>
				<button class="button button--danger" onclick={handleDelete} disabled={deleting}>
					{deleting ? 'Eliminando…' : 'Eliminar'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if pendingUpdate}
	<div class="modal-backdrop" role="presentation" tabindex="-1">
		<div
			class="modal modal--warning"
			role="alertdialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="oob-title"
		>
			<h2 id="oob-title">Ubicaciones fuera de rango</h2>
			<p>
				{pendingUpdate.outOfBounds.length} ubicaciones quedan fuera de los nuevos límites.
				{#if pendingUpdate.outOfBounds.some((u) => u.producto_id)}
					Algunas tienen productos asignados.
				{/if}
			</p>

			<ul class="oob-list">
				{#each pendingUpdate.outOfBounds as ubicacion}
					<li>
						<strong>{ubicacion.qr_valor}</strong>
						<span>(fila {ubicacion.fila}, col {ubicacion.columna})</span>
						{#if ubicacion.producto_id}
							<span> — {ubicacion.producto_sku} · stock {ubicacion.stock_actual}</span>
						{/if}
					</li>
				{/each}
			</ul>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={cancelOutOfBounds}>Cancelar</button>
				<button class="button button--danger" onclick={confirmOutOfBoundsDelete}>
					Confirmar eliminación
				</button>
			</div>
		</div>
	</div>
{/if}

{#if assignUbicacion}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeAssign}
		onkeydown={(e) => e.key === 'Escape' && closeAssign()}
	>
		<div
			class="modal"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="assign-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="assign-title">Asignar producto a {assignUbicacion.qr_valor}</h2>

			<label class="field-label" for="assign-search">Buscar por SKU o código de barra</label>
			<div class="search-row">
				<input
					id="assign-search"
					class="field-input"
					type="text"
					bind:value={searchQuery}
					placeholder="Ej: 7791234567890"
					onkeydown={(e) => e.key === 'Enter' && handleSearchProducts()}
				/>
				<button class="button button--secondary" onclick={handleSearchProducts} disabled={searching}>
					{searching ? '…' : 'Buscar'}
				</button>
			</div>

			{#if searchResults.length > 0}
				<ul class="product-list">
					{#each searchResults as product}
						<li class="product-item">
							<div class="product-item__info">
								<strong>{product.sku}</strong>
								<span>{product.descripcion}</span>
								<span class="product-item__barcode">{product.codigo_de_barra}</span>
							</div>
							<button
								class="button button--small button--primary"
								onclick={() => handleAssign(product)}
								disabled={assigning}
							>
								Asignar
							</button>
						</li>
					{/each}
				</ul>
			{:else if searchQuery.trim().length >= 2 && !searching}
				<p class="empty">No se encontraron productos.</p>
			{/if}

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeAssign} disabled={assigning}>Cancelar</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.estantes-page {
		padding: 0 0 2rem;
	}

	.page-header,
	.detail-header {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.detail-header {
		flex-direction: row;
		align-items: flex-start;
		justify-content: space-between;
	}

	h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	.button {
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

	.button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.button--primary {
		color: #ffffff;
		background-color: #2563eb;
	}

	.button--primary:not(:disabled):active {
		background-color: #1d4ed8;
	}

	.button--secondary {
		color: #334155;
		background-color: #f1f5f9;
	}

	.button--secondary:not(:disabled):active {
		background-color: #e2e8f0;
	}

	.button--danger {
		color: #ffffff;
		background-color: #dc2626;
	}

	.button--danger:not(:disabled):active {
		background-color: #b91c1c;
	}

	.button--small {
		min-height: 2.25rem;
		padding: 0.375rem 0.75rem;
		font-size: 0.875rem;
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

	.estante-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.estante-card {
		padding: 1rem;
		border: 1px solid #e2e8f0;
		border-radius: 0.75rem;
		background-color: #ffffff;
	}

	.estante-card--system {
		background-color: #f8fafc;
	}

	.estante-card__header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.estante-card__title {
		font-size: 1.125rem;
		margin: 0;
	}

	.badge {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 0.25rem 0.5rem;
		border-radius: 9999px;
	}

	.badge--system {
		color: #475569;
		background-color: #e2e8f0;
	}

	.estante-card__meta {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		color: #475569;
		font-size: 0.875rem;
		margin-bottom: 1rem;
	}

	.qr-preview {
		color: #64748b;
	}

	.qr-preview--standalone {
		margin: 0.75rem 0 0;
		font-size: 0.875rem;
		font-weight: 500;
		color: #334155;
	}

	.estante-card__actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	@media (min-width: 640px) {
		.estante-card__actions {
			grid-template-columns: repeat(3, 1fr);
		}

		.page-header {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}

	.detail-meta {
		color: #64748b;
		margin: 0.25rem 0 0;
	}

	.ubicaciones-grid {
		display: grid;
		gap: 0.25rem;
		overflow-x: auto;
		padding-bottom: 0.5rem;
		touch-action: manipulation;
	}

	.cell {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.125rem;
		min-height: 5rem;
		padding: 0.5rem;
		border-radius: 0.375rem;
		font-size: 0.75rem;
		text-align: center;
		word-break: break-word;
	}

	.cell--empty {
		background-color: #e2e8f0;
		color: #64748b;
	}

	.cell--occupied {
		background-color: #bbf7d0;
		color: #14532d;
	}

	.cell__coords {
		font-weight: 700;
	}

	.cell__qr {
		font-size: 0.6875rem;
		color: #475569;
	}

	.cell__product {
		font-weight: 600;
	}

	.cell__desc,
	.cell__stock {
		font-size: 0.6875rem;
	}

	.cell__empty {
		font-weight: 500;
		text-transform: uppercase;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding: 1rem;
		background-color: rgba(15, 23, 42, 0.6);
		z-index: 50;
		overflow-y: auto;
	}

	.modal {
		width: 100%;
		max-width: 28rem;
		margin-top: 2rem;
		padding: 1.25rem;
		background-color: #ffffff;
		border-radius: 0.75rem;
		box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
	}

	.modal--warning {
		border-top: 4px solid #dc2626;
	}

	.modal h2 {
		font-size: 1.25rem;
		margin: 0 0 1rem;
	}

	.modal-actions {
		display: flex;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}

	.modal-actions .button {
		flex: 1;
	}

	.field-label {
		display: block;
		margin-top: 0.75rem;
		margin-bottom: 0.375rem;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.field-input {
		width: 100%;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		background-color: #ffffff;
	}

	.field-input:disabled {
		background-color: #f1f5f9;
		color: #64748b;
	}

	.hint {
		font-size: 0.875rem;
		color: #64748b;
		margin-top: 0.75rem;
	}

	.oob-list {
		list-style: none;
		margin: 1rem 0 0;
		padding: 0;
		max-height: 16rem;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.oob-list li {
		padding: 0.625rem;
		background-color: #f1f5f9;
		border-radius: 0.375rem;
		font-size: 0.875rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}

	.search-row {
		display: flex;
		gap: 0.5rem;
	}

	.search-row .field-input {
		flex: 1;
	}

	.product-list {
		list-style: none;
		margin: 1rem 0 0;
		padding: 0;
		max-height: 16rem;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.product-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem;
		background-color: #f8fafc;
		border-radius: 0.5rem;
	}

	.product-item__info {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		font-size: 0.875rem;
		min-width: 0;
	}

	.product-item__info span {
		color: #475569;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.product-item__barcode {
		font-size: 0.75rem;
		color: #64748b;
	}
</style>
