<script>
	import { page } from '$app/stores';

	let { children } = $props();

	const tabs = [
		{ path: '/admin/import', label: 'Importar' },
		{ path: '/admin/estantes', label: 'Estantes' }
	];
</script>

<div class="admin-layout">
	<nav class="admin-nav" aria-label="Admin">
		{#each tabs as tab}
			<a
				href={tab.path}
				class="admin-nav__link"
				class:admin-nav__link--active={$page.url.pathname === tab.path}
			>
				{tab.label}
			</a>
		{/each}
	</nav>

	{@render children()}
</div>

<style>
	.admin-layout {
		padding: 1rem 0;
	}

	.admin-nav {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.admin-nav__link {
		flex: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		color: #334155;
		background-color: #f1f5f9;
		border-radius: 0.5rem;
		text-decoration: none;
		touch-action: manipulation;
	}

	.admin-nav__link--active {
		color: #ffffff;
		background-color: #2563eb;
	}

	.admin-nav__link:not(.admin-nav__link--active):active {
		background-color: #e2e8f0;
	}
</style>
