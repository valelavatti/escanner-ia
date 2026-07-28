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

export interface LoginResponse {
	token: string;
	usuario: { id: number; nombre: string; is_admin: boolean };
	expires_at: string;
}

export interface DepositoAssignment {
	deposito_id: number;
	deposito_nombre: string;
	role: 'admin' | 'operator' | 'viewer';
}

export async function login(nombre: string, password: string): Promise<LoginResponse> {
	return api<LoginResponse>('/auth/login', {
		method: 'POST',
		body: JSON.stringify({ nombre, password })
	});
}

export async function logout() {
	return api<{ ok: boolean }>('/auth/logout', { method: 'POST' });
}

export interface MeResponse {
	usuario: { id: number; nombre: string; is_admin: boolean };
	depositos: DepositoAssignment[];
}

export async function me(): Promise<MeResponse> {
	return api<MeResponse>('/auth/me');
}

// User management types (admin only)
export interface UsuarioResponse {
	id: number;
	nombre: string;
	is_admin: boolean;
}

export interface UsuarioWithDepositos extends UsuarioResponse {
	depositos: DepositoAssignment[];
}

export interface UsuarioCreate {
	nombre: string;
	password: string;
	is_admin: boolean;
}

export interface UsuarioUpdate {
	nombre?: string;
	password?: string;
	is_admin?: boolean;
}

export interface AssignDepositoRequest {
	deposito_id: number;
	role: 'admin' | 'operator' | 'viewer';
}

export async function listUsuarios(): Promise<UsuarioWithDepositos[]> {
	return api<UsuarioWithDepositos[]>('/usuarios');
}

