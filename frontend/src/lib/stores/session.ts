import { writable, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface UsuarioSession {
	id: number;
	nombre: string;
	is_admin: boolean;
}

export interface DepositoAssignment {
	deposito_id: number;
	deposito_nombre: string;
	role: 'admin' | 'operator' | 'viewer';
}

export interface UserSession {
	token: string;
	usuario: UsuarioSession;
	depositos: DepositoAssignment[];
	expires_at: string;
}

const STORAGE_KEY = 'asg_session';

function readStoredSession(): UserSession | null {
	if (!browser) return null;
	const raw = localStorage.getItem(STORAGE_KEY);
	if (!raw) return null;
	try {
		return JSON.parse(raw) as UserSession;
	} catch {
		localStorage.removeItem(STORAGE_KEY);
		return null;
	}
}

function createSessionStore(): Writable<UserSession | null> {
	const store = writable<UserSession | null>(readStoredSession());

	if (browser) {
		store.subscribe((value) => {
			if (value) {
				localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
			} else {
				localStorage.removeItem(STORAGE_KEY);
			}
		});
	}

	return store;
}

export const sessionStore = createSessionStore();

export function setSession(
	token: string,
	usuario: UsuarioSession,
	expires_at: string,
	depositos: DepositoAssignment[] = []
): void {
	sessionStore.set({ token, usuario, depositos, expires_at });
}

export function clearSession(): void {
	sessionStore.set(null);
}

export const isAuthenticated = derived(sessionStore, ($session) => !!$session);
