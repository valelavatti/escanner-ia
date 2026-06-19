<script>
	import { sessionStore } from '$lib/stores/session';
</script>

<section>
	<h1>ASG Scanner</h1>
	<p>Escáner de productos Accesaniga</p>

	{#if $sessionStore}
		<p>Hola, {$sessionStore.nombre}</p>
	{:else}
		<p>Inicie sesión para continuar</p>
	{/if}
</section>
