<script lang="ts">
	import { tick } from 'svelte';
	import { browser } from '$app/environment';
	import {
		downloadEstanteQRsZip,
		getEstanteQRPrintSheet,
		ApiError,
		type Estante
	} from '$lib/api/client';

	interface Props {
		estante: Estante;
		onClose: () => void;
	}

	let { estante, onClose }: Props = $props();

	let perPage = $state(4);
	let qrSize = $state<'small' | 'medium' | 'large'>('medium');
	let isGenerating = $state(false);
	let isDownloading = $state(false);
	let error = $state<string | null>(null);
	let visible = $state(false);

	const sizeOptions: { value: 'small' | 'medium' | 'large'; label: string; px: number }[] = [
		{ value: 'small', label: 'Pequeño (150 px)', px: 150 },
		{ value: 'medium', label: 'Mediano (200 px)', px: 200 },
		{ value: 'large', label: 'Grande (300 px)', px: 300 }
	];

	const perPageOptions = [1, 2, 4, 6, 8, 9];

	const sizeInPx = $derived(sizeOptions.find((o) => o.value === qrSize)?.px ?? 200);

	const grid = $derived(getGrid(perPage));

	function getGrid(per: number): { cols: number; rows: number } {
		switch (per) {
			case 1:
				return { cols: 1, rows: 1 };
			case 2:
				return { cols: 1, rows: 2 };
			case 4:
				return { cols: 2, rows: 2 };
			case 6:
				return { cols: 2, rows: 3 };
			case 8:
				return { cols: 2, rows: 4 };
			case 9:
				return { cols: 3, rows: 3 };
			default:
				return { cols: 2, rows: 2 };
		}
	}

	function getErrorMessage(err: unknown): string {
		if (err instanceof ApiError) {
			if (err.status === 404) return 'El estante o sus ubicaciones ya no existen.';
			if (err.status === 401) return 'Tu sesión expiró. Volvé a iniciar sesión.';
			return err.message;
		}
		return err instanceof Error ? err.message : 'Error inesperado. Intentá de nuevo.';
	}

	async function handleGenerate() {
		if (isGenerating || isDownloading) return;
		isGenerating = true;
		error = null;

		try {
			const blob = await getEstanteQRPrintSheet(estante.id, perPage, sizeInPx);
			const blobUrl = URL.createObjectURL(blob);

			if (browser) {
				const printWindow = window.open('', '_blank');
				if (printWindow) {
					printWindow.document.write(`
						<!DOCTYPE html>
						<html lang="es">
							<head>
								<meta charset="utf-8" />
								<title>Imprimir QRs — ${estante.nombre}</title>
								<style>
									* { box-sizing: border-box; }
									body { margin: 0; padding: 0; background: #fff; }
									img { display: block; width: 100%; height: auto; }
									@media print {
										body { margin: 0; }
										img { page-break-inside: avoid; }
									}
								</style>
							</head>
							<body>
								<img src="${blobUrl}" alt="Hoja A4 con códigos QR" onload="setTimeout(() => window.print(), 100)" />
							</body>
						</html>
					`);
					printWindow.document.close();
				} else {
					// Fallback if popup blocked
					window.open(blobUrl, '_blank');
				}
			}
		} catch (err) {
			error = getErrorMessage(err);
		} finally {
			isGenerating = false;
		}
	}

	async function handleDownload() {
		if (isGenerating || isDownloading) return;
		isDownloading = true;
		error = null;

		try {
			const blob = await downloadEstanteQRsZip(estante.id);
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `qr_${estante.nombre}.zip`;
			document.body.appendChild(anchor);
			anchor.click();
			anchor.remove();
			URL.revokeObjectURL(url);
		} catch (err) {
			error = getErrorMessage(err);
		} finally {
			isDownloading = false;
		}
	}

	function handleClose() {
		error = null;
		onClose();
	}

	$effect(() => {
		tick().then(() => {
			visible = true;
		});
	});
</script>

<div
	class="qr-modal-backdrop"
	role="presentation"
	tabindex="-1"
	onclick={handleClose}
	onkeydown={(e) => e.key === 'Escape' && handleClose()}
