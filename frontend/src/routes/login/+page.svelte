<script>
	import { goto } from '$app/navigation';
	import { listUsuarios, login } from '$lib/api/client';
	import { setSession } from '$lib/stores/session';

	let nombre = $state('');
	let errorMsg = $state('');
	/** @type {Array<{id: number, nombre: string}>} */
	let users = $state([]);
	let loading = $state(true);

	async function loadUsers() {
		try {
			users = await listUsuarios();
		} catch (e) {
			errorMsg = 'No se pudo cargar la lista de usuarios';
		} finally {
			loading = false;
		}
	}

	/** @param {string} userNombre */
	async function selectUser(userNombre) {
		errorMsg = '';
		try {
			const data = await login(userNombre);
			setSession(data.token, data.usuario, data.expires_at);
			goto('/');
		} catch (/** @type {any} */ e) {
			errorMsg = e.message || 'Error al iniciar sesión';
		}
	}

	/** @param {SubmitEvent} e */
	async function handleSubmit(e) {
		e.preventDefault();
		errorMsg = '';
		const trimmed = nombre.trim();
		if (!trimmed) {
			errorMsg = 'Ingrese un nombre';
			return;
		}
		await selectUser(trimmed);
	}

	loadUsers();
</script>

<section class="login">
	<h1>ASG Scanner</h1>
	<p class="subtitle">Seleccione su usuario para continuar</p>

	{#if loading}
		<p>Cargando usuarios...</p>
	{:else}
		<form onsubmit={handleSubmit}>
			<label for="nombre">Nombre</label>
			<input
				id="nombre"
				type="text"
				bind:value={nombre}
				placeholder="Escriba o toque un nombre"
				autocomplete="name"
			/>
			<button type="submit" disabled={!nombre.trim()}>Ingresar</button>
		</form>

		{#if users.length > 0}
			<ul class="user-list" role="listbox" aria-label="Usuarios disponibles">
				{#each users as user (user.id)}
					<li>
					<button
						type="button"
						role="option"
						aria-selected={false}
						onclick={() => selectUser(user.nombre)}
					>
						{user.nombre}
					</button>
					</li>
				{/each}
			</ul>
		{/if}

		{#if errorMsg}
			<p class="error" role="alert">{errorMsg}</p>
		{/if}
	{/if}
</section>

<style>
	.login {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 28rem;
		margin: 0 auto;
		padding-top: 2rem;
	}

	.subtitle {
		color: var(--color-text-muted, #6b7280);
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	label {
		font-weight: 600;
	}

	input,
	button[type='submit'],
	.user-list button {
		min-height: 48px;
		padding: 0.75rem;
		font-size: 1rem;
		border-radius: 0.5rem;
	}

	input {
		border: 1px solid var(--color-border, #d1d5db);
	}

	button {
		border: none;
		background: var(--color-primary, #0f172a);
		color: white;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.user-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.user-list button {
		width: 100%;
		text-align: left;
		background: var(--color-surface, #f3f4f6);
		color: var(--color-text, #111827);
	}

	.error {
		color: #dc2626;
	}
</style>
