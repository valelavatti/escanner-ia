import { writable } from 'svelte/store';
import type { RemitoState } from '$lib/api/client';

/**
 * Authoritative server state for the active remito.
 * Lives in memory only — a reload re-fetches from the server,
 * which is always the source of truth.
 */
export const remitoState = writable<RemitoState | null>(null);

/**
 * Apply a new server state, discarding it if it carries an older
 * route_version than what we already have (stale response from a
 * slow retry).
 */
export function applyServerState(next: RemitoState): void {
	remitoState.update((cur) => {
		if (
			cur &&
			cur.remito_id === next.remito_id &&
			next.route_version < cur.route_version
		) {
			return cur;
		}
		return next;
	});
}
