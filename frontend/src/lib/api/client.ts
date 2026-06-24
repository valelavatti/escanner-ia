import { get } from 'svelte/store';
import { browser } from '$app/environment';
import { sessionStore, clearSession } from '$lib/stores/session';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
	status: number;
	body: unknown;

	constructor(message: string, status: number, body: unknown) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.body = body;
	}
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
	const session = get(sessionStore);
	const isFormData = options.body instanceof FormData;
	const headers: Record<string, string> = {
		Accept: 'application/json',
		...(isFormData ? {} : { 'Content-Type': 'application/json' }),
		...((options.headers as Record<string, string>) || {})
	};

	if (session?.token) {
		headers['Authorization'] = `Bearer ${session.token}`;
	}

	const response = await fetch(`${API_BASE}${path}`, {
		...options,
		headers
	});

	if (response.status === 401) {
		clearSession();
		if (browser) {
			window.location.href = '/login';
		}
		throw new Error('Sesión inválida o expirada');
	}

	if (!response.ok) {
		const body = (await response.json().catch(() => null)) as unknown;
		let message = `Error HTTP ${response.status}`;

		if (body && typeof body === 'object') {
			if ('error' in body && typeof body.error === 'string' && body.error) {
				message = body.error;
			} else if ('detail' in body) {
				const detail = body.detail;
				if (detail && typeof detail === 'object') {
					if ('error' in detail && typeof detail.error === 'string' && detail.error) {
						message = detail.error;
					}
				} else if (typeof detail === 'string') {
					message = detail;
				}
			}
		}

		throw new ApiError(message, response.status, body);
	}

	return response.json() as Promise<T>;
}

export async function login(nombre: string) {
	return api<{
		token: string;
		usuario: { id: number; nombre: string };
		expires_at: string;
	}>('/auth/login', {
		method: 'POST',
		body: JSON.stringify({ nombre })
	});
}

export async function logout() {
	return api<{ ok: boolean }>('/auth/logout', { method: 'POST' });
}

export async function me() {
	return api<{ usuario: { id: number; nombre: string } }>('/auth/me');
}

export async function listUsuarios() {
	return api<Array<{ id: number; nombre: string }>>('/usuarios');
}

// Types matching backend ImportSummaryResponse
export interface ImportError {
	row: number;
	sku: string | null;
	message: string;
}

export interface ImportSummary {
	total_rows: number;
	imported: number;
	skipped: number;
	skipped_no_barcode: number;
	skipped_barcode_conflicts: number;
	barcode_conflicts: ImportError[];
	overwritten: number;
	errors: ImportError[];
}

export async function importExcel(file: File, strategy: string = 'error'): Promise<ImportSummary> {
	const formData = new FormData();
	formData.append('file', file);
	return api<ImportSummary>(`/import/excel?strategy=${encodeURIComponent(strategy)}`, {
		method: 'POST',
		body: formData,
		headers: {} // Let browser set Content-Type for multipart
	});
}

// Types matching backend schemas
export interface Deposito {
	id: number;
	nombre: string;
}

export interface Estante {
	id: number;
	nombre: string;
	orden_visual: number;
	filas: number;
	columnas: number;
	deposito_id: number | null;
	deposito_nombre: string | null;
	deleted_at: string | null;
	created_at: string;
	ubicaciones_count: number;
	ubicaciones?: Ubicacion[];
}

export interface Ubicacion {
	id: number;
	estante_id: number;
	estante_nombre: string;
	fila: number;
	columna: number;
	producto_id: string | null;
	producto_sku: string | null;
	producto_descripcion: string | null;
	stock_actual: number;
	qr_valor: string;
	estado: string;
}

export interface EstanteCreate {
	nombre: string;
	orden_visual: number;
	filas: number;
	columnas: number;
	deposito_id?: number | null;
}

export interface EstanteUpdate {
	filas?: number;
	columnas?: number;
	orden_visual?: number;
}

export interface EstanteUpdateResponse {
	estante: Estante;
	out_of_bounds: Ubicacion[];
}

export interface ProductSearchResult {
	sku: string;
	descripcion: string;
	codigo_de_barra: string;
}

export interface Product {
	sku: string;
	descripcion: string;
	codigo_de_barra: string;
	created_at: string;
}

export interface UbicacionStockInfo {
	ubicacion_id: number;
	stock_actual: number;
	is_assigned: boolean;
	existing_producto_sku: string | null;
}

export interface ProductWithUbicacionStock extends Product {
	ubicacion_stock: UbicacionStockInfo | null;
}

export interface ProductoStockTotal {
	sku: string;
	stock_total: number;
}

export interface MovimientoCreate {
	producto_sku: string;
	ubicacion_id: number;
	cantidad: number;
	tipo: 'alta' | 'ajuste';
}

export interface MovimientoResponse {
	id: number;
	usuario_id: number;
	usuario_nombre: string;
	producto_sku: string;
	producto_descripcion: string;
	ubicacion_id: number;
	ubicacion_qr: string;
	estante_nombre: string;
	fila: number;
	columna: number;
	cantidad: number;
	stock_anterior: number;
	stock_nuevo: number;
	timestamp: string;
	tipo: string;
	stock_general_anterior: number;
	stock_general_nuevo: number;
}

export interface MovimientoListResponse {
	items: MovimientoResponse[];
	total: number;
}

export async function listDepositos(): Promise<Deposito[]> {
	return api<Deposito[]>('/depositos');
}

