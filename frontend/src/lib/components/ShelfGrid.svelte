<script lang="ts">
	import LocationCell from './LocationCell.svelte';
	import type { Estante, Ubicacion } from '$lib/api/client';

	interface Props {
		estante: Estante & { ubicaciones: Ubicacion[] };
		selectedCellId?: number | null;
		onCellClick?: (ubicacion: Ubicacion) => void;
		onExpand?: (estante: Estante & { ubicaciones: Ubicacion[] }) => void;
	}

	let { estante, selectedCellId = null, onCellClick, onExpand }: Props = $props();

	const isSuelto = $derived(estante.nombre.toLowerCase().startsWith('suelto'));
</script>

<div class="shelf" class:shelf--suelto={isSuelto}>
	<div class="shelf__header">
		<h3 class="shelf__title">{estante.nombre}</h3>
		<div class="shelf__header-right">
			<span class="shelf__dims">{estante.filas}×{estante.columnas}</span>
			{#if onExpand}
				<button
					type="button"
					class="shelf__expand"
					onclick={() => onExpand(estante)}
					aria-label={`Ver completo ${estante.nombre}`}
					title="Ver completo"
				>
					⤢
				</button>
			{/if}
		</div>
	</div>
	<div
		class="shelf__grid"
		style="--cols: {estante.columnas}; --rows: {estante.filas};"
	>
		{#each estante.ubicaciones as ubicacion (ubicacion.id)}
			<LocationCell {ubicacion} isSelected={ubicacion.id === selectedCellId} onClick={onCellClick} />
		{/each}
	</div>
</div>

<style>
	.shelf {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.75rem;
		background-color: #ffffff;
		border-left: 4px solid #94a3b8;
		border-radius: 0.5rem;
		box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
		min-width: 0;
	}

	.shelf--suelto {
		border-left-color: #3b82f6;
		background-color: #eff6ff;
	}

	.shelf__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.shelf__header-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.shelf__title {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.shelf__dims {
		flex-shrink: 0;
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: #64748b;
		background-color: #f1f5f9;
		border-radius: 0.25rem;
	}

	.shelf__expand {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 3rem;
		min-height: 3rem;
		padding: 0.5rem;
		font-size: 1.125rem;
		line-height: 1;
		color: #2563eb;
		background-color: #eff6ff;
		border: 1px solid #bfdbfe;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
		transition: background-color 0.15s ease, border-color 0.15s ease;
	}

	.shelf__expand:active {
		background-color: #dbeafe;
		border-color: #93c5fd;
	}

	.shelf__grid {
		display: grid;
		grid-template-columns: repeat(var(--cols), minmax(64px, 1fr));
		grid-template-rows: repeat(var(--rows), minmax(64px, 1fr));
		gap: 0.25rem;
		width: 100%;
		min-width: 0;
		overflow-x: auto;
		overflow-x: auto;
		touch-action: pan-x;
	}
</style>
