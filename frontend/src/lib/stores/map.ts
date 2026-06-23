import { writable } from 'svelte/store';
import type { Estante, Ubicacion } from '$lib/api/client';

export interface MapState {
	selectedCellId: number | null;
	estantes: Estante[];
	ubicaciones: Record<number, Ubicacion[]>;
}

export const mapStore = writable<MapState>({
	selectedCellId: null,
	estantes: [],
	ubicaciones: {}
});
