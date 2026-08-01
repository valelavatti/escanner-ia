<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { cubicOut, quintOut } from 'svelte/easing';

	// ─── Types ────────────────────────────────────────────────────────────────
	type ScanOutcome = 'correct' | 'incorrect';
	type AIStatus = 'idle' | 'listening' | 'thinking' | 'speaking';

	interface Message {
		id: number;
		role: 'user' | 'ai';
		text: string;
		outcome?: ScanOutcome;
		ts: string;
	}

	// ─── Demo product context ─────────────────────────────────────────────────
	const PRODUCT = {
		sku: 'ELC-7842-B',
		descripcion: 'Cable HDMI 2.1 Premium 2m',
		ubicacion: 'EST-A3 F2-C4',
		deposito: 'Depósito Central',
		cantidad: 24
	};

	// ─── Canned AI responses ──────────────────────────────────────────────────
	const RESPONSES: Record<string, string[]> = {
		correct: [
			'Perfecto, escaneo registrado. Siguiente ítem: Cable HDMI en EST-A3, fila 2, columna 4.',
			'Correcto. Quedan 11 ítems en el remito. Continuá por el pasillo A.',
			'Registrado. Avanzá hacia EST-B1 para el próximo producto.'
		],
		incorrect: [
			'Espera. Verificá el SKU: debería ser ELC-7842-B. Fijate que el cable sea negro, no blanco.',
			'Ese no es el producto correcto. El Cable HDMI 2.1 está en EST-A3, fila 2, columna 4 — no en fila 3.',
			'Error de escaneo. Revisá que estés en el estante A3 y no en A2. El producto tiene etiqueta azul.'
		],
		greeting: [
			'Hola. Tenés el remito REM-2847 activo con 14 ítems. Primer producto: Cable HDMI 2.1 en EST-A3, fila 2, columna 4.',
		],
		question: [
			'El producto está en el pasillo A, tercer estante desde la entrada. Fila 2, cuarta columna desde la izquierda.',
			'Tenés 24 unidades disponibles en EST-A3. El mínimo de stock es 10.',
			'El remito vence hoy a las 18:00. Quedan 11 ítems por confirmar.'
		]
	};

	function pickRandom(arr: string[]) {
		return arr[Math.floor(Math.random() * arr.length)];
	}

	// ─── State ────────────────────────────────────────────────────────────────
	let msgId = 0;
	let aiStatus = $state<AIStatus>('idle');
	let messages = $state<Message[]>([
		{
			id: msgId++,
			role: 'ai',
			text: RESPONSES.greeting[0],
			ts: now()
		}
	]);
	let inputText = $state('');
	let messagesEl = $state<HTMLElement | undefined>(undefined);
	let muted = $state(false);
	let isSpeaking = $state(false);

	// Waveform bars
	let waveHeights = $state<number[]>(Array.from({ length: 18 }, () => 4));
	let waveTimer: ReturnType<typeof setInterval> | null = null;

	// Orb animation frame
	let orbPhase = $state(0);
	let orbTimer: ReturnType<typeof setInterval> | null = null;

	// ─── Helpers ──────────────────────────────────────────────────────────────
	function now(): string {
		return new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
	}

	function startOrb() {
		orbTimer = setInterval(() => {
			orbPhase = (orbPhase + 1) % 360;
		}, 16);
	}

	function stopOrb() {
		if (orbTimer) { clearInterval(orbTimer); orbTimer = null; }
		orbPhase = 0;
	}

	function startWave() {
		isSpeaking = true;
		waveTimer = setInterval(() => {
			waveHeights = waveHeights.map(() => 3 + Math.random() * 22);
		}, 80);
	}

	function stopWave() {
		isSpeaking = false;
		if (waveTimer) { clearInterval(waveTimer); waveTimer = null; }
		waveHeights = Array.from({ length: 18 }, (_, i) => 3 + Math.sin(i * 0.6) * 4);
	}

	function speak(text: string) {
		if (!('speechSynthesis' in window)) return;
		window.speechSynthesis.cancel();
		if (muted) return;
		const utt = new SpeechSynthesisUtterance(text);
		utt.lang = 'es-AR';
		utt.rate = 1.05;
		utt.pitch = 1;
		utt.onstart = () => { startWave(); };
		utt.onend = () => { stopWave(); aiStatus = 'idle'; };
		utt.onerror = () => { stopWave(); aiStatus = 'idle'; };
		window.speechSynthesis.speak(utt);
	}

	function scrollBottom() {
		requestAnimationFrame(() => {
			if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
		});
	}

	function pushAI(text: string, extra?: Partial<Message>) {
		messages = [
			...messages,
			{ id: msgId++, role: 'ai', text, ts: now(), ...extra }
		];
		scrollBottom();
	}

	function pushUser(text: string, extra?: Partial<Message>) {
		messages = [
			...messages,
			{ id: msgId++, role: 'user', text, ts: now(), ...extra }
		];
		scrollBottom();
	}

	async function simulateAIResponse(responseKey: keyof typeof RESPONSES) {
		aiStatus = 'thinking';
		startOrb();
		await new Promise(r => setTimeout(r, 900 + Math.random() * 400));
		stopOrb();
		aiStatus = 'speaking';
		const reply = pickRandom(RESPONSES[responseKey]);
		pushAI(reply);
		speak(reply);
	}

	async function handleOutcome(outcome: ScanOutcome) {
		if (aiStatus !== 'idle') return;
		const label = outcome === 'correct' ? 'Escaneo correcto confirmado.' : 'Escaneo incorrecto reportado.';
		pushUser(label, { outcome });
		await simulateAIResponse(outcome);
	}

	async function handleSend() {
		const text = inputText.trim();
		if (!text || aiStatus !== 'idle') return;
		inputText = '';
		pushUser(text);
		await simulateAIResponse('question');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && e.keyCode !== 229) {
			e.preventDefault();
			handleSend();
		}
	}

	function toggleMute() {
		muted = !muted;
		if (muted) { window.speechSynthesis?.cancel(); stopWave(); aiStatus = 'idle'; }
	}

	const orbGradientStart = $derived(
		aiStatus === 'thinking' ? '#7c3aed' :
		aiStatus === 'speaking' ? '#0ea5e9' :
		aiStatus === 'listening' ? '#059669' :
		'#1d4ed8'
	);
	const orbGradientEnd = $derived(
		aiStatus === 'thinking' ? '#a855f7' :
		aiStatus === 'speaking' ? '#38bdf8' :
		aiStatus === 'listening' ? '#10b981' :
		'#3b82f6'
	);
