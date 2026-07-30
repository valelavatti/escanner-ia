<script>
	import { goto } from '$app/navigation';
	import { login, me, ApiError } from '$lib/api/client';
	import { setSession } from '$lib/stores/session';

	let nombre = $state('');
	let password = $state('');
	let errorMsg = $state('');
	let loading = $state(false);

	/** @param {SubmitEvent} e */
	async function handleSubmit(e) {
		e.preventDefault();
		errorMsg = '';
		const trimmedNombre = nombre.trim();
		const trimmedPassword = password.trim();

		if (!trimmedNombre || !trimmedPassword) {
			errorMsg = 'Ingrese usuario y contraseña';
			return;
		}

		loading = true;
		try {
			const loginData = await login(trimmedNombre, trimmedPassword);
			// Store token FIRST so me() can authenticate
			setSession(loginData.token, loginData.usuario, loginData.expires_at, []);
			const meData = await me();
			// Update with depositos from /me
			setSession(loginData.token, loginData.usuario, loginData.expires_at, meData.depositos);
			goto('/');
		} catch (/** @type {any} */ e) {
			if (e instanceof ApiError && e.status === 401) {
				const message = e.message || '';
				if (message.toLowerCase().includes('sin contraseña')) {
					errorMsg = 'Usuario sin contraseña. Contacte al administrador.';
				} else {
					errorMsg = 'Usuario o contraseña incorrectos';
				}
			} else {
				errorMsg = e.message || 'Error al iniciar sesión';
			}
		} finally {
			loading = false;
		}
	}

	function devBypass() {
		const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
		setSession(
			'dev-token',
			{ id: 1, nombre: 'Dev Usuario', is_admin: true },
			expiresAt,
			[{ deposito_id: 1, deposito_nombre: 'Depósito Central', role: 'admin' }]
		);
		goto('/');
	}
</script>

<section class="login">
	<h1>ASG Scanner</h1>
	<p class="subtitle">Ingrese usuario y contraseña</p>

	<form onsubmit={handleSubmit}>
		<label for="nombre">Usuario</label>
		<input
			id="nombre"
			type="text"
			bind:value={nombre}
			placeholder="Nombre de usuario"
			autocomplete="username"
			disabled={loading}
		/>

		<label for="password">Contraseña</label>
		<input
			id="password"
			type="password"
			bind:value={password}
			placeholder="Contraseña"
			autocomplete="current-password"
			disabled={loading}
		/>

		<button type="submit" disabled={loading || !nombre.trim() || !password.trim()}>
			{loading ? 'Ingresando…' : 'Ingresar'}
		</button>
	</form>

	{#if errorMsg}
		<p class="error" role="alert">{errorMsg}</p>
	{/if}

	<div class="dev-bypass">
		<button type="button" class="dev-bypass__btn" onclick={devBypass}>
			Acceso de desarrollo (sin backend)
		</button>
	</div>
</section>

<style>
	.login {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		max-width: 28rem;
		margin: 0 auto;
		padding: 2rem 1rem;
	}

	.login h1 {
		margin: 0;
		font-size: 1.75rem;
	}

	.subtitle {
		margin: 0;
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
	button[type='submit'] {
		min-height: 48px;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		border-radius: 0.5rem;
	}

	input {
		border: 1px solid var(--color-border, #d1d5db);
		background-color: #ffffff;
	}

	button[type='submit'] {
		border: none;
		background: var(--color-primary, #0f172a);
		color: white;
		font-weight: 600;
		cursor: pointer;
		touch-action: manipulation;
	}

	button[type='submit']:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	button[type='submit']:not(:disabled):active {
		background-color: #334155;
	}

	.error {
		margin: 0;
		padding: 0.75rem 1rem;
		color: #991b1b;
		background-color: #fee2e2;
		border-radius: 0.5rem;
		font-weight: 500;
	}

	.dev-bypass {
		border-top: 1px dashed #d1d5db;
		padding-top: 1rem;
	}

	.dev-bypass__btn {
		width: 100%;
		min-height: 44px;
		padding: 0.625rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: #6b7280;
		background-color: transparent;
		border: 1px dashed #9ca3af;
		border-radius: 0.5rem;
		cursor: pointer;
	}

	.dev-bypass__btn:hover {
		background-color: #f9fafb;
		border-color: #6b7280;
		color: #374151;
	}
</style>
