<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { scannerState } from '$lib/stores/scanner';

	interface Props {
		onScan: (decodedText: string, formatName: string) => void;
		onError: (error: string) => void;
	}

	let { onScan, onError }: Props = $props();

	const readerId = 'reader-' + Math.random().toString(36).slice(2);
	let readerEl: HTMLDivElement | undefined = $state(undefined);
	let scannerObj: any = null;

	let torchSupported = $state(false);
	let zoomSupported = $state(false);
	let torchOn = $state(false);

	let zoomMin = $state(1);
	let zoomMax = $state(10);
	let zoomStep = $state(0.5);
	let zoomValue = $state(1);

	export function pause() {
		if (!scannerObj) return;
		try {
			scannerObj.pause(true);
			scannerState.set('paused');
		} catch {
			// ignore
		}
	}

	export function resume() {
		if (!scannerObj) return;
		try {
			scannerObj.resume();
			scannerState.set('scanning');
		} catch {
			// ignore
		}
	}

	export function stop() {
		return cleanup();
	}

	export function start() {
		return startScanner();
	}

	onMount(() => {
		if (browser) {
			startScanner();
		}
	});

	onDestroy(() => {
		cleanup();
	});

	async function startScanner() {
		if (!browser || !readerEl) return;

		await cleanup();
		scannerState.set('idle');

		try {
			const mod: any = await import('html5-qrcode');
			const Html5Qrcode = mod.Html5Qrcode;

			scannerObj = new Html5Qrcode(readerId, {
				formatsToSupport: [
					mod.Html5QrcodeSupportedFormats.QR_CODE,
					mod.Html5QrcodeSupportedFormats.EAN_13,
					mod.Html5QrcodeSupportedFormats.CODE_128,
					mod.Html5QrcodeSupportedFormats.UPC_A
				],
				useBarCodeDetectorIfSupported: true,
				verbose: false
			});

			const cameras = await Html5Qrcode.getCameras();
			if (!cameras || cameras.length === 0) {
				throw new Error('NO_CAMERAS');
			}

			await tryStartWithFallbacks(mod);

			detectCapabilities();
			scannerState.set('scanning');
		} catch (err) {
			const message = translateError(err);
			scannerState.set('error');
			onError(message);
		}
	}

	async function tryStartWithFallbacks(mod: any) {
		const configs = [
			{ facingMode: { exact: 'environment' } },
			{ facingMode: 'environment' },
			{ facingMode: 'user' }
		];

		let lastError: unknown = null;

		for (const cameraConfig of configs) {
			try {
				await scannerObj.start(
					cameraConfig,
					{
						fps: 10,
						qrbox: { width: 280, height: 280 },
						aspectRatio: 1,
						disableFlip: false
					},
					(decodedText: string, result: unknown) => {
						const formatName = getFormatName(result);
						onScan(decodedText, formatName);
					},
					() => {}
				);
				return;
			} catch (err) {
				lastError = err;
				const isOverconstrained =
					(err as any)?.name === 'OverconstrainedError' ||
					(typeof (err as any)?.message === 'string' &&
						(err as any).message.includes('Overconstrained'));
				if (!isOverconstrained) {
					throw err;
				}
			}
		}

		throw lastError;
	}

	function getFormatName(result: unknown): string {
		if (!result || typeof result !== 'object') return 'UNKNOWN';
		const r = result as any;
		return r?.result?.format?.formatName ?? 'UNKNOWN';
	}

	function translateError(err: unknown): string {
		if (!(err instanceof Error)) {
			return 'Error al iniciar la cámara: ' + String(err);
		}
		if (
			err.message === 'NO_CAMERAS' ||
			err.name === 'NotFoundError' ||
			err.name === 'DevicesNotFoundError'
		) {
			return 'No se encontró ninguna cámara en este dispositivo.';
		}
		if (
			err.name === 'NotAllowedError' ||
			err.name === 'PermissionDeniedError' ||
			err.name === 'SecurityError'
		) {
			return 'Permiso de cámara denegado. Habilite la cámara en la configuración del navegador.';
		}
		return 'Error al iniciar la cámara: ' + err.message;
	}

	async function cleanup() {
		if (!scannerObj) return;

		try {
			const mod: any = await import('html5-qrcode');
			const state = scannerObj.getState();
			if (
				state === mod.Html5QrcodeScannerState.SCANNING ||
				state === mod.Html5QrcodeScannerState.PAUSED
			) {
				await scannerObj.stop();
			}
		} catch {
			// ignore
		}

		try {
			scannerObj.clear();
		} catch {
			// ignore
		}

		scannerObj = null;
	}

	function detectCapabilities() {
		if (!scannerObj) return;
		try {
			const caps = scannerObj.getRunningTrackCapabilities() as MediaTrackCapabilities;
			if ('torch' in caps && caps.torch) {
				torchSupported = true;
			}
			if ('zoom' in caps && typeof caps.zoom === 'object' && caps.zoom !== null) {
				zoomSupported = true;
				const z = caps.zoom as { min?: number; max?: number; step?: number };
				zoomMin = z.min ?? 1;
				zoomMax = z.max ?? 10;
				zoomStep = z.step ?? 0.5;
				zoomValue = Math.min(Math.max(2, zoomMin), zoomMax);
			}
		} catch {
			// ignore
		}
	}

	async function toggleTorch() {
		if (!scannerObj) return;
		try {
			await scannerObj.applyVideoConstraints({
				advanced: [{ torch: !torchOn }]
			});
			torchOn = !torchOn;
		} catch {
			// ignore
		}
	}

	async function handleZoomChange(event: Event) {
		const target = event.target as HTMLInputElement;
		const value = Number(target.value);
		zoomValue = value;
		if (!scannerObj) return;
		try {
			await scannerObj.applyVideoConstraints({
				advanced: [{ zoom: value }]
			});
		} catch {
			// ignore
		}
	}
</script>

<div class="scanner">
	<div class="scanner__reader-wrapper">
		<div id={readerId} bind:this={readerEl} class="scanner__reader"></div>
	</div>

	{#if torchSupported || zoomSupported}
		<div class="scanner__camera-controls">
			{#if torchSupported}
				<button
					type="button"
					class="scanner__torch"
					class:scanner__torch--on={torchOn}
					onclick={toggleTorch}
					aria-label={torchOn ? 'Apagar linterna' : 'Encender linterna'}
				>
					{torchOn ? 'Apagar' : 'Encender'}
				</button>
			{/if}
			{#if zoomSupported}
				<label class="scanner__zoom">
					Zoom
					<input
						type="range"
						min={zoomMin}
						max={zoomMax}
						step={zoomStep}
						value={zoomValue}
						oninput={handleZoomChange}
					/>
				</label>
			{/if}
		</div>
	{/if}
</div>

<style>
	.scanner {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
	}

	.scanner__reader-wrapper {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
		width: 100%;
		aspect-ratio: 1 / 1;
		background-color: #0f172a;
		border-radius: 0.75rem;
		overflow: hidden;
	}

	.scanner__reader {
		width: 100%;
		height: 100%;
	}

	.scanner__reader :global(video) {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.scanner__camera-controls {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 0.5rem;
	}

	.scanner__torch {
		min-height: 2.75rem;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #0f172a;
		background-color: #f1f5f9;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
	}

	.scanner__torch--on {
		color: #ffffff;
		background-color: #2563eb;
	}

	.scanner__zoom {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: #f8fafc;
	}

	.scanner__zoom input {
		width: 6rem;
	}
</style>
