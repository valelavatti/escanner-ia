<script lang="ts">
	import { goto } from '$app/navigation';
	import { importExcel, ApiError, type ImportSummary } from '$lib/api/client';
	import { sessionStore } from '$lib/stores/session';

	$effect(() => {
		if ($sessionStore && !$sessionStore.usuario.is_admin) {
			goto('/admin/estantes');
		}
	});

	let file = $state<File | null>(null);
	let strategy = $state<'error' | 'skip' | 'overwrite'>('error');
	let isUploading = $state(false);
	let summary = $state<ImportSummary | null>(null);
	let errorMessage = $state<string | null>(null);
	let fileInput = $state<HTMLInputElement | null>(null);

	const strategyLabels: Record<typeof strategy, string> = {
		error: 'Error (abortar)',
		skip: 'Saltear (mantener existentes)',
		overwrite: 'Sobrescribir (reemplazar)'
	};

	function isExcelFile(name: string): boolean {
		return name.toLowerCase().endsWith('.xlsx') || name.toLowerCase().endsWith('.xls');
	}

	function handleFileSelected(selected: File | null) {
		if (selected && !isExcelFile(selected.name)) {
			errorMessage = 'Solo se permiten archivos .xlsx o .xls';
			file = null;
			return;
		}
		file = selected;
		summary = null;
		errorMessage = null;
	}

	function handleInputChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		handleFileSelected(input.files?.[0] ?? null);
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		const dropped = event.dataTransfer?.files?.[0] ?? null;
		handleFileSelected(dropped);
	}

	function handleDragOver(event: DragEvent) {
		event.preventDefault();
	}

	function openFilePicker() {
		fileInput?.click();
	}

	function formatValidationError(err: ApiError): string {
		const detail = err.body && typeof err.body === 'object' && 'detail' in err.body ? err.body.detail : undefined;
		if (!detail || typeof detail !== 'object') {
			return err.message;
		}

		if ('missing_columns' in detail && Array.isArray(detail.missing_columns) && detail.missing_columns.length > 0) {
			return `Faltan columnas: ${detail.missing_columns.join(', ')}`;
		}

		if ('duplicate_skus' in detail && Array.isArray(detail.duplicate_skus) && detail.duplicate_skus.length > 0) {
			const count = detail.duplicate_skus.length;
			const sample = detail.duplicate_skus.slice(0, 5).join(', ');
			const more = count > 5 ? ` (y ${count - 5} más)` : '';
			return `${count} SKU(s) ya existen en la base de datos. Use la estrategia "Saltear" o "Sobrescribir" para reimportar. Ejemplos: ${sample}${more}`;
		}

		if ('row_errors' in detail && Array.isArray(detail.row_errors) && detail.row_errors.length > 0) {
			return `Errores de validación en filas: ${detail.row_errors
				.map((e: { row: number; sku?: string | null; message: string }) => `fila ${e.row} (${e.sku ?? '-'}): ${e.message}`)
				.join('; ')}`;
		}

		if ('error' in detail && typeof detail.error === 'string' && detail.error) {
			return detail.error;
		}
		return err.message;
	}

	async function handleUpload() {
		if (!file) return;

		isUploading = true;
		summary = null;
		errorMessage = null;

		try {
			summary = await importExcel(file, strategy);
		} catch (err) {
			if (err instanceof ApiError && err.status === 400) {
				errorMessage = formatValidationError(err);
			} else if (err instanceof TypeError || (err instanceof Error && err.message.includes('fetch'))) {
				errorMessage = 'Error de conexión';
			} else if (err instanceof Error) {
				errorMessage = err.message;
			} else {
				errorMessage = 'Error desconocido';
			}
		} finally {
			isUploading = false;
		}
	}
</script>

