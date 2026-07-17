<script lang="ts">
	import { goto } from '$app/navigation';
	import { sessionStore } from '$lib/stores/session';
	import {
		listDepositos,
		createDeposito,
		updateDeposito,
		deleteDeposito,
		ApiError,
		type Deposito
	} from '$lib/api/client';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------
	let depositos = $state<Deposito[]>([]);
	let loading = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);

	// Create/edit form
	let formOpen = $state(false);
	let formMode = $state<'create' | 'edit'>('create');
	let formDeposito = $state<Deposito | null>(null);
	let formNombre = $state('');
	let formSaving = $state(false);

	// Delete confirmation
	let depositoToDelete = $state<Deposito | null>(null);
	let deleting = $state(false);

	$effect(() => {
		if ($sessionStore && !$sessionStore.usuario.is_admin) {
			goto('/');
		}
	});

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

	async function loadDepositos() {
		loading = true;
		try {
			depositos = await listDepositos();
		} catch (err) {
			showMessage(err instanceof Error ? err.message : 'Error al cargar depósitos', 'error');
		} finally {
			loading = false;
		}
	}

	function openCreate() {
		formMode = 'create';
		formDeposito = null;
		formNombre = '';
		formOpen = true;
	}

	function openEdit(deposito: Deposito) {
		formMode = 'edit';
		formDeposito = deposito;
		formNombre = deposito.nombre;
		formOpen = true;
	}

	function closeForm() {
		formOpen = false;
		formDeposito = null;
	}

	async function handleSave() {
		const nombre = formNombre.trim();
		if (!nombre) {
			showMessage('El nombre es obligatorio', 'error');
			return;
		}

		formSaving = true;
		try {
			if (formMode === 'create') {
				await createDeposito({ nombre });
				showMessage('Depósito creado');
			} else if (formDeposito) {
				await updateDeposito(formDeposito.id, { nombre });
				showMessage('Depósito actualizado');
			}
			closeForm();
			await loadDepositos();
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				showMessage('Ya existe un depósito con ese nombre', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al guardar el depósito', 'error');
			}
		} finally {
			formSaving = false;
		}
	}

	function canDeleteDeposito(deposito: Deposito): { ok: boolean; reason?: string } {
		if ((deposito.estantes_count ?? 0) > 0) {
			return {
				ok: false,
				reason: 'No se puede eliminar un depósito con estantes asignados.'
			};
		}
		if (depositos.length <= 1) {
			return { ok: false, reason: 'Debe existir al menos un depósito.' };
		}
		return { ok: true };
	}

	function openDelete(deposito: Deposito) {
		const check = canDeleteDeposito(deposito);
		if (!check.ok) {
			showMessage(check.reason || 'No se puede eliminar este depósito', 'error');
			return;
		}
		depositoToDelete = deposito;
	}

	function closeDelete() {
		depositoToDelete = null;
	}

	async function handleDelete() {
		if (!depositoToDelete) return;
		deleting = true;
		try {
			await deleteDeposito(depositoToDelete.id);
			closeDelete();
			await loadDepositos();
			showMessage('Depósito eliminado');
		} catch (err) {
			if (err instanceof ApiError && err.status === 400) {
				showMessage(err.message || 'No se puede eliminar este depósito', 'error');
			} else {
				showMessage(err instanceof Error ? err.message : 'Error al eliminar el depósito', 'error');
			}
		} finally {
			deleting = false;
		}
	}
</script>

<section class="depositos-page">
	<header class="page-header">
		<h1>Depósitos</h1>
		<button class="button button--primary" onclick={openCreate} disabled={loading}>
			Nuevo depósito
		</button>
	</header>

	{#if message}
		<div class="alert alert--{message.type}" role="alert">
			{message.text}
		</div>
	{/if}

	{#if loading && depositos.length === 0}
		<p class="loading">Cargando…</p>
	{:else if depositos.length === 0}
		<p class="empty">No hay depósitos configurados.</p>
	{:else}
		<ul class="deposito-list">
			{#each depositos as deposito (deposito.id)}
				<li class="deposito-card">
					<div class="deposito-card__header">
						<h2 class="deposito-card__name">{deposito.nombre}</h2>
					</div>

					<div class="deposito-card__meta">
						<span>{deposito.estantes_count ?? 0} estante{(deposito.estantes_count ?? 0) === 1 ? '' : 's'}</span>
						<span>{deposito.usuarios_count ?? 0} usuario{(deposito.usuarios_count ?? 0) === 1 ? '' : 's'}</span>
					</div>

					<div class="deposito-card__actions">
						<button
							class="button button--secondary"
							onclick={() => openEdit(deposito)}
							disabled={loading}
						>
							Editar
						</button>
						<button
							class="button button--danger"
							onclick={() => openDelete(deposito)}
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
			<h2 id="form-title">{formMode === 'create' ? 'Nuevo depósito' : 'Editar depósito'}</h2>

			<label class="field-label" for="form-nombre">Nombre</label>
			<input
				id="form-nombre"
				class="field-input"
				type="text"
				bind:value={formNombre}
				maxlength="100"
				placeholder="Nombre del depósito"
			/>

			<div class="modal-actions">
				<button class="button button--secondary" onclick={closeForm} disabled={formSaving}>
					Cancelar
				</button>
				<button class="button button--primary" onclick={handleSave} disabled={formSaving}>
					{formSaving ? 'Guardando…' : 'Guardar'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if depositoToDelete}
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
			<h2 id="delete-title">¿Eliminar el depósito {depositoToDelete.nombre}?</h2>
			<p>
				Las asignaciones de usuarios a este depósito se quitarán automáticamente.
				Esta acción no se puede deshacer.
			</p>

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
	.depositos-page {
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

	.deposito-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.deposito-card {
		padding: 1rem;
		border: 1px solid #e2e8f0;
		border-radius: 0.75rem;
		background-color: #ffffff;
	}

	.deposito-card__header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.deposito-card__name {
		font-size: 1.125rem;
		margin: 0;
	}

	.deposito-card__meta {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		color: #475569;
		font-size: 0.875rem;
		margin-bottom: 1rem;
	}

	.deposito-card__actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.5rem;
	}

	@media (min-width: 640px) {
		.deposito-card__actions {
			grid-template-columns: repeat(2, 1fr);
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

	.modal--warning {
		border-top: 4px solid #dc2626;
	}

	.modal h2 {
		font-size: 1.25rem;
		margin: 0 0 1rem;
	}

	.modal p {
		color: #475569;
		font-size: 0.875rem;
		margin: 0 0 0.5rem;
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

	.field-input {
		width: 100%;
		min-height: 3rem;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		border: 1px solid #cbd5e1;
		border-radius: 0.5rem;
		background-color: #ffffff;
	}
</style>
