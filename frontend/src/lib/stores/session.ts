import { writable } from 'svelte/store';

export interface UserSession {
	session_id: string;
	user_id: number;
	nombre: string;
	expires_at: string;
}

export const sessionStore = writable<UserSession | null>(null);
