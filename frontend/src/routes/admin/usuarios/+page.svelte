<script lang="ts">
	import { goto } from '$app/navigation';
	import { sessionStore } from '$lib/stores/session';
	import {
		listUsuarios,
		createUsuario,
		updateUsuario,
		deleteUsuario,
		listDepositos,
		assignUsuarioDeposito,
		removeUsuarioDeposito,
		ApiError,
		type UsuarioWithDepositos,
		type Deposito,
		type UsuarioCreate,
		type UsuarioUpdate,
		type AssignDepositoRequest
	} from '$lib/api/client';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------
	let users = $state<UsuarioWithDepositos[]>([]);
	let depositos = $state<Deposito[]>([]);
	let loading = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	// Create/edit form
	let formOpen = $state(false);
	let formMode = $state<'create' | 'edit'>('create');
	let formUser = $state<UsuarioWithDepositos | null>(null);
	let formNombre = $state('');
	let formPassword = $state('');
	let formIsAdmin = $state(false);
	let formSaving = $state(false);

	// Depósito management
	let depositosOpen = $state(false);
	let depositosUser = $state<UsuarioWithDepositos | null>(null);
	let newDepositoId = $state<number | null>(null);
	let newRole = $state<AssignDepositoRequest['role']>('operator');
	let depositoSaving = $state(false);

	// Delete confirmation
	let userToDelete = $state<UsuarioWithDepositos | null>(null);
	let deleting = $state(false);

	const ROLES: { value: AssignDepositoRequest['role']; label: string }[] = [
		{ value: 'admin', label: 'Administrador' },
		{ value: 'operator', label: 'Operador' },
		{ value: 'viewer', label: 'Visualizador' }
	];

	$effect(() => {
		if ($sessionStore && !$sessionStore.usuario.is_admin) {
			goto('/admin/estantes');
		}
	});

	loadUsers();
	loadDepositos();

	// ---------------------------------------------------------------------------
	// Helpers
	// ---------------------------------------------------------------------------
	function showMessage(text: string, type: 'success' | 'error' = 'success') {
		message = { text, type };
		setTimeout(() => {
			message = null;
		}, 5000);
	}

	async function loadUsers() {
		loading = true;
		try {
			users = await listUsuarios();
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al cargar usuarios', 'error');
		} finally {
			loading = false;
		}
	}

	async function loadDepositos() {
		try {
			depositos = await listDepositos();
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al cargar depósitos', 'error');
		}
	}

	function openCreate() {
		formMode = 'create';
		formUser = null;
		formNombre = '';
		formPassword = '';
		formIsAdmin = false;
		formOpen = true;
	}

	function openEdit(user: UsuarioWithDepositos) {
		formMode = 'edit';
		formUser = user;
		formNombre = user.nombre;
		formPassword = '';
		formIsAdmin = user.is_admin;
		formOpen = true;
	}

	function closeForm() {
		formOpen = false;
		formUser = null;
	}

	async function handleSaveUser() {
		const nombre = formNombre.trim();
		if (!nombre) {
			showMessage('El nombre es obligatorio', 'error');
			return;
		}
		if (formMode === 'create' && !formPassword) {
			showMessage('La contraseña es obligatoria para crear un usuario', 'error');
			return;
		}

		formSaving = true;
		try {
			if (formMode === 'create') {
				await createUsuario({ nombre, password: formPassword, is_admin: formIsAdmin });
				showMessage('Usuario creado');
			} else if (formUser) {
				const data: UsuarioUpdate = { nombre, is_admin: formIsAdmin };
				if (formPassword) {
					data.password = formPassword;
				}
				await updateUsuario(formUser.id, data);
				showMessage('Usuario actualizado');
			}
			closeForm();
			await loadUsers();
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				showMessage('Ya existe un usuario con ese nombre', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al guardar el usuario', 'error');
			}
		} finally {
			formSaving = false;
		}
	}

	function canDeleteUser(user: UsuarioWithDepositos): { ok: boolean; reason?: string } {
		if ($sessionStore && user.id === $sessionStore.usuario.id) {
			return { ok: false, reason: 'No podés eliminar tu propio usuario.' };
		}
		if (user.is_admin) {
			const adminCount = users.filter((u) => u.is_admin).length;
			if (adminCount <= 1) {
				return { ok: false, reason: 'No se puede eliminar el último administrador.' };
			}
		}
		return { ok: true };
	}

	function openDelete(user: UsuarioWithDepositos) {
		const check = canDeleteUser(user);
		if (!check.ok) {
			showMessage(check.reason || 'No se puede eliminar este usuario', 'error');
			return;
		}
		userToDelete = user;
	}

	function closeDelete() {
		userToDelete = null;
	}

	async function handleDelete() {
		if (!userToDelete) return;
		deleting = true;
		try {
			await deleteUsuario(userToDelete.id);
			closeDelete();
			await loadUsers();
			showMessage('Usuario eliminado');
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al eliminar el usuario', 'error');
		} finally {
			deleting = false;
		}
	}

	function openDepositos(user: UsuarioWithDepositos) {
		depositosUser = user;
		newDepositoId = null;
		newRole = 'operator';
		depositosOpen = true;
	}

	function closeDepositos() {
		depositosOpen = false;
		depositosUser = null;
	}

	async function handleAssignDeposito() {
		if (!depositosUser || newDepositoId == null) return;
		depositoSaving = true;
		try {
			await assignUsuarioDeposito(depositosUser.id, {
				deposito_id: newDepositoId,
				role: newRole
			});
			newDepositoId = null;
			newRole = 'operator';
			await loadUsers();
			depositosUser = users.find((u) => u.id === depositosUser!.id) ?? depositosUser;
			showMessage('Depósito asignado');
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				showMessage('El depósito ya está asignado a este usuario', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al asignar el depósito', 'error');
			}
		} finally {
			depositoSaving = false;
		}
	}

	async function handleRemoveDeposito(depositoId: number) {
		if (!depositosUser) return;
		try {
			await removeUsuarioDeposito(depositosUser.id, depositoId);
			await loadUsers();
			depositosUser = users.find((u) => u.id === depositosUser!.id) ?? depositosUser;
			showMessage('Depósito removido');
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al remover el depósito', 'error');
		}
	}

	function roleLabel(role: string): string {
		return ROLES.find((r) => r.value === role)?.label ?? role;
	}

	function unassignedDepositos(currentUser: UsuarioWithDepositos | null): Deposito[] {
		if (!currentUser) return depositos;
		const assignedIds = new Set(currentUser.depositos.map((d) => d.deposito_id));
		return depositos.filter((d) => !assignedIds.has(d.id));
	}
