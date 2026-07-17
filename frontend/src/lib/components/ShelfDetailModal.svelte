<script lang="ts">
	import { tick } from 'svelte';
	import LocationCell from './LocationCell.svelte';
	import type { Estante, Ubicacion } from '$lib/api/client';

	interface Props {
		estante: Estante & { ubicaciones: Ubicacion[] };
		onClose: () => void;
	}

	let { estante, onClose }: Props = $props();
	let visible = $state(false);

	$effect(() => {
		tick().then(() => {
			visible = true;
		});
	});

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeyDown} />

<div class="modal-backdrop" class:modal-backdrop--visible={visible}>
	<button
		type="button"
		class="modal-backdrop__close"
		onclick={onClose}
		aria-label="Cerrar vista completa"
		tabindex="-1"
	></button>
	<div
		class="modal"
		class:modal--visible={visible}
		role="dialog"
		aria-modal="true"
		aria-label={`Vista completa de ${estante.nombre}`}
	>
		<header class="modal__header">
			<div class="modal__heading">
				<h2 class="modal__title">{estante.nombre}</h2>
				<span class="modal__dims">{estante.filas}×{estante.columnas}</span>
			</div>
			<button
				type="button"
				class="modal__close"
				onclick={onClose}
				aria-label="Cerrar vista completa"
			>
				✕
			</button>
		</header>

		<div class="modal__body">
			<div
				class="modal__grid"
				style="--cols: {estante.columnas}; --rows: {estante.filas};"
			>
				{#each estante.ubicaciones as ubicacion (ubicacion.id)}
					<LocationCell {ubicacion} interactive={false} />
				{/each}
			</div>
		</div>

		<footer class="modal__footer">
			<p class="modal__note">Cerrá para interactuar con las ubicaciones</p>
		</footer>
	</div>
</div>

<style>
	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 100;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		background-color: rgba(15, 23, 42, 0.55);
		opacity: 0;
		transition: opacity 0.25s ease;
	}

	.modal-backdrop--visible {
		opacity: 1;
	}

	.modal-backdrop__close {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		padding: 0;
		margin: 0;
		border: none;
		background-color: transparent;
		cursor: default;
		z-index: 0;
	}

	.modal {
		position: relative;
		z-index: 1;
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 90vh;
		max-width: 100%;
		background-color: #ffffff;
		border-top-left-radius: 1rem;
		border-top-right-radius: 1rem;
		box-shadow: 0 -8px 30px rgba(15, 23, 42, 0.25);
		transform: translateY(100%);
		transition: transform 0.3s ease-out;
		overflow: hidden;
		padding-bottom: env(safe-area-inset-bottom);
	}

	.modal--visible {
		transform: translateY(0);
	}

	.modal__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 1rem;
		padding-top: max(1rem, env(safe-area-inset-top));
		border-bottom: 1px solid #e2e8f0;
		flex-shrink: 0;
	}

	.modal__heading {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		min-width: 0;
	}

	.modal__title {
		margin: 0;
		font-size: 1.25rem;
		font-weight: 800;
		color: #0f172a;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.modal__dims {
		flex-shrink: 0;
		padding: 0.25rem 0.5rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #64748b;
		background-color: #f1f5f9;
		border-radius: 0.375rem;
	}

	.modal__close {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 3rem;
		height: 3rem;
		font-size: 1.25rem;
		line-height: 1;
		color: #64748b;
		background-color: transparent;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.modal__close:active {
		background-color: #f1f5f9;
	}

	.modal__body {
		flex: 1 1 auto;
		overflow: auto;
		padding: 1rem;
		-webkit-overflow-scrolling: touch;
	}

	.modal__grid {
		display: grid;
		grid-template-columns: repeat(var(--cols), minmax(80px, 1fr));
		grid-template-rows: repeat(var(--rows), minmax(80px, 1fr));
		gap: 0.5rem;
		width: 100%;
		min-width: 0;
	}

	.modal__footer {
		flex-shrink: 0;
		padding: 0.75rem 1rem;
		padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
		border-top: 1px solid #e2e8f0;
		text-align: center;
	}

	.modal__note {
		margin: 0;
		font-size: 0.875rem;
		color: #64748b;
	}

	@media (min-width: 768px) {
		.modal-backdrop {
			align-items: center;
			padding: 1rem;
		}

		.modal {
			width: 90vw;
			max-width: 64rem;
			height: 90vh;
			border-radius: 1rem;
			box-shadow: 0 20px 50px rgba(15, 23, 42, 0.3);
			transform: scale(0.96);
			opacity: 0;
			transition: transform 0.25s ease-out, opacity 0.25s ease;
		}

		.modal--visible {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