>
	<div
		class="qr-modal"
		class:qr-modal--visible={visible}
		role="dialog"
		tabindex="0"
		aria-modal="true"
		aria-labelledby="qr-modal-title"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
	>
		<button
			type="button"
			class="qr-modal__close"
			onclick={handleClose}
			aria-label="Cerrar modal"
		>
			✕
		</button>

		<h2 id="qr-modal-title" class="qr-modal__title">Imprimir QRs de {estante.nombre}</h2>
		<p class="qr-modal__info">
			{estante.filas} × {estante.columnas} = {estante.filas * estante.columnas} ubicaciones
		</p>

		<div class="qr-modal__fields">
			<label class="field-label" for="qr-per-page">QRs por hoja</label>
			<select
				id="qr-per-page"
				class="field-input field-input--select"
				bind:value={perPage}
				disabled={isGenerating || isDownloading}
			>
				{#each perPageOptions as option}
					<option value={option}>{option}</option>
				{/each}
			</select>

			<label class="field-label" for="qr-size">Tamaño</label>
			<select
				id="qr-size"
				class="field-input field-input--select"
				bind:value={qrSize}
				disabled={isGenerating || isDownloading}
			>
				{#each sizeOptions as option}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</div>

		<div class="qr-preview">
			<div class="qr-preview__page">
				<div
					class="qr-preview__grid"
					style="grid-template-columns: repeat({grid.cols}, 1fr); grid-template-rows: repeat({grid.rows}, 1fr);"
				>
					{#each { length: perPage } as _, index (index)}
						<div class="qr-preview__cell">
							<div class="qr-preview__qr"></div>
						</div>
					{/each}
				</div>
			</div>
			<p class="qr-preview__hint">
				Vista previa: {grid.cols} × {grid.rows} · {sizeInPx} px
			</p>
		</div>

		{#if error}
			<p class="qr-modal__error" role="alert">{error}</p>
		{/if}

		<div class="qr-modal__actions">
			<button
				type="button"
				class="button button--primary"
				onclick={handleGenerate}
				disabled={isGenerating || isDownloading}
			>
				{isGenerating ? 'Generando…' : 'Generar e imprimir'}
			</button>
			<button
				type="button"
				class="button button--secondary"
				onclick={handleDownload}
				disabled={isGenerating || isDownloading}
			>
				{isDownloading ? 'Descargando…' : 'Descargar ZIP'}
			</button>
			<button
				type="button"
				class="button button--ghost"
				onclick={handleClose}
				disabled={isGenerating || isDownloading}
			>
				Cerrar
			</button>
		</div>
	</div>
</div>

<style>
	.qr-modal-backdrop {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		padding: 0;
		background-color: rgba(15, 23, 42, 0.6);
		z-index: 50;
		overflow-y: auto;
	}

	.qr-modal {
		position: relative;
		width: 100%;
		max-width: 28rem;
		padding: 1.25rem;
		padding-bottom: max(1.25rem, env(safe-area-inset-bottom));
		background-color: #ffffff;
		border-top-left-radius: 1rem;
		border-top-right-radius: 1rem;
		box-shadow: 0 -4px 20px rgba(15, 23, 42, 0.15);
		transform: translateY(100%);
		transition: transform 0.25s ease-out;
	}

	.qr-modal--visible {
		transform: translateY(0);
	}

	.qr-modal__close {
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

	.qr-modal__close:active {
		background-color: #f1f5f9;
	}

	.qr-modal__title {
		margin: 0 2.5rem 0.25rem 0;
		font-size: 1.125rem;
		font-weight: 700;
		color: #0f172a;
	}

	.qr-modal__info {
		margin: 0 0 1rem;
		font-size: 0.875rem;
		color: #64748b;
	}

	.qr-modal__fields {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.field-label {
		display: block;
		margin-top: 0.75rem;
		margin-bottom: 0.375rem;
		font-weight: 600;
		font-size: 0.875rem;
		color: #334155;
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

	.field-input--select {
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%23475569' viewBox='0 0 16 16'%3E%3Cpath d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 0.75rem center;
		padding-right: 2.5rem;
	}

	.qr-preview {
		margin-top: 1rem;
	}

	.qr-preview__page {
		aspect-ratio: 210 / 297;
		max-width: 12rem;
		margin: 0 auto;
		padding: 0.75rem;
		background-color: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 0.5rem;
		box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
	}

	.qr-preview__grid {
		display: grid;
		gap: 0.375rem;
		width: 100%;
		height: 100%;
	}

	.qr-preview__cell {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.25rem;
		background-color: #f8fafc;
		border-radius: 0.25rem;
	}

	.qr-preview__qr {
		width: 100%;
		height: 100%;
		max-width: 2.5rem;
		max-height: 2.5rem;
		background-color: #e2e8f0;
		border-radius: 0.25rem;
	}

	.qr-preview__hint {
		margin: 0.5rem 0 0;
		font-size: 0.875rem;
		text-align: center;
		color: #64748b;
	}

	.qr-modal__error {
		margin: 1rem 0 0;
		padding: 0.625rem 0.75rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: #991b1b;
		background-color: #fee2e2;
		border-radius: 0.5rem;
	}

	.qr-modal__actions {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 1.25rem;
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
		transition: opacity 0.15s ease;
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

	.button--ghost {
		color: #64748b;
		background-color: transparent;
	}

	.button--ghost:not(:disabled):active {
		background-color: #f1f5f9;
	}

	@media (min-width: 640px) {
		.qr-modal-backdrop {
			align-items: flex-start;
			padding: 1rem;
		}

		.qr-modal {
			margin-top: 2rem;
			border-radius: 0.75rem;
			box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
			transform: translateY(-1rem);
			opacity: 0;
			transition: transform 0.25s ease-out, opacity 0.25s ease-out;
		}

		.qr-modal--visible {
			transform: translateY(0);
			opacity: 1;
		}

		.qr-modal__actions {
			flex-direction: row;
		}

		.qr-modal__actions .button {
			flex: 1;
		}
	}
</style>