export async function listEstantes(
	includeDeleted = false,
	depositoId: number | null = null
): Promise<Estante[]> {
	const params = new URLSearchParams();
	params.set('include_deleted', String(includeDeleted));
	if (depositoId != null) {
		params.set('deposito_id', String(depositoId));
	}
	return api<Estante[]>(`/estantes?${params.toString()}`);
}

export async function getEstante(id: number): Promise<Estante> {
	return api<Estante>(`/estantes/${id}`);
}

export async function createEstante(data: EstanteCreate): Promise<Estante> {
	return api<Estante>('/estantes', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateEstante(id: number, data: EstanteUpdate): Promise<EstanteUpdateResponse> {
	return api<EstanteUpdateResponse>(`/estantes/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export async function deleteEstante(id: number): Promise<{ ok: boolean }> {
	return api<{ ok: boolean }>(`/estantes/${id}`, { method: 'DELETE' });
}

export async function confirmDeleteOutOfBounds(
	estanteId: number,
	ubicacionIds: number[]
): Promise<{ deleted: number }> {
	return api<{ deleted: number }>(`/estantes/${estanteId}/confirm-delete-out-of-bounds`, {
		method: 'POST',
		body: JSON.stringify({ ubicacion_ids: ubicacionIds })
	});
}

export async function assignProductToUbicacion(ubicacionId: number, productoSku: string): Promise<Ubicacion> {
	return api<Ubicacion>(`/ubicaciones/${ubicacionId}/assign`, {
		method: 'PUT',
		body: JSON.stringify({ producto_id: productoSku })
	});
}

export async function unassignProductFromUbicacion(ubicacionId: number): Promise<Ubicacion> {
	return api<Ubicacion>(`/ubicaciones/${ubicacionId}/assign`, {
		method: 'DELETE'
	});
}

export async function searchProductos(query: string): Promise<ProductSearchResult[]> {
	const encoded = encodeURIComponent(query);
	const response = await api<{ items: ProductSearchResult[]; total: number }>(
		`/productos?search=${encoded}`
	);
	return response.items;
}

// Sector lookup by QR value
export async function lookupSector(qrValor: string): Promise<Ubicacion> {
	return api<Ubicacion>(`/sectores/lookup?qr_valor=${encodeURIComponent(qrValor)}`);
}

// Product lookup by barcode (exact)
export async function getProductoByBarcode(codigo: string): Promise<Product | null> {
	try {
		return await api<Product>(`/productos/${encodeURIComponent(codigo)}`);
	} catch {
		return null;
	}
}

// Product lookup with stock info for the anchored ubicacion
export async function getProductoByBarcodeWithStock(
	codigo: string,
	ubicacionId: number
): Promise<ProductWithUbicacionStock | null> {
	try {
		return await api<ProductWithUbicacionStock>(
			`/productos/${encodeURIComponent(codigo)}?ubicacion_id=${ubicacionId}`
		);
	} catch {
		return null;
	}
}

export async function getProductoStockTotal(sku: string): Promise<ProductoStockTotal> {
	return api<ProductoStockTotal>(
		`/productos/${encodeURIComponent(sku)}/stock-total?sku=${encodeURIComponent(sku)}`
	);
}

export async function createMovimiento(data: MovimientoCreate): Promise<MovimientoResponse> {
	return api<MovimientoResponse>('/movimientos', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export interface MovimientoFilters {
	usuario_id?: number;
	producto_sku?: string;
	ubicacion_id?: number;
	from_date?: string;
	to_date?: string;
	limit?: number;
	offset?: number;
}

export async function listMovimientos(filters: MovimientoFilters): Promise<MovimientoListResponse> {
	const params = new URLSearchParams();
	if (filters.usuario_id) params.set('usuario_id', String(filters.usuario_id));
	if (filters.producto_sku) params.set('producto_sku', filters.producto_sku);
	if (filters.ubicacion_id) params.set('ubicacion_id', String(filters.ubicacion_id));
	if (filters.from_date) params.set('from_date', filters.from_date);
	if (filters.to_date) params.set('to_date', filters.to_date);
	if (filters.limit) params.set('limit', String(filters.limit));
	if (filters.offset) params.set('offset', String(filters.offset));
	return api<MovimientoListResponse>(`/movimientos?${params.toString()}`);
}

export async function exportMovimientosCSV(filters: MovimientoFilters): Promise<Blob> {
	const session = get(sessionStore);
	const params = new URLSearchParams();
	if (filters.usuario_id) params.set('usuario_id', String(filters.usuario_id));
	if (filters.producto_sku) params.set('producto_sku', filters.producto_sku);
	if (filters.ubicacion_id) params.set('ubicacion_id', String(filters.ubicacion_id));
	if (filters.from_date) params.set('from_date', filters.from_date);
	if (filters.to_date) params.set('to_date', filters.to_date);

	const headers: Record<string, string> = {};
	if (session?.token) {
		headers['Authorization'] = `Bearer ${session.token}`;
	}

	const response = await fetch(`${API_BASE}/movimientos/export?${params.toString()}`, {
		headers
	});

	if (!response.ok) {
		const body = (await response.json().catch(() => null)) as unknown;
		let message = `Error HTTP ${response.status}`;
		if (body && typeof body === 'object' && 'detail' in body) {
			const detail = body.detail;
			if (typeof detail === 'string') message = detail;
		}
		throw new ApiError(message, response.status, body);
	}

	return response.blob();
}

export async function getEstanteUbicaciones(estanteId: number): Promise<Ubicacion[]> {
	return api<Ubicacion[]>(`/estantes/${estanteId}/ubicaciones`);
}