<section class="import-page">
	<h1>Importar productos</h1>
	<p class="subtitle">Suba el Excel con el catálogo de productos.</p>

	<div
		class="drop-zone"
		role="button"
		tabindex="0"
		aria-label="Zona para soltar archivo Excel"
		onclick={openFilePicker}
		onkeydown={(e) => e.key === 'Enter' && openFilePicker()}
		ondrop={handleDrop}
		ondragover={handleDragOver}
	>
		{#if file}
			<span class="drop-zone__file">{file.name}</span>
			<span class="drop-zone__hint">Toca para cambiar el archivo</span>
		{:else}
			<span class="drop-zone__main">Arrastre un Excel aquí o toque para seleccionar</span>
			<span class="drop-zone__hint">.xlsx / .xls</span>
		{/if}
		<input
			bind:this={fileInput}
			type="file"
			accept=".xlsx,.xls"
			class="drop-zone__input"
			onchange={handleInputChange}
		/>
	</div>

	<label class="strategy-label" for="strategy">Estrategia ante duplicados</label>
	<select id="strategy" bind:value={strategy} class="strategy-select" disabled={isUploading}>
		<option value="error">{strategyLabels.error}</option>
		<option value="skip">{strategyLabels.skip}</option>
		<option value="overwrite">{strategyLabels.overwrite}</option>
	</select>

	<button
		class="upload-button"
		onclick={handleUpload}
		disabled={!file || isUploading}
	>
		{#if isUploading}
			Importando…
		{:else}
			Importar
		{/if}
	</button>

	{#if errorMessage}
		<div class="alert alert--error" role="alert">
			{errorMessage}
		</div>
	{/if}

	{#if summary}
		<div class="results">
			<h2>Resultado</h2>
			<div class="summary-grid">
				<div class="summary-card">
					<span class="summary-card__value">{summary.total_rows}</span>
					<span class="summary-card__label">Filas totales</span>
				</div>
				<div class="summary-card">
					<span class="summary-card__value">{summary.imported}</span>
					<span class="summary-card__label">Importados</span>
				</div>
				{#if summary.skipped > 0}
					<div class="summary-card">
						<span class="summary-card__value">{summary.skipped}</span>
						<span class="summary-card__label">Saltados (existentes)</span>
					</div>
				{/if}
				{#if summary.skipped_no_barcode > 0}
					<div class="summary-card">
						<span class="summary-card__value">{summary.skipped_no_barcode}</span>
						<span class="summary-card__label">Sin código de barra</span>
					</div>
				{/if}
				{#if summary.skipped_barcode_conflicts > 0}
					<div class="summary-card">
						<span class="summary-card__value">{summary.skipped_barcode_conflicts}</span>
						<span class="summary-card__label">Conflictos de código</span>
					</div>
				{/if}
				{#if summary.overwritten > 0}
					<div class="summary-card">
						<span class="summary-card__value">{summary.overwritten}</span>
						<span class="summary-card__label">Reemplazados</span>
					</div>
				{/if}
			</div>

			{#if summary.imported > 0}
				<div class="alert alert--success" role="status">
					Se importaron {summary.imported} productos exitosamente.
				</div>
			{/if}

			{#if summary.barcode_conflicts.length > 0}
				<div class="detail-section">
					<h3>Conflictos de código de barra</h3>
					<ul class="detail-list">
						{#each summary.barcode_conflicts as conflict}
							<li>
								<strong>SKU(s): {conflict.sku ?? '-'}</strong>
								<span>{conflict.message}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if summary.errors.length > 0}
				<div class="detail-section">
					<h3>Errores por fila</h3>
					<ul class="detail-list">
						{#each summary.errors as error}
							<li>
								<strong>Fila {error.row}</strong>
								<span>SKU: {error.sku ?? '-'}</span>
								<span>{error.message}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	.import-page {
		padding: 1rem;
		max-width: 48rem;
		margin: 0 auto;
	}

	h1 {
		font-size: 1.5rem;
		margin: 0 0 0.25rem;
	}

	.subtitle {
		color: #475569;
		margin: 0 0 1.5rem;
	}

	.drop-zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		min-height: 10rem;
		padding: 1.5rem;
		border: 2px dashed #94a3b8;
		border-radius: 0.75rem;
		background-color: #f8fafc;
		text-align: center;
		cursor: pointer;
		touch-action: manipulation;
	}

	.drop-zone:focus-visible {
		outline: 3px solid #2563eb;
		outline-offset: 2px;
	}

	.drop-zone__main {
		font-size: 1.125rem;
		font-weight: 600;
		color: #0f172a;
	}

	.drop-zone__file {
		font-size: 1.125rem;
		font-weight: 600;
		color: #0f172a;
		word-break: break-all;
	}

	.drop-zone__hint {
		font-size: 0.875rem;
		color: #64748b;
	}

	.drop-zone__input {
		display: none;
	}

	.strategy-label {
		display: block;
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
		font-weight: 600;
	}

	.strategy-select {
		width: 100%;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		background-color: #ffffff;
		cursor: pointer;
	}

	.upload-button {
		width: 100%;
		min-height: 3rem;
		margin-top: 1.5rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		color: #ffffff;
		background-color: #2563eb;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.upload-button:disabled {
		background-color: #93c5fd;
		cursor: not-allowed;
	}

	.upload-button:not(:disabled):active {
		background-color: #1d4ed8;
	}

	.alert {
		margin-top: 1rem;
		padding: 1rem;
		border-radius: 0.5rem;
		font-weight: 500;
	}

	.alert--error {
		background-color: #fee2e2;
		color: #991b1b;
	}

	.alert--success {
		background-color: #dcfce7;
		color: #166534;
	}

	.results {
		margin-top: 1.5rem;
	}

	.results h2 {
		font-size: 1.25rem;
		margin: 0 0 1rem;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}

	@media (min-width: 640px) {
		.summary-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	.summary-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		border: 1px solid #e2e8f0;
		border-radius: 0.5rem;
		background-color: #ffffff;
	}

	.summary-card__value {
		font-size: 1.75rem;
		font-weight: 700;
		color: #0f172a;
	}

	.summary-card__label {
		font-size: 0.875rem;
		color: #64748b;
		text-align: center;
	}

	.detail-section {
		margin-top: 1.5rem;
	}

	.detail-section h3 {
		font-size: 1rem;
		margin: 0 0 0.5rem;
	}

	.detail-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.detail-list li {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		padding: 0.75rem;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
		font-size: 0.875rem;
	}
</style>