</script>

<svelte:head>
	<title>Asistente IA — Picking</title>
	<meta name="description" content="Demo del asistente de voz para operaciones de picking en depósito." />
</svelte:head>

<main class="app">
	<!-- ─── Top bar ──────────────────────────────────────────────────────────── -->
	<header class="topbar">
		<div class="topbar__left">
			<div class="topbar__logo" aria-hidden="true">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
					<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
					<polyline points="9 22 9 12 15 12 15 22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
				</svg>
			</div>
			<div>
				<p class="topbar__title">Depósito Central</p>
				<p class="topbar__sub">REM-2847 · 14 ítems</p>
			</div>
		</div>
		<div class="topbar__right">
			<div class="topbar__ai-badge" class:topbar__ai-badge--active={aiStatus !== 'idle'}>
				<span class="topbar__ai-dot"></span>
				{#if aiStatus === 'thinking'}
					Pensando
				{:else if aiStatus === 'speaking'}
					Hablando
				{:else}
					IA activa
				{/if}
			</div>
		</div>
	</header>

	<!-- ─── Product context card ─────────────────────────────────────────────── -->
	<section class="product-card" aria-label="Producto activo">
		<div class="product-card__icon" aria-hidden="true">
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
				<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
				<polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
				<line x1="12" y1="22.08" x2="12" y2="12"/>
			</svg>
		</div>
		<div class="product-card__info">
			<p class="product-card__sku">{PRODUCT.sku}</p>
			<p class="product-card__desc">{PRODUCT.descripcion}</p>
		</div>
		<div class="product-card__meta">
			<span class="product-card__location">
				<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
					<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
				</svg>
				{PRODUCT.ubicacion}
			</span>
			<span class="product-card__qty">×{PRODUCT.cantidad}</span>
		</div>
	</section>

	<!-- ─── AI Voice orb + outcome buttons ──────────────────────────────────── -->
	<section class="voice-section" aria-label="Control de voz">
		<!-- Outcome buttons -->
		<button
			class="outcome-btn outcome-btn--incorrect"
			onclick={() => handleOutcome('incorrect')}
			disabled={aiStatus !== 'idle'}
			aria-label="Escaneo incorrecto"
		>
			<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
				<line x1="18" y1="6" x2="6" y2="18"/>
				<line x1="6" y1="6" x2="18" y2="18"/>
			</svg>
			<span>Incorrecto</span>
		</button>

		<!-- Central orb -->
		<div class="orb-wrap" aria-live="polite" aria-label="Estado del asistente">
			<div
				class="orb"
				class:orb--active={aiStatus !== 'idle'}
				style="--orb-start: {orbGradientStart}; --orb-end: {orbGradientEnd};"
			>
				<!-- Pulse rings -->
				{#if aiStatus !== 'idle'}
					<div class="orb__ring orb__ring--1" transition:fade={{ duration: 300 }}></div>
					<div class="orb__ring orb__ring--2" transition:fade={{ duration: 300 }}></div>
				{/if}

				<!-- Waveform inside orb when speaking -->
				{#if isSpeaking}
					<div class="orb__wave" aria-hidden="true" transition:fade={{ duration: 150 }}>
						{#each waveHeights as h, i}
							<span class="orb__bar" style="height: {h}px; animation-delay: {i * 40}ms;"></span>
						{/each}
					</div>
				{:else if aiStatus === 'thinking'}
					<div class="orb__dots" aria-hidden="true" transition:fade={{ duration: 150 }}>
						<span></span><span></span><span></span>
					</div>
				{:else}
					<div class="orb__icon" transition:fade={{ duration: 150 }}>
						<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
							<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
							<line x1="12" y1="19" x2="12" y2="23"/>
							<line x1="8" y1="23" x2="16" y2="23"/>
						</svg>
					</div>
				{/if}
			</div>

			<!-- Status label -->
			<p class="orb__label">
				{#if aiStatus === 'idle'}
					Listo para escuchar
				{:else if aiStatus === 'thinking'}
					Procesando...
				{:else if aiStatus === 'speaking'}
					Respondiendo
				{/if}
			</p>
		</div>

		<!-- Correct button -->
		<button
			class="outcome-btn outcome-btn--correct"
			onclick={() => handleOutcome('correct')}
			disabled={aiStatus !== 'idle'}
			aria-label="Escaneo correcto"
		>
			<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<polyline points="20 6 9 17 4 12"/>
			</svg>
			<span>Correcto</span>
		</button>
	</section>

	<!-- ─── Conversation ──────────────────────────────────────────────────────── -->
	<section
		class="messages"
		bind:this={messagesEl}
		aria-live="polite"
		aria-label="Conversación con el asistente"
	>
		{#each messages as msg (msg.id)}
			<div
				class="msg"
				class:msg--ai={msg.role === 'ai'}
				class:msg--user={msg.role === 'user'}
				class:msg--correct={msg.outcome === 'correct'}
				class:msg--incorrect={msg.outcome === 'incorrect'}
				transition:fly={{ y: 12, duration: 240, easing: cubicOut }}
			>
				{#if msg.role === 'ai'}
					<div class="msg__avatar" aria-hidden="true">IA</div>
				{/if}
				<div class="msg__body">
					<p class="msg__text">{msg.text}</p>
					<time class="msg__ts" datetime={new Date().toISOString()}>{msg.ts}</time>
				</div>
			</div>
		{/each}

		{#if aiStatus === 'thinking'}
			<div class="msg msg--ai" transition:fade={{ duration: 150 }}>
				<div class="msg__avatar" aria-hidden="true">IA</div>
				<div class="msg__body">
					<div class="typing-dots"><span></span><span></span><span></span></div>
				</div>
			</div>
		{/if}
	</section>

	<!-- ─── Input row ─────────────────────────────────────────────────────────── -->
	<footer class="input-row">
		<button
			class="input-row__mute"
			class:input-row__mute--off={muted}
			onclick={toggleMute}
			aria-label={muted ? 'Activar voz' : 'Silenciar voz'}
		>
			{#if muted}
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
					<line x1="1" y1="1" x2="23" y2="23"/>
					<path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
					<path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
					<line x1="12" y1="19" x2="12" y2="23"/>
					<line x1="8" y1="23" x2="16" y2="23"/>
				</svg>
			{:else}
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
					<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
					<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
					<line x1="12" y1="19" x2="12" y2="23"/>
					<line x1="8" y1="23" x2="16" y2="23"/>
				</svg>
			{/if}
		</button>

		<input
			type="text"
			class="input-row__field"
			placeholder="Preguntale algo al asistente..."
			bind:value={inputText}
			onkeydown={handleKeydown}
			disabled={aiStatus !== 'idle'}
			aria-label="Mensaje al asistente"
			autocomplete="off"
			autocorrect="off"
			spellcheck="false"
		/>

		<button
			class="input-row__send"
			onclick={handleSend}
			disabled={aiStatus !== 'idle' || !inputText.trim()}
			aria-label="Enviar"
		>
			<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="22" y1="2" x2="11" y2="13"/>
				<polygon points="22 2 15 22 11 13 2 9 22 2"/>
			</svg>
		</button>
	</footer>
</main>

<style>
	/* ─── Reset & tokens ──────────────────────────────────────────────────────── */
	*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

	:global(html), :global(body) {
		height: 100%;
		background: #060b14;
	}

	.app {
		display: flex;
		flex-direction: column;
		height: 100dvh;
		max-width: 480px;
		margin: 0 auto;
		background: #060b14;
		color: #e2e8f0;
		font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
		-webkit-font-smoothing: antialiased;
		overflow: hidden;
	}

	/* ─── Top bar ─────────────────────────────────────────────────────────────── */
	.topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.875rem 1.25rem 0.75rem;
		border-bottom: 1px solid rgba(255,255,255,0.05);
		flex-shrink: 0;
	}

	.topbar__left {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.topbar__logo {
		width: 2rem;
		height: 2rem;
		border-radius: 0.5rem;
		background: rgba(37,99,235,0.15);
		border: 1px solid rgba(37,99,235,0.25);
		display: flex;
		align-items: center;
		justify-content: center;
		color: #60a5fa;
		flex-shrink: 0;
	}

	.topbar__title {
		font-size: 0.9375rem;
		font-weight: 700;
		color: #f1f5f9;
		letter-spacing: -0.01em;
		line-height: 1.2;
	}

	.topbar__sub {
		font-size: 0.71875rem;
		color: #475569;
		margin-top: 0.0625rem;
		line-height: 1.2;
	}

	.topbar__ai-badge {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.3125rem 0.625rem;
		border-radius: 99px;
		font-size: 0.6875rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		text-transform: uppercase;
		background: rgba(255,255,255,0.04);
		border: 1px solid rgba(255,255,255,0.08);
		color: #475569;
		transition: background 0.3s, color 0.3s, border-color 0.3s;
	}

	.topbar__ai-badge--active {
		background: rgba(37,99,235,0.12);
		border-color: rgba(37,99,235,0.3);
		color: #93c5fd;
	}

	.topbar__ai-dot {
		display: inline-block;
		width: 0.4375rem;
		height: 0.4375rem;
		border-radius: 50%;
		background: #22c55e;
		animation: pulse-dot 2s ease-in-out infinite;
	}

	@keyframes pulse-dot {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.5; transform: scale(0.85); }
	}

	/* ─── Product card ────────────────────────────────────────────────────────── */
	.product-card {
		display: flex;
		align-items: center;
		gap: 0.875rem;
		margin: 0.875rem 1.25rem;
		padding: 0.875rem 1rem;
		background: rgba(255,255,255,0.035);
		border: 1px solid rgba(255,255,255,0.07);
		border-radius: 1rem;
		flex-shrink: 0;
	}

	.product-card__icon {
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 0.75rem;
		background: rgba(37,99,235,0.1);
		border: 1px solid rgba(37,99,235,0.18);
		display: flex;
		align-items: center;
		justify-content: center;
		color: #60a5fa;
		flex-shrink: 0;
	}

	.product-card__info {
		flex: 1 1 auto;
		min-width: 0;
	}

	.product-card__sku {
		font-size: 0.75rem;
		font-weight: 700;
		color: #93c5fd;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		line-height: 1.2;
	}

	.product-card__desc {
		font-size: 0.875rem;
		color: #cbd5e1;
		margin-top: 0.1875rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		line-height: 1.3;
	}

	.product-card__meta {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.25rem;
		flex-shrink: 0;
	}

	.product-card__location {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.6875rem;
		font-weight: 600;
		color: #86efac;
		background: rgba(22,163,74,0.1);
		border: 1px solid rgba(22,163,74,0.2);
		padding: 0.1875rem 0.5rem;
		border-radius: 99px;
		white-space: nowrap;
	}

	.product-card__qty {
		font-size: 0.6875rem;
		font-weight: 700;
		color: #64748b;
		letter-spacing: 0.02em;
	}

	/* ─── Voice section ───────────────────────────────────────────────────────── */
	.voice-section {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0;
		padding: 0.5rem 1.25rem 0.75rem;
		flex-shrink: 0;
	}

	/* Outcome buttons */
	.outcome-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.375rem;
		width: 5rem;
		height: 5.5rem;
		border: none;
		border-radius: 1.25rem;
		font-size: 0.6875rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		text-transform: uppercase;
		cursor: pointer;
		touch-action: manipulation;
		transition: transform 0.12s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease, opacity 0.2s;
		flex-shrink: 0;
	}

	.outcome-btn:disabled {
		opacity: 0.3;
		cursor: not-allowed;
		transform: none !important;
	}

	.outcome-btn:not(:disabled):active {
		transform: scale(0.93);
	}

	.outcome-btn--incorrect {
		background: rgba(220,38,38,0.12);
		border: 1.5px solid rgba(220,38,38,0.3);
		color: #fca5a5;
		box-shadow: 0 4px 20px rgba(220,38,38,0.12);
	}

	.outcome-btn--incorrect:not(:disabled):hover {
		background: rgba(220,38,38,0.22);
		border-color: rgba(220,38,38,0.5);
		box-shadow: 0 4px 24px rgba(220,38,38,0.28);
		transform: scale(1.04);
	}

	.outcome-btn--correct {
		background: rgba(22,163,74,0.12);
		border: 1.5px solid rgba(22,163,74,0.3);
		color: #86efac;
		box-shadow: 0 4px 20px rgba(22,163,74,0.12);
	}

	.outcome-btn--correct:not(:disabled):hover {
		background: rgba(22,163,74,0.22);
		border-color: rgba(22,163,74,0.5);
		box-shadow: 0 4px 24px rgba(22,163,74,0.28);
		transform: scale(1.04);
	}

	/* Orb */
	.orb-wrap {
		flex: 1 1 auto;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.625rem;
	}

	.orb {
		position: relative;
		width: 7rem;
		height: 7rem;
		border-radius: 50%;
		background: radial-gradient(circle at 40% 35%, var(--orb-end), var(--orb-start));
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background 0.5s ease;
		box-shadow: 0 8px 32px rgba(37,99,235,0.2);
	}

	.orb--active {
		animation: orb-breathe 2s ease-in-out infinite;
		box-shadow: 0 8px 48px rgba(37,99,235,0.35);
	}

	@keyframes orb-breathe {
		0%, 100% { transform: scale(1); box-shadow: 0 8px 32px rgba(37,99,235,0.25); }
		50% { transform: scale(1.05); box-shadow: 0 12px 52px rgba(37,99,235,0.45); }
	}

	/* Pulse rings */
	.orb__ring {
		position: absolute;
		inset: -6px;
		border-radius: 50%;
		border: 1.5px solid rgba(59,130,246,0.35);
		animation: ring-expand 2s ease-out infinite;
	}

	.orb__ring--2 {
		inset: -14px;
		animation-delay: 0.6s;
		border-color: rgba(59,130,246,0.18);
	}

	@keyframes ring-expand {
		0% { opacity: 1; transform: scale(0.95); }
		100% { opacity: 0; transform: scale(1.15); }
	}

	/* Wave inside orb */
	.orb__wave {
		display: flex;
		align-items: center;
		gap: 2.5px;
		height: 36px;
	}

	.orb__bar {
		display: block;
		width: 2.5px;
		background: rgba(255,255,255,0.85);
		border-radius: 2px;
		min-height: 3px;
		transition: height 0.07s ease;
	}

	/* Thinking dots inside orb */
	.orb__dots {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.orb__dots span {
		display: block;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: rgba(255,255,255,0.7);
		animation: bounce-dot 1.1s ease-in-out infinite;
	}

	.orb__dots span:nth-child(2) { animation-delay: 0.16s; }
	.orb__dots span:nth-child(3) { animation-delay: 0.32s; }

	@keyframes bounce-dot {
		0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
		40% { transform: scale(1); opacity: 1; }
	}

	/* Mic icon inside orb */
	.orb__icon {
		color: rgba(255,255,255,0.9);
	}

	/* Status label below orb */
	.orb__label {
		font-size: 0.71875rem;
		font-weight: 500;
		color: #475569;
		letter-spacing: 0.01em;
		text-align: center;
		height: 1rem;
	}

	/* ─── Messages ────────────────────────────────────────────────────────────── */
	.messages {
		flex: 1 1 auto;
		overflow-y: auto;
		padding: 0.5rem 1.125rem 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		border-top: 1px solid rgba(255,255,255,0.04);
		scroll-behavior: smooth;
	}

	.messages::-webkit-scrollbar { width: 0.125rem; }
	.messages::-webkit-scrollbar-track { background: transparent; }
	.messages::-webkit-scrollbar-thumb {
		background: rgba(255,255,255,0.08);
		border-radius: 99px;
	}

	.msg {
		display: flex;
		align-items: flex-end;
		gap: 0.5rem;
		max-width: 100%;
	}

	.msg--user {
		flex-direction: row-reverse;
	}

	.msg__avatar {
		width: 1.625rem;
		height: 1.625rem;
		border-radius: 50%;
		background: linear-gradient(135deg, #1d4ed8, #3b82f6);
		color: #fff;
		font-size: 0.5rem;
		font-weight: 800;
		letter-spacing: 0.03em;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.msg__body {
		display: flex;
		flex-direction: column;
		gap: 0.1875rem;
		max-width: 78%;
	}

	.msg--user .msg__body { align-items: flex-end; }

	.msg__text {
		margin: 0;
		padding: 0.5625rem 0.875rem;
		border-radius: 1.125rem;
		font-size: 0.9rem;
		line-height: 1.5;
		word-break: break-word;
	}

	.msg--ai .msg__text {
		background: rgba(255,255,255,0.055);
		border: 1px solid rgba(255,255,255,0.07);
		color: #cbd5e1;
		border-bottom-left-radius: 0.25rem;
	}

	.msg--user .msg__text {
		background: #1e40af;
		color: #eff6ff;
		border-bottom-right-radius: 0.25rem;
	}

	.msg--correct .msg__text {
		background: rgba(22,163,74,0.15) !important;
		border: 1px solid rgba(22,163,74,0.3) !important;
		color: #bbf7d0 !important;
		font-weight: 600;
	}

	.msg--incorrect .msg__text {
		background: rgba(220,38,38,0.15) !important;
		border: 1px solid rgba(220,38,38,0.3) !important;
		color: #fecaca !important;
		font-weight: 600;
	}

	.msg__ts {
		font-size: 0.625rem;
		color: #334155;
		letter-spacing: 0.01em;
	}

	/* Typing dots */
	.typing-dots {
		display: flex;
		align-items: center;
		gap: 0.3125rem;
		padding: 0.625rem 0.875rem;
		background: rgba(255,255,255,0.055);
		border: 1px solid rgba(255,255,255,0.07);
		border-radius: 1.125rem;
		border-bottom-left-radius: 0.25rem;
	}

	.typing-dots span {
		display: block;
		width: 5px;
		height: 5px;
		background: #475569;
		border-radius: 50%;
		animation: bounce-dot 1.2s ease-in-out infinite;
	}

	.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
	.typing-dots span:nth-child(3) { animation-delay: 0.3s; }

	/* ─── Input row ───────────────────────────────────────────────────────────── */
	.input-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.625rem 1rem calc(0.625rem + env(safe-area-inset-bottom, 0px));
		border-top: 1px solid rgba(255,255,255,0.05);
		flex-shrink: 0;
		background: #060b14;
	}

	.input-row__mute {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 0.75rem;
		border: 1px solid rgba(255,255,255,0.08);
		background: rgba(255,255,255,0.04);
		color: #475569;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.15s, color 0.15s, border-color 0.15s;
	}

	.input-row__mute:hover {
		background: rgba(255,255,255,0.08);
		color: #94a3b8;
	}

	.input-row__mute--off {
		color: #ef4444;
		border-color: rgba(239,68,68,0.3);
		background: rgba(239,68,68,0.08);
	}

	.input-row__field {
		flex: 1 1 auto;
		height: 2.5rem;
		padding: 0 0.875rem;
		border-radius: 0.75rem;
		border: 1px solid rgba(255,255,255,0.08);
		background: rgba(255,255,255,0.04);
		color: #e2e8f0;
		font-size: 0.9rem;
		outline: none;
		transition: border-color 0.15s, background 0.15s;
		font-family: inherit;
	}

	.input-row__field::placeholder { color: #334155; }

	.input-row__field:focus {
		border-color: rgba(37,99,235,0.4);
		background: rgba(37,99,235,0.06);
	}

	.input-row__field:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.input-row__send {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 0.75rem;
		border: none;
		background: #2563eb;
		color: #fff;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.15s, transform 0.1s, opacity 0.15s;
	}

	.input-row__send:not(:disabled):hover { background: #1d4ed8; }
	.input-row__send:not(:disabled):active { transform: scale(0.93); }

	.input-row__send:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
</style>
