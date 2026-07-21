<script lang="ts">
	import { fade } from 'svelte/transition';
	import { get } from 'svelte/store';
	import Scanner from '$lib/components/Scanner.svelte';
	import ProductCard from '$lib/components/ProductCard.svelte';
	import ProductLocationsCard from '$lib/components/ProductLocationsCard.svelte';
	import { scannerState, anchoredLocation, type AnchoredLocation } from '$lib/stores/scanner';
	import { sessionStore } from '$lib/stores/session';
	import {
		listEstantes,
		listDepositos,
		getEstanteUbicaciones,
		lookupSector,
		getProductoByBarcodeWithStock,
		getProductoStockTotal,
		getProductoUbicaciones,
		createMovimiento,
		ApiError
	} from '$lib/api/client';
	import type {
		Estante,
		Deposito,
		Ubicacion,
		ProductWithUbicacionStock,
		ProductoUbicacionItem,
		ProductoUbicacionesResponse
	} from '$lib/api/client';

	interface LastScan {
		text: string;
		format: string;
	}

	let scannerRef: {
		pause: () => void;
		resume: () => void;
		stop: () => Promise<void>;
		start: () => Promise<void>;
	} | null = $state(null);

	let cameraError = $state('');
	let lastScan = $state<LastScan | null>(null);
	let scannedProduct = $state<ProductWithUbicacionStock | null>(null);
	let stockTotal = $state(0);

	let lastScannedCode = $state('');
	let lastScannedTime = $state(0);
	const DEBOUNCE_MS = 2000;

	let quantity = $state(0);
	let mode = $state<'alta' | 'ajuste'>('alta');
	let isSaving = $state(false);

	let greenFlash = $state<string | null>(null);
	let greenFlashTimeout: ReturnType<typeof setTimeout> | null = null;
	let errorFlash = $state<string | null>(null);
	let errorFlashTimeout: ReturnType<typeof setTimeout> | null = null;

	let showLocationModal = $state(false);
	let depositos = $state<Deposito[]>([]);
	let selectedDepositoId = $state<number | null>(null);
	let estantes = $state<Estante[]>([]);
	let selectedEstanteId = $state<number | null>(null);
	let ubicaciones = $state<Ubicacion[]>([]);
	let loadingLocations = $state(false);

	// Product-locations fallback (scan product without anchored QR).
	let locationsProduct = $state<ProductoUbicacionesResponse | null>(null);
	let locationsList = $state<ProductoUbicacionItem[]>([]);
	let showLocationsCard = $state(false);
	let locationsLoading = $state(false);
	let scannedBarcodePending = $state('');

	function showGreenFlash(message: string) {
		greenFlash = message;
		if (greenFlashTimeout) clearTimeout(greenFlashTimeout);
		greenFlashTimeout = setTimeout(() => {
			greenFlash = null;
		}, 1500);
	}

	function showError(message: string) {
		errorFlash = message;
		if (errorFlashTimeout) clearTimeout(errorFlashTimeout);
		errorFlashTimeout = setTimeout(() => {
			errorFlash = null;
		}, 3000);
	}

	async function handleScan(decodedText: string, formatName: string) {
		const now = Date.now();
		if (decodedText === lastScannedCode && now - lastScannedTime < DEBOUNCE_MS) {
			return;
		}
		lastScannedCode = decodedText;
		lastScannedTime = now;
		lastScan = { text: decodedText, format: formatName };

		if (formatName === 'QR_CODE') {
			await handleSectorScan(decodedText);
		} else {
			await handleProductScan(decodedText);
		}
	}

	async function finalizeLocationSelection(anchored: AnchoredLocation, barcode: string) {
		// Shared by handleSelectLocation (tap a location) and handleSectorScan
		// (QR scanned while the locations card is visible): anchor the location,
		// pause the camera to enter stock-entry mode, and load the already-scanned
		// product for that location so ProductCard + StockInput render exactly as
		// in the QR-first flow.
		showLocationsCard = false;
		anchoredLocation.set(anchored);
		scannerRef?.pause();

		try {
			const product = await getProductoByBarcodeWithStock(barcode, anchored.ubicacion_id);
			if (!product) {
				showError('Producto no encontrado al anclar ubicación');
				return;
			}
			scannedProduct = product;
			quantity = 0;
			mode = 'alta';
			try {
				const stockInfo = await getProductoStockTotal(product.sku);
				stockTotal = stockInfo.stock_total;
			} catch {
				stockTotal = 0;
			}
		} catch (err) {
			showError(`Error al cargar producto: ${barcode}`);
		}
	}

	async function loadProductLocations(barcode: string): Promise<boolean> {
		// Fetch locations for the given barcode and update the locations card
		// state. Used when the card first opens (no anchored location) and when a
		// different product is scanned while the card is already visible. Returns
		// true on success, false on error so the caller decides the UX.
		locationsLoading = true;
		locationsProduct = null;
		locationsList = [];
		try {
			const result = await getProductoUbicaciones(barcode);
			locationsProduct = result;
			locationsList = result.ubicaciones;
			return true;
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) {
				showError('Producto no encontrado');
			} else {
				showError(`Error al buscar producto: ${barcode}`);
			}
			return false;
		} finally {
			locationsLoading = false;
		}
	}

	async function handleSectorScan(qrValor: string) {
		try {
			const ubicacion = await lookupSector(qrValor);
			const anchored: AnchoredLocation = {
				ubicacion_id: ubicacion.id,
				estante_nombre: ubicacion.estante_nombre,
				qr_valor: ubicacion.qr_valor,
				fila: ubicacion.fila,
				columna: ubicacion.columna
			};

			if (showLocationsCard) {
				// QR scanned while the product-locations card is visible: the user
				// is picking a location for the already-scanned product. Anchor it,
				// pause the camera, and load the product for stock entry.
				await finalizeLocationSelection(anchored, scannedBarcodePending);
				return;
			}

			anchoredLocation.set(anchored);
			clearScannedProduct();
			showGreenFlash(`Ubicación anclada: ${ubicacion.estante_nombre} ${ubicacion.qr_valor}`);
		} catch (err) {
			if (err instanceof ApiError && err.status === 403) {
				showError('No tenés permiso para este depósito');
			} else {
				showError(`QR no reconocido: ${qrValor} — no es un sector válido`);
			}
		}
	}

	async function handleProductScan(barcode: string) {
		const location = get(anchoredLocation);

		// While the product-locations card is visible the camera stays active so
		// the user can scan a QR sector to pick a location. Re-scans of the same
		// product are ignored (the debounce in handleScan also covers this); a
		// different product refreshes the card in place without closing it.
		if (showLocationsCard) {
			if (barcode === scannedBarcodePending) {
				return;
			}
			scannedBarcodePending = barcode;
			await loadProductLocations(barcode);
			return;
		}

		if (!location) {
			// No QR anchored: fall back to the product-locations picker instead
			// of blocking with a red flash. The camera stays active so the user
			// can scan a QR sector to pick a location while the card is visible.
			scannedBarcodePending = barcode;
			showLocationsCard = true;
			const ok = await loadProductLocations(barcode);
			if (!ok) {
				showLocationsCard = false;
				scannerRef?.resume();
			}
			return;
		}

		scannerRef?.pause();

		try {
			const product = await getProductoByBarcodeWithStock(barcode, location.ubicacion_id);
			if (!product) {
				showError(`Producto no encontrado: ${barcode}`);
				clearScannedProduct();
				scannerRef?.resume();
				return;
			}

			scannedProduct = product;
			quantity = 0;
			mode = 'alta';

			try {
				const stockInfo = await getProductoStockTotal(product.sku);
				stockTotal = stockInfo.stock_total;
			} catch {
				stockTotal = 0;
			}

			showGreenFlash(`Producto: ${product.sku} — ${product.descripcion?.substring(0, 40) ?? ''}`);
		} catch (err) {
			showError(`Error al buscar producto: ${barcode}`);
			clearScannedProduct();
			scannerRef?.resume();
		}
	}

	function clearScannedProduct() {
		scannedProduct = null;
		stockTotal = 0;
		quantity = 0;
		mode = 'alta';
	}

	async function handleSave() {
		const location = get(anchoredLocation);
		if (!location || !scannedProduct) {
			showError('No hay producto ni ubicación para guardar');
			return;
		}

		if (!Number.isFinite(quantity) || quantity < 0) {
			showError('La cantidad debe ser un número mayor o igual a 0');
			return;
		}

		isSaving = true;
		try {
			const response = await createMovimiento({
				producto_sku: scannedProduct.sku,
				ubicacion_id: location.ubicacion_id,
				cantidad: quantity,
				tipo: mode
			});

			showGreenFlash(`Stock guardado: ${response.stock_anterior} → ${response.stock_nuevo}`);

			if (scannedProduct.ubicacion_stock) {
				scannedProduct = {
					...scannedProduct,
					ubicacion_stock: {
						...scannedProduct.ubicacion_stock,
						stock_actual: response.stock_nuevo,
						is_assigned: true
					}
				};
			}

			stockTotal += response.stock_nuevo - response.stock_anterior;
			quantity = 0;
			scannerRef?.resume();
		} catch (err) {
			if (err instanceof ApiError && err.status === 403) {
				showError('No tenés permiso para crear movimientos');
			} else {
				const message = err instanceof Error ? err.message : 'Error al guardar el movimiento';
				showError(message);
			}
		} finally {
			isSaving = false;
		}
	}

	function handleClose() {
		clearScannedProduct();
		scannerRef?.resume();
	}

	async function handleSelectLocation(loc: ProductoUbicacionItem) {
		// Anchor the chosen location — same shape as selectUbicacion / handleSectorScan.
		const anchored: AnchoredLocation = {
			ubicacion_id: loc.ubicacion_id,
			estante_nombre: loc.estante_nombre,
			qr_valor: loc.qr_valor,
			fila: loc.fila,
			columna: loc.columna
		};
		// Pause the camera (entering stock-entry mode) and load the product WITH
		// stock for the newly-anchored location — reuses the existing
		// getProductoByBarcodeWithStock path so ProductCard + StockInput render
		// exactly as in the QR-first flow.
		await finalizeLocationSelection(anchored, scannedBarcodePending);
	}

	function handleCancelLocations() {
		showLocationsCard = false;
		locationsProduct = null;
		locationsList = [];
		scannerRef?.resume();
	}

	function handleQuantityChange(value: number) {
		quantity = value;
	}

	function handleModeChange(newMode: 'alta' | 'ajuste') {
		mode = newMode;
	}

	function handleError(error: string) {
		cameraError = error;
	}

	function togglePause() {
		if ($scannerState === 'scanning') {
			scannerRef?.pause();
		} else if ($scannerState === 'paused') {
			scannerRef?.resume();
		}
	}

	async function retryCamera() {
		cameraError = '';
		await scannerRef?.start();
	}

	function clearAnchoredLocation() {
		anchoredLocation.set(null);
		clearScannedProduct();
	}

	function openLocationModal() {
		showLocationModal = true;
		if (estantes.length === 0) loadEstantes();
	}

	async function loadEstantes() {
		try {
			if (depositos.length === 0) {
				if ($sessionStore?.usuario.is_admin) {
					depositos = await listDepositos();
				} else if ($sessionStore) {
					depositos = $sessionStore.depositos.map((d) => ({
						id: d.deposito_id,
						nombre: d.deposito_nombre
					}));
					if (selectedDepositoId == null && depositos.length > 0) {
						selectedDepositoId = depositos[0].id;
					}
				}
			}
			const rows = await listEstantes(false, selectedDepositoId);
			estantes = rows.filter((e) => !e.deleted_at);
			if (estantes.length > 0 && !estantes.some((e) => e.id === selectedEstanteId)) {
				selectedEstanteId = estantes[0].id;
				await loadUbicaciones();
			} else if (estantes.length === 0) {
				selectedEstanteId = null;
				ubicaciones = [];
			}
		} catch (err) {
			console.error(err);
		}
	}

	async function loadUbicaciones() {
		if (selectedEstanteId == null) return;
		loadingLocations = true;
		try {
			ubicaciones = await getEstanteUbicaciones(selectedEstanteId);
		} finally {
			loadingLocations = false;
		}
	}

	function handleDepositoChange(event: Event) {
		const value = (event.target as HTMLSelectElement).value;
		selectedDepositoId = value === '' ? null : Number(value);
		selectedEstanteId = null;
		ubicaciones = [];
		loadEstantes();
	}

	function handleEstanteChange(event: Event) {
		const value = Number((event.target as HTMLSelectElement).value);
		selectedEstanteId = value;
		ubicaciones = [];
		loadUbicaciones();
	}

	function handleUbicacionChange(event: Event) {
		const value = Number((event.target as HTMLSelectElement).value);
		const ubicacion = ubicaciones.find((u) => u.id === value);
		if (ubicacion) {
			selectUbicacion(ubicacion);
		}
	}

	function selectUbicacion(ubicacion: Ubicacion) {
		const anchored: AnchoredLocation = {
			ubicacion_id: ubicacion.id,
			estante_nombre: ubicacion.estante_nombre,
			qr_valor: ubicacion.qr_valor,
			fila: ubicacion.fila,
			columna: ubicacion.columna
		};

		// When the product-locations card is visible the user is picking a
		// location for the already-scanned product: close the modal and run the
		// same finalize path as handleSelectLocation / handleSectorScan.
		if (showLocationsCard && scannedBarcodePending) {
			showLocationModal = false;
			void finalizeLocationSelection(anchored, scannedBarcodePending);
			return;
		}

		anchoredLocation.set(anchored);
		clearScannedProduct();
		showGreenFlash(`Ubicación anclada: ${ubicacion.estante_nombre} ${ubicacion.qr_valor}`);
		showLocationModal = false;
	}

	function closeModal() {
		showLocationModal = false;
	}

	function statusMessage(state: string): string {
		switch (state) {
			case 'idle':
				return 'Esperando cámara...';
			case 'scanning':
				return 'Cámara activa — apunte a un código';
			case 'paused':
				return 'Cámara pausada';
			default:
				return cameraError || 'Error de cámara';
		}
	}
