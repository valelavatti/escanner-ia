import { writable } from 'svelte/store';

export interface AnchoredLocation {
	ubicacion_id: number;
	estante_nombre: string;
	qr_valor: string;
	fila: number;
	columna: number;
}

export const anchoredLocation = writable<AnchoredLocation | null>(null);
export const scannerState = writable<'idle' | 'scanning' | 'paused' | 'error'>('idle');
