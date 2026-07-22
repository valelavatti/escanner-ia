import { writable } from 'svelte/store';

export interface AnchoredLocation {
	ubicacion_id: number;
	estante_nombre: string;
	qr_valor: string;
	fila: number;
	columna: number;
	fila_label?: string;
	columna_label?: string;
}

export const anchoredLocation = writable<AnchoredLocation | null>(null);
export const scannerState = writable<'idle' | 'scanning' | 'paused' | 'error'>('idle');