export async function createUsuario(data: UsuarioCreate): Promise<UsuarioResponse> {
	return api<UsuarioResponse>('/usuarios', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateUsuario(id: number, data: UsuarioUpdate): Promise<UsuarioResponse> {
	return api<UsuarioResponse>(`/usuarios/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export async function deleteUsuario(id: number): Promise<void> {
	await api<{ ok: boolean }>(`/usuarios/${id}`, { method: 'DELETE' });
}

export async function getUsuarioDepositos(usuarioId: number): Promise<DepositoAssignment[]> {
	return api<DepositoAssignment[]>(`/usuarios/${usuarioId}/depositos`);
}

export async function assignUsuarioDeposito(
	usuarioId: number,
	data: AssignDepositoRequest
): Promise<void> {
	await api<{ ok: boolean }>(`/usuarios/${usuarioId}/depositos`, {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function removeUsuarioDeposito(usuarioId: number, depositoId: number): Promise<void> {
	await api<{ ok: boolean }>(`/usuarios/${usuarioId}/depositos/${depositoId}`, {
		method: 'DELETE'
	});
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
	created_at?: string;
	estantes_count?: number;
	usuarios_count?: number;
}

export interface DepositoCreate {
	nombre: string;
}

export interface DepositoUpdate {
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
	fila_order: string;
	columna_order: string;
	fila_format: string;
	columna_format: string;
	ubicaciones?: Ubicacion[];
}

export interface Ubicacion {
	id: number;
	estante_id: number;
	estante_nombre: string;
	fila: number;
	columna: number;
	fila_label: string;
	columna_label: string;
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
	fila_order?: string;
	columna_order?: string;
	fila_format?: string;
	columna_format?: string;
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
	existing_producto_stock: number | null;
}

export interface ProductWithUbicacionStock extends Product {
	ubicacion_stock: UbicacionStockInfo | null;
}

export interface ProductoStockTotal {
	sku: string;
	stock_total: number;
	stock_sin_ubicacion: number;
}

// Admin listing of products whose units sit in the sin-ubicacion bucket
// (Slice 6 / FE Point 5). Read-only — there are no admin actions on the
// bucket; it only exits via re-assigning to a physical ubicacion.
export interface StockSinUbicacionListItem {
	producto_sku: string;
	producto_descripcion: string;
	cantidad: number;
	updated_at: string | null;
}

export interface ProductoUbicacionItem {
	ubicacion_id: number | null;
	estante_nombre: string;
	qr_valor: string | null;
	fila: number;
	columna: number;
	fila_label: string;
	columna_label: string;
	stock: number;
	deposito_nombre: string;
}

export interface ProductoUbicacionesResponse {
	sku: string;
	descripcion: string;
	codigo_de_barra: string;
	stock_total: number;
	ubicaciones: ProductoUbicacionItem[];
}

export interface MovimientoCreate {
	producto_sku: string;
	ubicacion_id: number;
	cantidad: number;
	tipo: 'alta' | 'ajuste';
}

export interface MovimientoResponse {
	id: number;
	usuario_id: number | null;
	usuario_nombre: string | null;
	producto_sku: string;
	producto_descripcion: string;
	ubicacion_id: number;
	ubicacion_qr: string;
	estante_nombre: string;
	fila: number;
	columna: number;
	fila_label: string;
	columna_label: string;
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

export async function createDeposito(data: DepositoCreate): Promise<Deposito> {
	return api<Deposito>('/depositos', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateDeposito(id: number, data: DepositoUpdate): Promise<Deposito> {
	return api<Deposito>(`/depositos/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export async function deleteDeposito(id: number): Promise<{ ok: boolean }> {
	return api<{ ok: boolean }>(`/depositos/${id}`, { method: 'DELETE' });
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

// Admin-only listing of every product with units in the sin-ubicacion bucket
// (Slice 6 / FE Point 5 — backend ``GET /productos/sin-ubicacion`` guarded
// by ``require_admin``). Each row pairs a bucket qty with the product SKU +
// description joined server-side.
export async function getStockSinUbicacion(): Promise<StockSinUbicacionListItem[]> {
	return api<StockSinUbicacionListItem[]>('/productos/sin-ubicacion');
}

export async function getProductoUbicaciones(
	codigo: string
): Promise<ProductoUbicacionesResponse> {
	return api<ProductoUbicacionesResponse>(
		`/productos/${encodeURIComponent(codigo)}/ubicaciones`
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

// ---------------------------------------------------------------------------
// QR generation endpoints (return binary content)
// ---------------------------------------------------------------------------

async function extractBlobError(response: Response): Promise<{ message: string; body: unknown }> {
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

	return { message, body };
}

async function authenticatedBlobFetch(path: string, acceptHeader: string): Promise<Response> {
	const session = get(sessionStore);
	const headers: Record<string, string> = { Accept: acceptHeader };

	if (session?.token) {
		headers['Authorization'] = `Bearer ${session.token}`;
	}

	const response = await fetch(`${API_BASE}${path}`, { headers });

	if (response.status === 401) {
		clearSession();
		if (browser) {
			window.location.href = '/login';
		}
		throw new Error('Sesión inválida o expirada');
	}

	return response;
}

export async function getUbicacionQR(ubicacionId: number, size: number = 200): Promise<Blob> {
	const response = await authenticatedBlobFetch(
		`/ubicaciones/${ubicacionId}/qr.png?size=${size}`,
		'image/png'
	);

	if (!response.ok) {
		const { message, body } = await extractBlobError(response);
		throw new ApiError(message, response.status, body);
	}

	return response.blob();
}

export async function downloadEstanteQRsZip(estanteId: number): Promise<Blob> {
	const response = await authenticatedBlobFetch(`/estantes/${estanteId}/qrs`, 'application/zip');

	if (!response.ok) {
		const { message, body } = await extractBlobError(response);
		throw new ApiError(message, response.status, body);
	}

	return response.blob();
}

export async function getEstanteQRPrintSheet(
	estanteId: number,
	perPage: number
): Promise<Blob> {
	const response = await authenticatedBlobFetch(
		`/estantes/${estanteId}/qrs/print?per_page=${perPage}`,
		'application/pdf'
	);

	if (!response.ok) {
		const { message, body } = await extractBlobError(response);
		throw new ApiError(message, response.status, body);
	}

	return response.blob();
}
