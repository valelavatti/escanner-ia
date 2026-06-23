<script lang="ts">
	import ShelfGrid from './ShelfGrid.svelte';
	import type { Deposito, Estante, Ubicacion } from '$lib/api/client';

	interface Props {
		depositos: Deposito[];
		estantes: (Estante & { ubicaciones: Ubicacion[] })[];
		onCellClick?: (ubicacion: Ubicacion) => void;
	}

	let { depositos, estantes, onCellClick }: Props = $props();

	const sortedEstantes = $derived(
		[...estantes].sort((a, b) => a.orden_visual - b.orden_visual)
	);

	const estantesByDeposito = $derived(
		sortedEstantes.reduce<Record<number, (Estante & { ubicaciones: Ubicacion[] })[]>>((acc, estante) => {
			const depositoId = estante.deposito_id ?? -1;
			if (!acc[depositoId]) {
				acc[depositoId] = [];
			}
			acc[depositoId].push(estante);
			return acc;
		}, {})
	);

	const sortedDepositos = $derived(
		[...depositos].sort((a, b) => a.nombre.localeCompare(b.nombre))
	);

	const ungroupedEstantes = $derived(estantesByDeposito[-1] ?? []);
</script>

<div class="warehouse-map">
	{#each sortedDepositos as deposito (deposito.id)}
		<section class="deposito-section">
			<h2 class="deposito-section__title">{deposito.nombre}</h2>
			<div class="deposito-section__shelves">
				{#each estantesByDeposito[deposito.id] ?? [] as estante (estante.id)}
					<ShelfGrid {estante} onCellClick={onCellClick} />
				{/each}
			</div>
		</section>
	{/each}

	{#if ungroupedEstantes.length > 0}
		<section class="deposito-section">
			<h2 class="deposito-section__title">Sin depósito</h2>
			<div class="deposito-section__shelves">
				{#each ungroupedEstantes as estante (estante.id)}
					<ShelfGrid {estante} onCellClick={onCellClick} />
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	.warehouse-map {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.deposito-section {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.deposito-section__title {
		margin: 0;
		font-size: 1.25rem;
		font-weight: 800;
		color: #0f172a;
	}

	.deposito-section__shelves {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1rem;
	}

	@media (min-width: 768px) {
		.deposito-section__shelves {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (min-width: 1024px) {
		.deposito-section__shelves {
			grid-template-columns: repeat(3, 1fr);
		}
	}
</style>
