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