</script>

<section class="usuarios-page">
	<header class="page-header">
		<h1>Gestionar usuarios</h1>
		<button class="button button--primary" onclick={openCreate} disabled={loading}>
			Nuevo usuario
		</button>
	</header>

	{#if message}
		<div class="alert alert--{message.type}" role="alert">
			{message.text}
		</div>
	{/if}

	{#if loading && users.length === 0}
		<p class="loading">Cargando…</p>
	{:else if users.length === 0}
		<p class="empty">No hay usuarios configurados.</p>
	{:else}
		<ul class="user-list">
			{#each users as user (user.id)}
				<li class="user-card">
					<div class="user-card__header">
						<h2 class="user-card__name">{user.nombre}</h2>
						{#if user.is_admin}
							<span class="badge badge--admin">admin</span>
						{/if}
					</div>

					<div class="user-card__meta">
						<span>{user.depositos.length} depósito{user.depositos.length === 1 ? '' : 's'}</span>
					</div>

					<div class="user-card__actions">
						<button
							class="button button--secondary"
							onclick={() => openDepositos(user)}
							disabled={loading}
						>
							Depósitos
						</button>
						<button
							class="button button--secondary"
							onclick={() => openEdit(user)}
							disabled={loading}
						>
							Editar
						</button>
						<button
							class="button button--danger"
							onclick={() => openDelete(user)}
							disabled={loading}
						>
							Eliminar
						</button>
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</section>

{#if formOpen}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeForm}
		onkeydown={(e) => e.key === 'Escape' && closeForm()}
	>
		<div
			class="modal"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="form-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="form-title">{formMode === 'create' ? 'Nuevo usuario' : 'Editar usuario'}</h2>

			<label class="field-label" for="form-nombre">Nombre</label>
			<input id="form-nombre" class="field-input" type="text" bind:value={formNombre} maxlength="100" />

			<label class="field-label" for="form-password">
				Contraseña
				{#if formMode === 'edit'}
					<span class="hint-inline">(dejar en blanco para no cambiar)</span>
				{/if}
			</label>
			<input
				id="form-password"
				class="field-input"
				type="password"
				bind:value={formPassword}
				placeholder={formMode === 'create' ? 'Contraseña' : 'Nueva contraseña (opcional)'}
			/>

			<label class="field-label field-label--checkbox" for="form-is-admin">
				<input id="form-is-admin" type="checkbox" bind:checked={formIsAdmin} />
				<span>Administrador global</span>
			</label>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeForm} disabled={formSaving}>
					Cancelar
				</button>
				<button class="button button--primary" onclick={handleSaveUser} disabled={formSaving}>
					{formSaving ? 'Guardando…' : 'Guardar'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if depositosOpen && depositosUser}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeDepositos}
		onkeydown={(e) => e.key === 'Escape' && closeDepositos()}
	>
		<div
			class="modal modal--tall"
			role="dialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="depositos-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="depositos-title">Depósitos de {depositosUser.nombre}</h2>

			{#if depositosUser.depositos.length > 0}
				<ul class="assignment-list">
					{#each depositosUser.depositos as assignment (assignment.deposito_id)}
						<li class="assignment-item">
							<div class="assignment-item__info">
								<strong>{assignment.deposito_nombre}</strong>
								<span class="badge badge--role">{roleLabel(assignment.role)}</span>
							</div>
							<button
								class="button button--small button--danger"
								onclick={() => handleRemoveDeposito(assignment.deposito_id)}
							>
								Quitar
							</button>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="empty">No tiene depósitos asignados.</p>
			{/if}

			{#if unassignedDepositos(depositosUser).length > 0}
				<div class="assign-form">
					<label class="field-label" for="assign-deposito">Agregar depósito</label>
					<select id="assign-deposito" class="field-input field-input--select" bind:value={newDepositoId}>
						<option value={null}>Seleccione un depósito</option>
						{#each unassignedDepositos(depositosUser) as deposito}
							<option value={deposito.id}>{deposito.nombre}</option>
						{/each}
					</select>

					<label class="field-label" for="assign-role">Rol</label>
					<select id="assign-role" class="field-input field-input--select" bind:value={newRole}>
						{#each ROLES as role}
							<option value={role.value}>{role.label}</option>
						{/each}
					</select>

					<button
						class="button button--primary"
						onclick={handleAssignDeposito}
						disabled={newDepositoId == null || depositoSaving}
					>
						{depositoSaving ? 'Asignando…' : 'Asignar'}
					</button>
				</div>
			{/if}

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeDepositos}>Cerrar</button>
			</div>
		</div>
	</div>
{/if}

{#if userToDelete}
	<div
		class="modal-backdrop"
		role="presentation"
		tabindex="-1"
		onclick={closeDelete}
		onkeydown={(e) => e.key === 'Escape' && closeDelete()}
	>
		<div
			class="modal modal--warning"
			role="alertdialog"
			tabindex="0"
			aria-modal="true"
			aria-labelledby="delete-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 id="delete-title">¿Eliminar el usuario {userToDelete.nombre}?</h2>
			<p>Esta acción no se puede deshacer.</p>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeDelete} disabled={deleting}>
					Cancelar
				</button>
				<button class="button button--danger" onclick={handleDelete} disabled={deleting}>
					{deleting ? 'Eliminando…' : 'Eliminar'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.usuarios-page {
		padding: 0 0 2rem;
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		font-weight: 600;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.button--primary {
		color: #ffffff;
		background-color: #2563eb;
	}

	.button--primary:not(:disabled):active {
		background-color: #1d4ed8;
	}

	.button--secondary {
		color: #334155;
		background-color: #f1f5f9;
	}

	.button--secondary:not(:disabled):active {
		background-color: #e2e8f0;
	}

	.button--danger {
		color: #ffffff;
		background-color: #dc2626;
	}

	.button--danger:not(:disabled):active {
		background-color: #b91c1c;
	}

	.button--small {
		min-height: 2.25rem;
		padding: 0.375rem 0.75rem;
		font-size: 0.875rem;
	}

	.alert {
		margin-bottom: 1rem;
		padding: 1rem;
		border-radius: 0.5rem;
		font-weight: 500;
	}

	.alert--success {
		background-color: #dcfce7;
		color: #166534;
	}

	.alert--error {
		background-color: #fee2e2;
		color: #991b1b;
	}

	.loading,
	.empty {
		color: #64748b;
		padding: 1rem 0;
	}

	.user-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.user-card {
		padding: 1rem;
		border: 1px solid #e2e8f0;
		border-radius: 0.75rem;
		background-color: #ffffff;
	}

	.user-card__header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.user-card__name {
		font-size: 1.125rem;
		margin: 0;
	}

	.badge {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 0.25rem 0.5rem;
		border-radius: 9999px;
	}

	.badge--admin {
		color: #ffffff;
		background-color: #2563eb;
	}

	.badge--role {
		color: #475569;
		background-color: #e2e8f0;
	}

	.user-card__meta {
		color: #475569;
		font-size: 0.875rem;
		margin-bottom: 1rem;
	}

	.user-card__actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	@media (min-width: 640px) {
		.user-card__actions {
			grid-template-columns: repeat(3, 1fr);
		}

		.page-header {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		padding: 0;
		background-color: rgba(15, 23, 42, 0.6);
		z-index: 50;
		overflow-y: auto;
	}

	@media (min-width: 640px) {
		.modal-backdrop {
			align-items: flex-start;
			padding: 1rem;
		}
	}

	.modal {
		width: 100%;
		max-width: 28rem;
		max-height: 90vh;
		overflow-y: auto;
		padding: 1.25rem;
		background-color: #ffffff;
		border-radius: 0.75rem 0.75rem 0 0;
		box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
	}

	@media (min-width: 640px) {
		.modal {
			border-radius: 0.75rem;
			margin-top: 2rem;
		}
	}

	.modal--tall {
		max-height: 85vh;
	}

	.modal--warning {
		border-top: 4px solid #dc2626;
	}

	.modal h2 {
		font-size: 1.25rem;
		margin: 0 0 1rem;
	}

	.modal-actions {
		display: flex;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}

	.modal-actions .button {
		flex: 1;
	}

	.field-label {
		display: block;
		margin-top: 0.75rem;
		margin-bottom: 0.375rem;
		font-weight: 600;
		font-size: 0.875rem;
	}

	.field-label--checkbox {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 3rem;
		cursor: pointer;
	}

	.field-label--checkbox input {
		width: 1.25rem;
		height: 1.25rem;
	}

	.field-input {
		width: 100%;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		background-color: #ffffff;
	}

	.field-input--select {
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%23475569' viewBox='0 0 16 16'%3E%3Cpath d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 0.75rem center;
		padding-right: 2.5rem;
	}

	.hint-inline {
		font-weight: 400;
		color: #64748b;
	}

	.assignment-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-height: 16rem;
		overflow-y: auto;
	}

	.assignment-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem;
		background-color: #f8fafc;
		border-radius: 0.5rem;
	}

	.assignment-item__info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}

	.assign-form {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid #e2e8f0;
	}
</style>
