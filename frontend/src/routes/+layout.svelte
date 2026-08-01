<script>
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { sessionStore, clearSession } from '$lib/stores/session';
	import { logout } from '$lib/api/client';
	import '../app.css';

	let { children } = $props();

	$effect(() => {
		const path = $page.url.pathname;
		const hasSession = !!$sessionStore;

		if (!hasSession && path !== '/login' && path !== '/mockups' && !path.startsWith('/picking')) {
			goto('/login');
		}

		if (hasSession && path === '/login') {
			goto('/');
		}
	});

	async function handleLogout() {
		try {
			await logout();
		} catch {
			// Ignore errors — we clear the session locally regardless
		}
		clearSession();
		goto('/login');
	}
</script>

<div class="app">
	{#if $sessionStore && $page.url.pathname !== '/login'}
		<header class="app__header">
			<div class="app__nav">
				{#if $page.url.pathname !== '/'}
					<button class="app__back" onclick={() => goto('/')} aria-label="Volver al inicio">
						&larr;
					</button>
				{/if}
				<span class="app__user">{$sessionStore.usuario.nombre}</span>
			</div>
			<button class="app__logout" onclick={handleLogout}>Cerrar sesión</button>
		</header>
	{/if}
	{@render children()}
</div>

<style>
	.app {
		min-height: 100vh;
		padding: env(safe-area-inset-top) 1rem env(safe-area-inset-bottom);
	}

	.app__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0;
		margin-bottom: 0.5rem;
	}

	.app__nav {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.app__back {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		font-size: 1.25rem;
		font-weight: 700;
		color: #334155;
		background-color: #f1f5f9;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.app__back:active {
		background-color: #e2e8f0;
	}

	.app__user {
		font-size: 0.875rem;
		font-weight: 600;
		color: #334155;
	}

	.app__logout {
		min-height: 2.5rem;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #dc2626;
		background-color: transparent;
		border: 1px solid #dc2626;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.app__logout:active {
		background-color: #fee2e2;
	}
</style>
