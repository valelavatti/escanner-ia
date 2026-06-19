<script>
	import { sessionStore } from '$lib/stores/session';
</script>

<section class="home">
	<h1>ASG Scanner</h1>
	<p>Escáner de productos Accesaniga</p>

	{#if $sessionStore}
		<p>Hola, {$sessionStore.usuario.nombre}</p>
		<a href="/admin/import" class="home__action">Importar productos</a>
	{:else}
		<p>Inicie sesión para continuar</p>
	{/if}
</section>

<style>
	.home {
		padding: 1rem;
	}

	.home__action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		margin-top: 1rem;
		padding: 0.75rem 1.5rem;
		font-size: 1rem;
		font-weight: 600;
		color: #ffffff;
		background-color: #2563eb;
		border-radius: 0.5rem;
		text-decoration: none;
		touch-action: manipulation;
	}

	.home__action:active {
		background-color: #1d4ed8;
	}
</style>

