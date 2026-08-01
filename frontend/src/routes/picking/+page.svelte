<script lang="ts">
	import { fade } from 'svelte/transition';
	import Scanner from '$lib/components/Scanner.svelte';
	import ScanFlash from '$lib/components/picking/ScanFlash.svelte';
	import RemitoItemList from '$lib/components/picking/RemitoItemList.svelte';
	import RoutePanel from '$lib/components/picking/RoutePanel.svelte';
	import TalkButton from '$lib/components/picking/TalkButton.svelte';
	import { remitoState, applyServerState } from '$lib/stores/picking';
	import {
		listPickingRemitos,
		startPickingRemito,
		scanPickingCode,
		resetPickingRemito,
		finishPickingRemito,
		getTtsAudio,
		type RemitoListItem,
		type OutcomeColor
	} from '$lib/api/client';
	import { say, sayFallback, unlock, vibrate } from '$lib/audio/speaker';

	// ── View state ──────────────────────────────────────────────────────────────
	type View = 'list' | 'picking' | 'completed';
	let view = $state<View>('list');

	// ── Remito list ─────────────────────────────────────────────────────────────
	let remitos = $state<RemitoListItem[]>([]);
	let loadingList = $state(true);
	let listError = $state<string | null>(null);

	// ── Active picking session ───────────────────────────────────────────────────
	let scannerRef = $state<{ pause: () => void; resume: () => void } | null>(null);
	let lastScannedCode = $state<string | null>(null);
	let lastScannedTime = $state(0);
	const DEBOUNCE_MS = 800;

	// ── Flash feedback ───────────────────────────────────────────────────────────
	let flashVisible = $state(false);
	let flashColor = $state<OutcomeColor>('green');
	let flashText = $state('');
	let flashTimer: ReturnType<typeof setTimeout> | null = null;

	// ── Route panel ──────────────────────────────────────────────────────────────
	let showRoute = $state(false);

	// ── Reset confirm ────────────────────────────────────────────────────────────
	let resetting = $state(false);
	let resetPressTimer: ReturnType<typeof setTimeout> | null = null;

	// ── Load remito list on mount ────────────────────────────────────────────────
	async function loadList() {
		loadingList = true;
		listError = null;
		try {
			remitos = await listPickingRemitos();
		} catch (err) {
			listError = err instanceof Error ? err.message : 'Error al cargar remitos.';
		} finally {
			loadingList = false;
		}
	}

	$effect(() => {
		loadList();
	});

	// ── Start a remito ───────────────────────────────────────────────────────────
	async function handleSelectRemito(remito: RemitoListItem) {
		// Unlock audio on this real user gesture
		await unlock();

		try {
			const state = await startPickingRemito(remito.remito_id);
			applyServerState(state);
			view = 'picking';
		} catch (err) {
			listError = err instanceof Error ? err.message : 'Error al iniciar el remito.';
		}
	}

	// ── Scan handler ─────────────────────────────────────────────────────────────
	async function handleScan(rawCode: string, _formatName: string) {
		const state = $remitoState;
		if (!state) return;

		const now = Date.now();
		if (rawCode === lastScannedCode && now - lastScannedTime < DEBOUNCE_MS) {
			// Duplicate scan within debounce window — show a neutral pulse
			triggerFlash('amber', '…', 300);
			return;
		}
		lastScannedCode = rawCode;
		lastScannedTime = now;

		// Generate a stable UUID for this unique scan intention.
		// Same UUID is reused if the request is retried (on network error).
		const clientEventId = crypto.randomUUID();

		try {
			const res = await scanPickingCode(state.remito_id, rawCode, clientEventId);
			applyServerState(res.state);

			const dismissMs = res.color === 'red' ? 2200 : 900;
			triggerFlash(res.color, res.display_text, dismissMs);

			if (res.color === 'green') vibrate([0, 120]);
			else if (res.color === 'red') vibrate([0, 80, 60, 80]);

			// Fire TTS in parallel — never blocks render
			speakText(res.speech_text);

			if (res.state.estado === 'completed') {
				view = 'completed';
			}
		} catch (err) {
			const msg = err instanceof Error ? err.message : 'Error de red';
			triggerFlash('amber', msg, 2000);
		}
	}

	function handleScanError(_err: string) {
		// Scanner errors are shown inline by the Scanner component
	}

	// ── Flash ────────────────────────────────────────────────────────────────────
	function triggerFlash(color: OutcomeColor, text: string, durationMs: number) {
		if (flashTimer) clearTimeout(flashTimer);
		flashColor = color;
		flashText = text;
		flashVisible = true;
		flashTimer = setTimeout(() => {
			flashVisible = false;
		}, durationMs);
	}

	// ── Audio ─────────────────────────────────────────────────────────────────────
	async function speakText(text: string) {
		try {
			const blob = await getTtsAudio(text);
			await say(blob);
		} catch {
			sayFallback(text);
		}
	}

	// ── Reset (long press) ────────────────────────────────────────────────────────
	function handleResetPointerDown() {
		resetPressTimer = setTimeout(async () => {
			await doReset();
		}, 1200);
	}

	function handleResetPointerUp() {
		if (resetPressTimer) clearTimeout(resetPressTimer);
	}

	async function doReset() {
		const state = $remitoState;
		if (!state) return;
		resetting = true;
		try {
			const fresh = await resetPickingRemito(state.remito_id);
			applyServerState(fresh);
			lastScannedCode = null;
			lastScannedTime = 0;
			flashVisible = false;
			showRoute = false;
			view = 'picking';
		} catch (err) {
			triggerFlash('amber', err instanceof Error ? err.message : 'Error al resetear.', 2000);
		} finally {
			resetting = false;
		}
	}

	// ── Finish ───────────────────────────────────────────────────────────────────
	async function handleFinish() {
		const state = $remitoState;
		if (!state) return;
		try {
			await finishPickingRemito(state.remito_id);
			remitoState.set(null);
			view = 'list';
			loadList();
		} catch (err) {
			triggerFlash('amber', err instanceof Error ? err.message : 'Error al finalizar.', 2000);
		}
	}

	// ── Back to list ─────────────────────────────────────────────────────────────
	function handleBackToList() {
		remitoState.set(null);
		view = 'list';
		lastScannedCode = null;
	}

	// ── Derived ──────────────────────────────────────────────────────────────────
	const estado = $derived($remitoState);
	const progresoPct = $derived(
		estado ? Math.round((estado.lineas_completas / estado.total_lineas) * 100) : 0
	);
	const siguiente = $derived(
		estado?.ruta?.paradas.find((p) => p.es_siguiente) ?? null
	);
