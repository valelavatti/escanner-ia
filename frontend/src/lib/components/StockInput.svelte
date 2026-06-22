<script lang="ts">
	interface Props {
		quantity: number;
		mode: 'alta' | 'ajuste';
		currentStock: number;
		isSaving: boolean;
		onQuantityChange: (value: number) => void;
		onModeChange: (mode: 'alta' | 'ajuste') => void;
		onSave: () => void;
		onClose: () => void;
	}

	let { quantity, mode, currentStock, isSaving, onQuantityChange, onModeChange, onSave, onClose }: Props =
		$props();

	function handleInput(event: Event) {
		const target = event.target as HTMLInputElement;
		const parsed = target.value === '' ? 0 : Number(target.value);
		onQuantityChange(Number.isFinite(parsed) && parsed >= 0 ? parsed : 0);
	}

	const resultStock = $derived(mode === 'alta' ? currentStock + quantity : quantity);
	const canSave = $derived(!isSaving && Number.isFinite(quantity) && quantity >= 0);
</script>

<div class="stock-input">
	<div class="stock-input__mode" role="group" aria-label="Tipo de movimiento">
		<button
			type="button"
			class="stock-input__mode-btn"
			class:stock-input__mode-btn--active={mode === 'alta'}
			onclick={() => onModeChange('alta')}
			disabled={isSaving}
		>
			Sumar
		</button>
		<button
			type="button"
			class="stock-input__mode-btn"
			class:stock-input__mode-btn--active={mode === 'ajuste'}
			onclick={() => onModeChange('ajuste')}
			disabled={isSaving}
		>
			Ajustar
		</button>
	</div>

	<label class="stock-input__field">
		<span class="stock-input__label">Cantidad a {mode === 'alta' ? 'sumar' : 'ajustar'}</span>
		<input
			type="number"
			inputmode="numeric"
			pattern="[0-9]*"
			min="0"
			step="1"
			value={quantity || ''}
			oninput={handleInput}
			disabled={isSaving}
			class="stock-input__quantity"
		/>
	</label>

	<div class="stock-input__preview">Stock resultante: {resultStock}</div>

	<div class="stock-input__actions">
		<button
			type="button"
			class="stock-input__save"
			onclick={onSave}
			disabled={!canSave}
		>
			{isSaving ? 'Guardando...' : 'Guardar'}
		</button>
		<button
			type="button"
			class="stock-input__close"
			onclick={onClose}
			disabled={isSaving}
		>
			Cerrar
		</button>
	</div>
</div>

<style>
	.stock-input {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.stock-input__mode {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.5rem;
	}

	.stock-input__mode-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem;
		font-size: 1rem;
		font-weight: 600;
		color: #334155;
		background-color: #f1f5f9;
		border: 2px solid transparent;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.stock-input__mode-btn--active {
		color: #ffffff;
		background-color: #2563eb;
	}

	.stock-input__mode-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.stock-input__field {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.stock-input__label {
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.stock-input__quantity {
		min-height: 3rem;
		padding: 0.75rem;
		font-size: 1.25rem;
		font-weight: 700;
		color: #0f172a;
		background-color: #ffffff;
		border: 2px solid #cbd5e1;
		border-radius: 0.5rem;
	}

	.stock-input__quantity:focus {
		outline: none;
		border-color: #2563eb;
	}

	.stock-input__preview {
		padding: 0.5rem 0.75rem;
		font-size: 1rem;
		font-weight: 700;
		text-align: center;
		color: #0f172a;
		background-color: #e0f2fe;
		border-radius: 0.5rem;
	}

	.stock-input__actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	.stock-input__save,
	.stock-input__close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 700;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.stock-input__save {
		color: #ffffff;
		background-color: #16a34a;
	}

	.stock-input__save:disabled {
		background-color: #86efac;
		cursor: not-allowed;
	}

	.stock-input__close {
		color: #334155;
		background-color: #f1f5f9;
	}

	@media (min-width: 640px) {
		.stock-input__actions {
			grid-template-columns: repeat(2, 1fr);
		}

		.stock-input__save {
			order: 2;
		}

		.stock-input__close {
			order: 1;
		}
	}
</style>
