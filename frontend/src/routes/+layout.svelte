<script>
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { sessionStore } from '$lib/stores/session';
	import '../app.css';

	let { children } = $props();

	$effect(() => {
		const path = $page.url.pathname;
		const hasSession = !!$sessionStore;

		if (!hasSession && path !== '/login') {
			goto('/login');
		}

		if (hasSession && path === '/login') {
			goto('/');
		}
	});
</script>

<div class="app">
	{@render children()}
</div>

<style>
	.app {
		min-height: 100vh;
		padding: env(safe-area-inset-top) 1rem env(safe-area-inset-bottom);
	}
</style>