</script>

<div class="scanner-page">
	<div class="scanner-page__viewfinder">
		<Scanner bind:this={scannerRef} onScan={handleScan} onError={handleError} />

		{#if greenFlash}
			<div class="flash flash--green" transition:fade={{ duration: 150 }}>
				{greenFlash}
			</div>
		{/if}

		{#if errorFlash}
			<div class="flash flash--red" transition:fade={{ duration: 150 }}>
				{errorFlash}
			</div>
		{/if}
	</div>

	<div class="scanner-page__status" class:scanner-page__status--error={$scannerState === 'error'}>
		{statusMessage($scannerState)}
	</div>

	{#if lastScan}
		<div class="scanner-page__last-scan">
			Escaneado: {lastScan.text} ({lastScan.format})
		</div>
	{/if}

	{#if $sessionStore && !$sessionStore.usuario.is_admin && $sessionStore.depositos.length > 0}
		<div class="scanner-page__depositos">
			<span>Depósitos:</span>
			<span class="deposito-names">
				{$sessionStore.depositos.map((d) => d.deposito_nombre).join(', ')}
			</span>
		</div>
	{/if}

	<div class="scanner-page__location" class:scanner-page__location--anchored={$anchoredLocation}>
		{#if $anchoredLocation}
			<span class="location-pin">📍</span>
			<span class="location-text">
				{$anchoredLocation.estante_nombre} — F{$anchoredLocation.fila}-C{$anchoredLocation.columna}
			</span>
			<button
				type="button"
				class="scanner-page__button scanner-page__button--small"
				onclick={clearAnchoredLocation}
			>
				Quitar
			</button>
		{:else}
			<span class="location-text">Sin ubicación anclada</span>
		{/if}
	</div>

	{#if showLocationsCard}
		<ProductLocationsCard
			product={locationsProduct
				? { sku: locationsProduct.sku, descripcion: locationsProduct.descripcion, stock_total: locationsProduct.stock_total }
				: { sku: scannedBarcodePending, descripcion: '…', stock_total: 0 }}
			locations={locationsList}
			loading={locationsLoading}
			onSelectLocation={handleSelectLocation}
			onCancel={handleCancelLocations}
		/>
	{/if}

	{#if scannedProduct}
		<ProductCard
			product={scannedProduct}
			{stockTotal}
			{quantity}
			{mode}
			{isSaving}
			onQuantityChange={handleQuantityChange}
			onModeChange={handleModeChange}
			onSave={handleSave}
			onClose={handleClose}
		/>
	{/if}

	<div class="scanner-page__controls">
		{#if $scannerState === 'scanning' || $scannerState === 'paused'}
			<button type="button" class="scanner-page__button" onclick={togglePause}>
				{$scannerState === 'scanning' ? 'Pausar' : 'Reanudar'}
			</button>
		{/if}

		<button type="button" class="scanner-page__button" onclick={openLocationModal}>
			Cambiar ubicación
		</button>

		{#if $scannerState === 'error'}
			<button
				type="button"
				class="scanner-page__button scanner-page__button--primary"
				onclick={retryCamera}
			>
				Reintentar cámara
			</button>
		{/if}
	</div>
</div>

{#if showLocationModal}
	<div class="modal" role="dialog" aria-modal="true" aria-label="Seleccionar ubicación">
		<div class="modal__content">
			<h2>Seleccionar ubicación</h2>
			{#if estantes.length === 0}
				<p>Cargando estantes...</p>
			{:else}
			<label class="modal__field">
				Depósito
				<select value={selectedDepositoId ?? ''} onchange={handleDepositoChange}>
					{#if $sessionStore?.usuario.is_admin}
						<option value="">Todos</option>
					{/if}
					{#each depositos as deposito}
						<option value={deposito.id}>{deposito.nombre}</option>
					{/each}
				</select>
			</label>

			<label class="modal__field">
				Estante
				<select value={selectedEstanteId ?? ''} onchange={handleEstanteChange}>
					{#each estantes as estante}
						<option value={estante.id}>{estante.nombre}</option>
					{/each}
				</select>
			</label>

				<label class="modal__field">
					Ubicación
					<select
						disabled={loadingLocations || ubicaciones.length === 0}
						onchange={handleUbicacionChange}
					>
						{#if loadingLocations}
							<option value="">Cargando...</option>
						{:else}
							<option value="" disabled selected>Seleccione una ubicación</option>
							{#each ubicaciones as u}
								<option value={u.id}
									>{u.qr_valor}{u.producto_sku
										? ` — OCUPADA: ${u.producto_sku} (${u.stock_actual} u.)`
										: ''}</option
								>
							{/each}
						{/if}
					</select>
				</label>
			{/if}

			<div class="modal__actions">
				<button type="button" class="scanner-page__button" onclick={closeModal}>
					Cancelar
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.scanner-page {
		display: flex;
		flex-direction: column;
		height: 100%;
		gap: 0.75rem;
	}

	.scanner-page__viewfinder {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
		width: 100%;
	}

	.flash {
		position: absolute;
		left: 0;
		right: 0;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 700;
		text-align: center;
		color: #ffffff;
		z-index: 20;
	}

	.flash--green {
		top: 0;
		background-color: #16a34a;
	}

	.flash--red {
		bottom: 0;
		background-color: #dc2626;
	}

	.scanner-page__status {
		padding: 0.75rem;
		font-size: 1rem;
		font-weight: 600;
		text-align: center;
		color: #0f172a;
		background-color: #e2e8f0;
		border-radius: 0.5rem;
	}

	.scanner-page__status--error {
		color: #ffffff;
		background-color: #dc2626;
	}

	.scanner-page__last-scan {
		padding: 0.5rem 0.75rem;
		font-size: 0.9375rem;
		color: #334155;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
	}

	.scanner-page__depositos {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.875rem;
		color: #475569;
		background-color: #f8fafc;
		border-radius: 0.5rem;
	}

	.deposito-names {
		font-weight: 600;
		color: #0f172a;
	}

	.scanner-page__location {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem;
		font-size: 1rem;
		font-weight: 600;
		color: #334155;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
	}

	.scanner-page__location--anchored {
		color: #ffffff;
		background-color: #16a34a;
	}

	.location-pin {
		font-size: 1.25rem;
	}

	.location-text {
		flex: 1 1 auto;
	}

	.scanner-page__controls {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.75rem;
	}

	.scanner-page__button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		color: #334155;
		background-color: #f1f5f9;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.scanner-page__button--primary {
		color: #ffffff;
		background-color: #2563eb;
	}

	.scanner-page__button--small {
		min-height: 2.25rem;
		padding: 0.375rem 0.75rem;
		font-size: 0.875rem;
	}

	.modal {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		background-color: rgba(15, 23, 42, 0.6);
		z-index: 50;
	}

	.modal__content {
		width: 100%;
		max-width: 24rem;
		padding: 1.25rem;
		background-color: #ffffff;
		border-radius: 0.75rem;
	}

	.modal__field {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-top: 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.modal__field select {
		min-height: 3rem;
		padding: 0.5rem;
		font-size: 1rem;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
	}

	.modal__actions {
		display: flex;
		justify-content: flex-end;
		margin-top: 1.25rem;
	}
</style>
