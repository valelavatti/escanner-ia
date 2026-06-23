<script lang="ts">
	import type { ProductSearchResult } from '$lib/api/client';

	interface Props {
		open: boolean;
		title: string;
		searching: boolean;
		selecting: boolean;
		results: ProductSearchResult[];
		onclose: () => void;
		onsearch: (query: string) => void;
		onselect: (product: ProductSearchResult) => void;
	}

	let { open, title, searching, selecting, results, onclose, onsearch, onselect }: Props = $props();
	let query = $state('');

	function handleSearch() {
		const trimmed = query.trim();
		if (trimmed.length < 2) {
			return;
		}
		onsearch(trimmed);
	}

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			event.preventDefault();
			handleSearch();
		}
	}

	function handleClose() {
		query = '';
		onclose();
	}
</script>

{#if open}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={handleClose}
		onkeydown={(e) => e.key === 'Escape' && handleClose()}
	>
		<div
			class="modal"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="search-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="search-title">{title}</h2>

			<label class="field-label" for="product-search">Buscar por SKU o código de barra</label>
			<div class="search-row">
				<input
					id="product-search"
					class="field-input"
					type="text"
					bind:value={query}
					placeholder="Ej: 7791234567890"
					disabled={selecting}
					onkeydown={handleKeyDown}
				/>
				<button
					type="button"
					class="button button--secondary"
					onclick={handleSearch}
					disabled={searching || selecting}
				>
					{searching ? '…' : 'Buscar'}
				</button>
			</div>

			{#if results.length > 0}
				<ul class="product-list" role="listbox" aria-label="Resultados de búsqueda">
					{#each results as product (product.sku)}
						<li class="product-item">
							<div class="product-item__info">
								<strong>{product.sku}</strong>
								<span>{product.descripcion}</span>
								<span class="product-item__barcode">{product.codigo_de_barra}</span>
							</div>
							<button
								type="button"
								class="button button--small button--primary"
								onclick={() => onselect(product)}
								disabled={selecting}
							>
								{selecting ? '…' : 'Seleccionar'}
							</button>
						</li>
					{/each}
				</ul>
			{:else if query.trim().length >= 2 && !searching}
				<p class="empty">No se encontraron productos.</p>
			{/if}

			<div class="modal-actions">
				<button
					type="button"
					class="button button--secondary"
					onclick={handleClose}
					disabled={selecting}
				>
					Cancelar
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
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

	.modal h2 {
		font-size: 1.25rem;
		margin: 0 0 1rem;
		color: #0f172a;
	}

	.field-label {
		display: block;
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

	.search-row {
		display: flex;
		gap: 0.5rem;
	}

	.search-row .field-input {
		flex: 1;
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

	.button--small {
		min-height: 2.25rem;
		padding: 0.375rem 0.75rem;
		font-size: 0.875rem;
	}

	.modal-actions {
		display: flex;
		gap: 0.75rem;
		margin-top: 1.5rem;
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

	.empty {
		margin: 1rem 0 0;
		color: #64748b;
		font-size: 0.9375rem;
	}
</style>