</script>

<svelte:head>
	<title>InvenTIA — Modo Remito</title>
</svelte:head>

{#if view === 'list'}
	<!-- ────────────────────────── REMITO LIST ────────────────────────── -->
	<div class="picking-page" transition:fade={{ duration: 160 }}>
		<header class="picking-page__topbar">
			<a href="/" class="picking-page__back" aria-label="Volver al inicio">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<polyline points="15 18 9 12 15 6"></polyline>
				</svg>
			</a>
			<span class="picking-page__topbar-title">Modo Remito</span>
		</header>

		<main class="picking-page__main">
			{#if loadingList}
				<div class="picking-page__loading" role="status">
					<span class="picking-page__spinner" aria-hidden="true"></span>
					<span>Cargando remitos…</span>
				</div>
			{:else if listError}
				<div class="picking-page__error" role="alert">
					<p>{listError}</p>
					<button type="button" class="btn btn--primary" onclick={loadList}>Reintentar</button>
				</div>
			{:else if remitos.length === 0}
				<div class="picking-page__empty">No hay remitos disponibles.</div>
			{:else}
				<div class="picking-page__section-label">Seleccioná un remito para comenzar</div>
				<ul class="remito-list" role="list">
					{#each remitos as remito (remito.remito_id)}
						<li>
							<button
								type="button"
								class="remito-card"
								class:remito-card--in-progress={remito.estado === 'in_progress'}
								class:remito-card--completed={remito.estado === 'completed'}
								onclick={() => handleSelectRemito(remito)}
							>
								<div class="remito-card__header">
									<span class="remito-card__ref">{remito.referencia}</span>
									<span class="remito-card__badge remito-card__badge--{remito.estado}">
										{#if remito.estado === 'ready'}Listo
										{:else if remito.estado === 'in_progress'}En curso
										{:else}Completado{/if}
									</span>
								</div>
								<div class="remito-card__progress-bar">
									<div
										class="remito-card__progress-fill"
										style="width: {Math.round((remito.lineas_completas / remito.total_lineas) * 100)}%"
									></div>
								</div>
								<div class="remito-card__meta">
									<span>{remito.lineas_completas}/{remito.total_lineas} líneas</span>
									{#if remito.es_demo}
										<span class="remito-card__demo-pill">DEMO</span>
									{/if}
								</div>
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</main>
	</div>

{:else if view === 'picking' && estado}
	<!-- ────────────────────────── PICKING ACTIVO ────────────────────────── -->
	<div class="picking-page picking-page--active" transition:fade={{ duration: 160 }}>

		<!-- Top bar -->
		<header class="picking-page__topbar">
			<button type="button" class="picking-page__back" onclick={handleBackToList} aria-label="Volver a remitos">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<polyline points="15 18 9 12 15 6"></polyline>
				</svg>
			</button>
			<div class="picking-page__topbar-center">
				<span class="picking-page__topbar-title">{estado.referencia}</span>
				<span class="picking-page__topbar-sub">{estado.lineas_completas}/{estado.total_lineas}</span>
			</div>
			<button
				type="button"
				class="picking-page__route-btn"
				onclick={() => (showRoute = !showRoute)}
				aria-label="Ver ruta"
			>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
				</svg>
			</button>
		</header>

		<!-- Progress bar -->
		<div class="picking-progress" role="progressbar" aria-valuenow={progresoPct} aria-valuemin={0} aria-valuemax={100} aria-label="Progreso del remito">
			<div class="picking-progress__fill" style="width: {progresoPct}%"></div>
		</div>

		<!-- Next stop hero (only when anchor is set and route exists) -->
		{#if siguiente && estado.anchor_ubicacion_qr}
			<div class="picking-next">
				<span class="picking-next__label">Siguiente</span>
				<span class="picking-next__desc">{siguiente.descripcion}</span>
				<span class="picking-next__ubicacion">{siguiente.ubicacion_hablada}</span>
			</div>
		{:else if !estado.anchor_ubicacion_qr}
			<div class="picking-hint">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="12" r="10"></circle>
					<line x1="12" y1="8" x2="12" y2="12"></line>
					<line x1="12" y1="16" x2="12.01" y2="16"></line>
				</svg>
				<span>Escaneá cualquier producto para anclar tu posición</span>
			</div>
		{/if}

		<!-- Scanner -->
		<div class="picking-scanner">
			<Scanner bind:this={scannerRef} onScan={handleScan} onError={handleScanError} />
		</div>

		<!-- Checklist -->
		<div class="picking-items">
			<RemitoItemList items={estado.items} ruta={estado.ruta} />
		</div>

		<!-- Bottom controls -->
		<div class="picking-controls">
			<TalkButton remito={estado} scannerRef={scannerRef} />

			<div class="picking-controls__row">
				<!-- Long-press to reset -->
				<button
					type="button"
					class="btn btn--ghost"
					class:btn--loading={resetting}
					onpointerdown={handleResetPointerDown}
					onpointerup={handleResetPointerUp}
					onpointercancel={handleResetPointerUp}
					aria-label="Mantener presionado para resetear la demo"
				>
					{resetting ? 'Reseteando…' : 'Reset demo'}
				</button>

				<button
					type="button"
					class="btn btn--danger"
					onclick={handleFinish}
					aria-label="Finalizar remito"
				>
					Finalizar
				</button>
			</div>
		</div>
	</div>

	<!-- Flash overlay (full screen) -->
	<ScanFlash color={flashColor} text={flashText} visible={flashVisible} />

	<!-- Route panel (slide up sheet) -->
	{#if showRoute && estado.ruta}
		<RoutePanel ruta={estado.ruta} onClose={() => (showRoute = false)} />
	{/if}

{:else if view === 'completed'}
	<!-- ────────────────────────── COMPLETED ────────────────────────── -->
	<div class="picking-page picking-page--done" transition:fade={{ duration: 200 }}>
		<div class="picking-done">
			<div class="picking-done__icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
					<polyline points="22 4 12 14.01 9 11.01"></polyline>
				</svg>
			</div>
			<h1 class="picking-done__title">Remito completado</h1>
			{#if estado}
				<p class="picking-done__sub">{estado.referencia} — {estado.total_lineas} líneas pickeadas</p>
			{/if}
			<button type="button" class="btn btn--primary picking-done__cta" onclick={handleFinish}>
				Nuevo remito
			</button>
		</div>
	</div>
{/if}

<style>
	/* ── Page shell ── */
	.picking-page {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
		background-color: #f8fafc;
	}

	.picking-page--active {
		background-color: #ffffff;
	}

	/* ── Top bar ── */
	.picking-page__topbar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background-color: #ffffff;
		border-bottom: 1px solid #e2e8f0;
		min-height: 3.5rem;
		position: sticky;
		top: 0;
		z-index: 10;
	}

	.picking-page__back {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		color: #334155;
		background: none;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		padding: 0;
		flex-shrink: 0;
		text-decoration: none;
	}

	.picking-page__back:active {
		background-color: #f1f5f9;
	}

	.picking-page__back svg {
		width: 1.375rem;
		height: 1.375rem;
	}

	.picking-page__topbar-center {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.picking-page__topbar-title {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.picking-page__topbar-sub {
		font-size: 0.8125rem;
		color: #64748b;
		font-weight: 500;
	}

	.picking-page__route-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		color: #2563eb;
		background: none;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		padding: 0;
		flex-shrink: 0;
	}

	.picking-page__route-btn svg {
		width: 1.25rem;
		height: 1.25rem;
	}

	/* ── Progress bar ── */
	.picking-progress {
		height: 3px;
		background-color: #e2e8f0;
		overflow: hidden;
	}

	.picking-progress__fill {
		height: 100%;
		background-color: #2563eb;
		transition: width 0.4s ease;
	}

	/* ── Next stop hero ── */
	.picking-next {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem 1rem;
		background-color: #eff6ff;
		border-bottom: 1px solid #bfdbfe;
	}

	.picking-next__label {
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #2563eb;
	}

	.picking-next__desc {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
		line-height: 1.3;
	}

	.picking-next__ubicacion {
		font-size: 0.875rem;
		font-weight: 600;
		color: #1d4ed8;
	}

	/* ── Anchor hint ── */
	.picking-hint {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.625rem 1rem;
		background-color: #fefce8;
		border-bottom: 1px solid #fde68a;
		font-size: 0.875rem;
		font-weight: 600;
		color: #92400e;
	}

	.picking-hint svg {
		width: 1.125rem;
		height: 1.125rem;
		flex-shrink: 0;
	}

	/* ── Scanner area ── */
	.picking-scanner {
		padding: 0.75rem 1rem 0;
	}

	/* ── Checklist ── */
	.picking-items {
		padding: 0.75rem 1rem;
		flex: 1 1 auto;
		overflow-y: auto;
	}

	/* ── Bottom controls ── */
	.picking-controls {
		padding: 0.75rem 1rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		border-top: 1px solid #e2e8f0;
		background-color: #ffffff;
		position: sticky;
		bottom: 0;
	}

	.picking-controls__row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.625rem;
	}

	/* ── Remito list ── */
	.picking-page__main {
		padding: 1rem;
		flex: 1;
	}

	.picking-page__section-label {
		font-size: 0.8125rem;
		font-weight: 600;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		margin-bottom: 0.75rem;
	}

	.remito-list {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.remito-card {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		background-color: #ffffff;
		border: 1.5px solid #e2e8f0;
		border-radius: 0.875rem;
		cursor: pointer;
		text-align: left;
		touch-action: manipulation;
		transition: border-color 0.15s ease, box-shadow 0.15s ease;
	}

	.remito-card:active {
		border-color: #2563eb;
		box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
	}

	.remito-card--in-progress {
		border-color: #93c5fd;
		background-color: #f0f9ff;
	}

	.remito-card--completed {
		border-color: #bbf7d0;
		background-color: #f0fdf4;
		opacity: 0.7;
	}

	.remito-card__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.remito-card__ref {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
	}

	.remito-card__badge {
		padding: 0.1875rem 0.625rem;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		border-radius: 9999px;
	}

	.remito-card__badge--ready {
		color: #334155;
		background-color: #f1f5f9;
	}

	.remito-card__badge--in_progress {
		color: #1d4ed8;
		background-color: #dbeafe;
	}

	.remito-card__badge--completed {
		color: #15803d;
		background-color: #dcfce7;
	}

	.remito-card__progress-bar {
		height: 4px;
		background-color: #e2e8f0;
		border-radius: 9999px;
		overflow: hidden;
	}

	.remito-card__progress-fill {
		height: 100%;
		background-color: #2563eb;
		border-radius: 9999px;
		transition: width 0.3s ease;
	}

	.remito-card__meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		font-size: 0.8125rem;
		color: #64748b;
		font-weight: 500;
	}

	.remito-card__demo-pill {
		padding: 0.125rem 0.5rem;
		font-size: 0.6875rem;
		font-weight: 700;
		color: #7c3aed;
		background-color: #ede9fe;
		border-radius: 9999px;
	}

	/* ── Completed screen ── */
	.picking-page--done {
		align-items: center;
		justify-content: center;
	}

	.picking-done {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 2rem 1.5rem;
		text-align: center;
	}

	.picking-done__icon {
		width: 5rem;
		height: 5rem;
		color: #16a34a;
	}

	.picking-done__icon svg {
		width: 100%;
		height: 100%;
	}

	.picking-done__title {
		font-size: 1.5rem;
		font-weight: 800;
		color: #0f172a;
		margin: 0;
	}

	.picking-done__sub {
		font-size: 1rem;
		color: #64748b;
		margin: 0;
	}

	.picking-done__cta {
		margin-top: 0.5rem;
		min-width: 12rem;
	}

	/* ── Shared buttons ── */
	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 3rem;
		padding: 0.75rem 1.25rem;
		font-size: 0.9375rem;
		font-weight: 700;
		border: none;
		border-radius: 0.625rem;
		cursor: pointer;
		touch-action: manipulation;
	}

	.btn--primary {
		color: #ffffff;
		background-color: #2563eb;
	}

	.btn--primary:active {
		background-color: #1d4ed8;
	}

	.btn--ghost {
		color: #334155;
		background-color: #f1f5f9;
	}

	.btn--ghost:active {
		background-color: #e2e8f0;
	}

	.btn--danger {
		color: #ffffff;
		background-color: #dc2626;
	}

	.btn--danger:active {
		background-color: #b91c1c;
	}

	.btn--loading {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* ── States ── */
	.picking-page__loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 3rem 1rem;
		color: #64748b;
		font-size: 0.9375rem;
	}

	.picking-page__spinner {
		display: inline-block;
		width: 2rem;
		height: 2rem;
		border: 3px solid #e2e8f0;
		border-top-color: #2563eb;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.picking-page__error {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 2rem 1rem;
		text-align: center;
	}

	.picking-page__error p {
		font-size: 0.9375rem;
		color: #dc2626;
		font-weight: 600;
		margin: 0;
	}

	.picking-page__empty {
		padding: 2rem 1rem;
		text-align: center;
		font-size: 1rem;
		color: #64748b;
	}
</style>
