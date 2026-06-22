<script lang="ts">
	import Scanner from '$lib/components/Scanner.svelte';
	import { scannerState, anchoredLocation, type AnchoredLocation } from '$lib/stores/scanner';
	import { listEstantes, getEstanteUbicaciones } from '$lib/api/client';
	import type { Estante, Ubicacion } from '$lib/api/client';

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

	let showLocationModal = $state(false);
	let estantes = $state<Estante[]>([]);
	let selectedEstanteId = $state<number | null>(null);
	let ubicaciones = $state<Ubicacion[]>([]);
	let loadingLocations = $state(false);

	function handleScan(decodedText: string, formatName: string) {
		lastScan = { text: decodedText, format: formatName };
		console.log('[Scanner] scanned', formatName, decodedText);
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

	function openLocationModal() {
		showLocationModal = true;
		if (estantes.length === 0) loadEstantes();
	}

	async function loadEstantes() {
		try {
			const rows = await listEstantes();
			estantes = rows.filter((e) => !e.deleted_at);
			if (estantes.length > 0 && selectedEstanteId == null) {
				selectedEstanteId = estantes[0].id;
				await loadUbicaciones();
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
		anchoredLocation.set(anchored);
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
	</div>

	<div class="scanner-page__status" class:scanner-page__status--error={$scannerState === 'error'}>
		{statusMessage($scannerState)}
	</div>

	{#if lastScan}
		<div class="scanner-page__last-scan">
			Escaneado: {lastScan.text} ({lastScan.format})
		</div>
	{/if}

	<div class="scanner-page__location">
		{#if $anchoredLocation}
			<span>Ubicación: {$anchoredLocation.qr_valor}</span>
		{:else}
			<span>Sin ubicación anclada</span>
		{/if}
	</div>

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
								<option value={u.id}>{u.qr_valor}</option>
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
		flex: 1 1 auto;
		min-height: 0;
		width: 100%;
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

	.scanner-page__location {
		padding: 0.5rem 0.75rem;
		font-size: 1rem;
		font-weight: 600;
		color: #0f172a;
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
