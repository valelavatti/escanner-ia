import { get } from 'svelte/store';
import { browser } from '$app/environment';
import { sessionStore, clearSession } from '$lib/stores/session';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface ApiErrorBody {
	error?: string;
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
	const session = get(sessionStore);
	const headers: Record<string, string> = {
		Accept: 'application/json',
		'Content-Type': 'application/json',
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
		const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
		throw new Error(body.error || `Error HTTP ${response.status}`);
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
