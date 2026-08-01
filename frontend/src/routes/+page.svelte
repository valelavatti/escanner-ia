<script>
	import { sessionStore } from '$lib/stores/session';
</script>

<section class="home">
	<h1>ASG Scanner</h1>
	<p>Escáner de productos Accesaniga</p>

	{#if $sessionStore}
		<p>Hola, {$sessionStore.usuario.nombre}</p>
		<div class="home__actions">
			<a href="/picking" class="home__action home__action--picking">Modo Remito (InvenTIA)</a>
			<a href="/scanner" class="home__action">Escanear</a>
			<a href="/mapa" class="home__action home__action--secondary">Ver mapa</a>
			<a href="/historial" class="home__action home__action--secondary">Historial</a>
			<a href="/admin/estantes" class="home__action home__action--secondary">Gestionar estantes</a>

			{#if $sessionStore.usuario.is_admin}
				<div class="home__admin-divider">
					<span>Administración</span>
				</div>
				<a href="/admin/usuarios" class="home__action home__action--admin">Gestionar usuarios</a>
				<a href="/admin/import" class="home__action home__action--admin">Importar productos</a>
			{/if}
		</div>
	{:else}
		<p>Inicie sesión para continuar</p>
	{/if}
</section>

<style>
	.home {
		padding: 1rem;
	}

	.home__actions {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.home__action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
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

	.home__action--secondary {
		color: #334155;
		background-color: #f1f5f9;
	}

	.home__action--secondary:active {
		background-color: #e2e8f0;
	}

	.home__action--picking {
		color: #ffffff;
		background-color: #16a34a;
		font-size: 1.0625rem;
	}

	.home__action--picking:active {
		background-color: #15803d;
	}

	.home__action--admin {
		color: #ffffff;
		background-color: #0f172a;
	}

	.home__action--admin:active {
		background-color: #334155;
	}

	.home__admin-divider {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 0.5rem;
		color: #64748b;
		font-size: 0.875rem;
		font-weight: 600;
		text-transform: uppercase;
	}

	.home__admin-divider::before,
	.home__admin-divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background-color: #e2e8f0;
	}
</style>
