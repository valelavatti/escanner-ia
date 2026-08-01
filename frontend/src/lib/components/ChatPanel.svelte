<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';

	// ── Types ────────────────────────────────────────────────────────────────────

	type OutcomeKind = 'correct' | 'incorrect';

	interface Message {
		id: number;
		role: 'user' | 'assistant' | 'outcome';
		content: string;
		outcome?: OutcomeKind;
		timestamp: Date;
	}

	interface Props {
		onClose: () => void;
		context?: {
			sku?: string;
			descripcion?: string;
			ubicacion?: string;
			deposito?: string;
		};
	}

	let { onClose, context = {} }: Props = $props();

	// ── Config ───────────────────────────────────────────────────────────────────

	const GEMINI_API_KEY = import.meta.env.VITE_GEMINI_API_KEY ?? '';
	const MODEL = 'gemini-2.0-flash';
	const MAX_HISTORY_TURNS = 10;

	// ── State ────────────────────────────────────────────────────────────────────

	let msgId = 0;

	let messages = $state<Message[]>([
		{
			id: msgId++,
			role: 'assistant',
			content: context.sku
				? `Producto detectado: **${context.sku}**${context.descripcion ? ` — ${context.descripcion}` : ''}.\nUsá los botones para registrar el resultado del escaneo, o haceme una pregunta.`
				: 'Listo. Usá los botones para registrar el resultado del escaneo, o preguntame sobre un producto o ubicación.',
			timestamp: new Date()
		}
	]);

	type AiStatus = 'idle' | 'thinking' | 'speaking';

	let status = $state<AiStatus>('idle');
	let input = $state('');
	let muted = $state(false);
	let messagesEl: HTMLElement | undefined = $state(undefined);

	// Speech synthesis
	let currentUtterance: SpeechSynthesisUtterance | null = null;

	// Waveform
	let waveHeights = $state<number[]>(Array.from({ length: 18 }, () => 4));
	let waveInterval: ReturnType<typeof setInterval> | null = null;

	// ── Derived context chips ────────────────────────────────────────────────────

	let contextChips = $derived(
		[
			context.sku ? { label: context.sku, color: 'blue' as const } : null,
			context.ubicacion ? { label: context.ubicacion, color: 'green' as const } : null
		].filter(Boolean) as { label: string; color: 'blue' | 'green' }[]
	);

	// ── Audio helpers ─────────────────────────────────────────────────────────────

	function startWave() {
		status = 'speaking';
		waveInterval = setInterval(() => {
			waveHeights = Array.from({ length: 18 }, () => 4 + Math.random() * 22);
		}, 110);
	}

	function stopWave() {
		status = 'idle';
		if (waveInterval) {
			clearInterval(waveInterval);
			waveInterval = null;
		}
		waveHeights = Array.from({ length: 18 }, () => 4);
	}

	function speak(text: string) {
		if (muted || typeof window === 'undefined') return;

		window.speechSynthesis.cancel();
		const utterance = new SpeechSynthesisUtterance(text);
		utterance.lang = 'es-AR';
		utterance.rate = 1.05;
		utterance.pitch = 1;

		// Pick a Spanish voice if available
		const voices = window.speechSynthesis.getVoices();
		const esVoice = voices.find(
			(v) => v.lang.startsWith('es') && !v.name.toLowerCase().includes('compact')
		);
		if (esVoice) utterance.voice = esVoice;

		utterance.onstart = startWave;
		utterance.onend = stopWave;
		utterance.onerror = stopWave;

		currentUtterance = utterance;
		window.speechSynthesis.speak(utterance);
	}

	function stopSpeaking() {
		if (typeof window !== 'undefined') window.speechSynthesis.cancel();
		stopWave();
	}

	// ── System prompt ─────────────────────────────────────────────────────────────

	function buildSystemPrompt(): string {
		const lines = [
			'Sos un asistente experto en operaciones de depósito y logística.',
			'Respondés en español rioplatense, de forma muy breve y directa.',
			'El operario está parado frente a una estantería con un scanner en la mano.',
			'Tu objetivo es ayudarlo a encontrar o almacenar el producto de la forma más rápida posible.',
			'Nunca inventés datos. Si no tenés información, decilo en una oración.',
			'Respondés en máximo 2 oraciones. Priorizá claridad sobre completitud.',
			'Si el operario reporta un error, dá pasos específicos y concretos.'
		];

		if (context.sku) lines.push(`Producto escaneado actualmente: SKU ${context.sku}.`);
		if (context.descripcion) lines.push(`Descripción: ${context.descripcion}.`);
		if (context.ubicacion) lines.push(`Ubicación anclada: ${context.ubicacion}.`);
		if (context.deposito) lines.push(`Depósito asignado: ${context.deposito}.`);

		return lines.join('\n');
	}

	// ── Gemini call ───────────────────────────────────────────────────────────────

	async function callGemini(userText: string): Promise<string> {
		const history = messages.slice(-MAX_HISTORY_TURNS * 2);

		const geminiHistory = history
			.filter((m) => m.role === 'user' || m.role === 'assistant')
			.map((m) => ({
				role: m.role === 'user' ? 'user' : 'model',
				parts: [{ text: m.content }]
			}));

		const payload = {
			system_instruction: { parts: [{ text: buildSystemPrompt() }] },
			contents: [
				...geminiHistory,
				{ role: 'user', parts: [{ text: userText }] }
			],
			generationConfig: {
				temperature: 0.3,
				maxOutputTokens: 120
			}
		};

		const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}`;

		const res = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});

		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			throw new Error(err?.error?.message ?? `HTTP ${res.status}`);
		}

		const data = await res.json();
		return data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? '(Sin respuesta)';
	}

	// ── Send message ──────────────────────────────────────────────────────────────

	async function sendMessage(text: string) {
		const trimmed = text.trim();
		if (!trimmed || status === 'thinking') return;

		messages = [
			...messages,
			{ id: msgId++, role: 'user', content: trimmed, timestamp: new Date() }
		];
		input = '';
		status = 'thinking';

		scrollToBottom();

		try {
			const reply = await callGemini(trimmed);
			messages = [
				...messages,
				{ id: msgId++, role: 'assistant', content: reply, timestamp: new Date() }
			];
			speak(reply);
		} catch (err) {
			const msg = err instanceof Error ? err.message : 'Error al consultar la IA.';
			messages = [
				...messages,
				{ id: msgId++, role: 'assistant', content: `Error: ${msg}`, timestamp: new Date() }
			];
			status = 'idle';
		}

		scrollToBottom();
	}

	// ── Outcome buttons ───────────────────────────────────────────────────────────

	async function handleOutcome(kind: OutcomeKind) {
		const label =
			kind === 'correct'
				? 'Escaneo correcto'
				: 'Escaneo incorrecto';

		messages = [
			...messages,
			{ id: msgId++, role: 'outcome', content: label, outcome: kind, timestamp: new Date() }
		];

		const prompt =
			kind === 'correct'
				? `El operario confirmó que el escaneo fue correcto.${context.sku ? ` Producto: ${context.sku}.` : ''} Dá una confirmación breve y motivadora.`
				: `El operario reportó un escaneo incorrecto.${context.sku ? ` Producto esperado: ${context.sku}.` : ''} Guialo en 1-2 pasos concretos para corregirlo.`;

		status = 'thinking';
		scrollToBottom();

		try {
			const reply = await callGemini(prompt);
			messages = [
				...messages,
				{ id: msgId++, role: 'assistant', content: reply, timestamp: new Date() }
			];
			speak(reply);
		} catch {
			status = 'idle';
		}

		scrollToBottom();
	}

	// ── Scroll ────────────────────────────────────────────────────────────────────

	function scrollToBottom() {
		if (messagesEl) {
			setTimeout(() => {
				if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
			}, 60);
		}
	}

	// ── Keyboard ──────────────────────────────────────────────────────────────────

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && !(e as any).isComposing) {
			sendMessage(input);
		}
	}
</script>

<aside
	class="chat-panel"
	role="complementary"
	aria-label="Asistente IA de depósito"
	transition:fly={{ y: '100%', duration: 380, easing: cubicOut }}
>
	<!-- ── Header ─────────────────────────────────────────────────────────────── -->
	<header class="chat-panel__header">
		<div class="chat-panel__header-left">
			<div class="chat-panel__orb" class:chat-panel__orb--thinking={status === 'thinking'} class:chat-panel__orb--speaking={status === 'speaking'}>
				{#if status === 'thinking'}
					<span class="chat-panel__dots" aria-hidden="true">
						<span></span><span></span><span></span>
					</span>
				{:else if status === 'speaking'}
					<div class="chat-panel__waveform" aria-hidden="true">
						{#each waveHeights as h}
							<span class="chat-panel__bar" style="height:{h}px"></span>
						{/each}
					</div>
				{:else}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
						<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
						<line x1="12" y1="19" x2="12" y2="22"/>
					</svg>
				{/if}
			</div>

			<div class="chat-panel__header-info">
				<span class="chat-panel__title">InvenTIA</span>
				<span class="chat-panel__status-label">
					{#if status === 'thinking'}
						Pensando...
					{:else if status === 'speaking'}
						Hablando
					{:else}
						Listo
					{/if}
				</span>
			</div>
		</div>

		<div class="chat-panel__header-right">
			<button
				type="button"
				class="chat-panel__icon-btn"
				onclick={() => { muted = !muted; if (muted) stopSpeaking(); }}
				title={muted ? 'Activar voz' : 'Silenciar'}
				aria-label={muted ? 'Activar voz' : 'Silenciar'}
			>
				{#if muted}
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
				{:else}
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
				{/if}
			</button>

			<button
				type="button"
				class="chat-panel__icon-btn chat-panel__icon-btn--close"
				onclick={onClose}
				aria-label="Cerrar asistente"
			>
				<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
			</button>
		</div>
	</header>

	<!-- ── Context chips ──────────────────────────────────────────────────────── -->
	{#if contextChips.length > 0}
		<div class="chat-panel__chips" role="list" aria-label="Contexto activo">
			{#each contextChips as chip}
				<span class="chat-panel__chip chat-panel__chip--{chip.color}" role="listitem">
					{chip.label}
				</span>
			{/each}
		</div>
	{/if}

	<!-- ── Outcome buttons ────────────────────────────────────────────────────── -->
	<div class="chat-panel__outcomes" role="group" aria-label="Resultado del escaneo">
		<button
			type="button"
			class="chat-panel__outcome-btn chat-panel__outcome-btn--incorrect"
			onclick={() => handleOutcome('incorrect')}
			disabled={status === 'thinking'}
			aria-label="Registrar escaneo incorrecto"
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
			<span>Incorrecto</span>
		</button>

		<button
			type="button"
			class="chat-panel__outcome-btn chat-panel__outcome-btn--correct"
			onclick={() => handleOutcome('correct')}
			disabled={status === 'thinking'}
			aria-label="Registrar escaneo correcto"
		>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
			<span>Correcto</span>
		</button>
	</div>

	<!-- ── Messages ──────────────────────────────────────────────────────────── -->
	<div class="chat-panel__messages" bind:this={messagesEl} role="log" aria-live="polite" aria-label="Conversación con el asistente">
		{#each messages as msg (msg.id)}
			{#if msg.role === 'outcome'}
				<div
					class="chat-panel__outcome-pill chat-panel__outcome-pill--{msg.outcome}"
					transition:fade={{ duration: 180 }}
					role="status"
				>
					{msg.outcome === 'correct'
						? '✓ Escaneo correcto registrado'
						: '✗ Escaneo incorrecto registrado'}
				</div>
			{:else}
				<div
					class="chat-panel__bubble chat-panel__bubble--{msg.role}"
					transition:fly={{ y: 10, duration: 220, easing: cubicOut }}
				>
					<p class="chat-panel__bubble-text">{msg.content}</p>
					<time
						class="chat-panel__bubble-time"
						datetime={msg.timestamp.toISOString()}
					>
						{msg.timestamp.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
					</time>
				</div>
			{/if}
		{/each}

		{#if status === 'thinking'}
			<div class="chat-panel__typing" transition:fade={{ duration: 150 }} aria-label="El asistente está escribiendo">
				<span></span><span></span><span></span>
			</div>
		{/if}
	</div>

	<!-- ── Input ──────────────────────────────────────────────────────────────── -->
	<div class="chat-panel__input-row">
		<input
			type="text"
			class="chat-panel__input"
			bind:value={input}
			onkeydown={handleKeydown}
			placeholder="Preguntá algo..."
			autocomplete="off"
			spellcheck={false}
			disabled={status === 'thinking'}
			aria-label="Mensaje para el asistente"
		/>
		<button
			type="button"
			class="chat-panel__send-btn"
			onclick={() => sendMessage(input)}
			disabled={!input.trim() || status === 'thinking'}
			aria-label="Enviar mensaje"
		>
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
		</button>
	</div>
</aside>

<style>
	/* ── Panel shell ────────────────────────────────────────────────────────── */
	.chat-panel {
		position: fixed;
		inset-inline: 0;
		bottom: 0;
		height: 76dvh;
		display: flex;
		flex-direction: column;
		background: #090e1a;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 1.25rem 1.25rem 0 0;
		box-shadow: 0 -24px 64px rgba(0, 0, 0, 0.65);
		z-index: 100;
		overflow: hidden;
		/* safe area for notch phones */
		padding-bottom: env(safe-area-inset-bottom, 0px);
	}

	/* ── Header ─────────────────────────────────────────────────────────────── */
	.chat-panel__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.125rem 0.75rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
		flex-shrink: 0;
	}

	.chat-panel__header-left {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.chat-panel__header-right {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	/* ── Orb ────────────────────────────────────────────────────────────────── */
	.chat-panel__orb {
		width: 2.625rem;
		height: 2.625rem;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		background: radial-gradient(circle at 35% 35%, #1d4ed8, #1e3a8a);
		box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.3), 0 0 20px rgba(37, 99, 235, 0.25);
		color: #93c5fd;
		flex-shrink: 0;
		transition: background 0.4s, box-shadow 0.4s;
	}

	.chat-panel__orb--thinking {
		background: radial-gradient(circle at 35% 35%, #7c3aed, #4c1d95);
		box-shadow: 0 0 0 1px rgba(139, 92, 246, 0.4), 0 0 24px rgba(124, 58, 237, 0.35);
		color: #c4b5fd;
		animation: orb-pulse 1.4s ease-in-out infinite;
	}

	.chat-panel__orb--speaking {
		background: radial-gradient(circle at 35% 35%, #0891b2, #0e7490);
		box-shadow: 0 0 0 1px rgba(6, 182, 212, 0.4), 0 0 28px rgba(8, 145, 178, 0.4);
		color: #67e8f9;
	}

	@keyframes orb-pulse {
		0%, 100% { transform: scale(1); opacity: 1; }
		50% { transform: scale(1.06); opacity: 0.85; }
	}

	.chat-panel__dots {
		display: flex;
		align-items: center;
		gap: 3px;
	}

	.chat-panel__dots span {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		background: currentColor;
		animation: bounce-dot 1.1s ease-in-out infinite;
	}

	.chat-panel__dots span:nth-child(2) { animation-delay: 0.16s; }
	.chat-panel__dots span:nth-child(3) { animation-delay: 0.32s; }

	@keyframes bounce-dot {
		0%, 80%, 100% { transform: translateY(0); }
		40% { transform: translateY(-5px); }
	}

	.chat-panel__waveform {
		display: flex;
		align-items: center;
		gap: 2px;
		height: 20px;
	}

	.chat-panel__bar {
		display: block;
		width: 2px;
		min-height: 4px;
		border-radius: 2px;
		background: currentColor;
		transition: height 0.1s ease;
	}

	/* ── Header text ─────────────────────────────────────────────────────────── */
	.chat-panel__header-info {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.chat-panel__title {
		font-size: 0.9375rem;
		font-weight: 700;
		color: #f1f5f9;
		letter-spacing: 0.01em;
	}

	.chat-panel__status-label {
		font-size: 0.75rem;
		color: #64748b;
		letter-spacing: 0.02em;
	}

	/* ── Icon buttons ────────────────────────────────────────────────────────── */
	.chat-panel__icon-btn {
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.05);
		color: #94a3b8;
		cursor: pointer;
		transition: background 0.18s, color 0.18s;
	}

	.chat-panel__icon-btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: #e2e8f0;
	}

	.chat-panel__icon-btn--close:hover {
		background: rgba(220, 38, 38, 0.15);
		color: #f87171;
	}

	/* ── Context chips ───────────────────────────────────────────────────────── */
	.chat-panel__chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		padding: 0.5rem 1.125rem;
		flex-shrink: 0;
	}

	.chat-panel__chip {
		display: inline-flex;
		align-items: center;
		padding: 0.25rem 0.625rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.02em;
	}

	.chat-panel__chip--blue {
		background: rgba(37, 99, 235, 0.18);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.25);
	}

	.chat-panel__chip--green {
		background: rgba(22, 163, 74, 0.15);
		color: #86efac;
		border: 1px solid rgba(34, 197, 94, 0.22);
	}

	/* ── Outcome buttons ─────────────────────────────────────────────────────── */
	.chat-panel__outcomes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.625rem;
		padding: 0 1.125rem 0.75rem;
		flex-shrink: 0;
	}

	.chat-panel__outcome-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.875rem 1rem;
		border: none;
		border-radius: 0.75rem;
		font-size: 1rem;
		font-weight: 700;
		cursor: pointer;
		transition: transform 0.12s, box-shadow 0.18s, opacity 0.15s;
		touch-action: manipulation;
		letter-spacing: 0.01em;
	}

	.chat-panel__outcome-btn:active {
		transform: scale(0.96);
	}

	.chat-panel__outcome-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.chat-panel__outcome-btn--incorrect {
		background: rgba(220, 38, 38, 0.12);
		color: #fca5a5;
		border: 1.5px solid rgba(220, 38, 38, 0.35);
		box-shadow: 0 0 18px rgba(220, 38, 38, 0.08);
	}

	.chat-panel__outcome-btn--incorrect:hover:not(:disabled) {
		background: rgba(220, 38, 38, 0.2);
		box-shadow: 0 0 24px rgba(220, 38, 38, 0.2);
	}

	.chat-panel__outcome-btn--correct {
		background: rgba(22, 163, 74, 0.12);
		color: #86efac;
		border: 1.5px solid rgba(22, 163, 74, 0.35);
		box-shadow: 0 0 18px rgba(22, 163, 74, 0.08);
	}

	.chat-panel__outcome-btn--correct:hover:not(:disabled) {
		background: rgba(22, 163, 74, 0.2);
		box-shadow: 0 0 24px rgba(22, 163, 74, 0.2);
	}

	/* ── Messages ────────────────────────────────────────────────────────────── */
	.chat-panel__messages {
		flex: 1 1 0;
		overflow-y: auto;
		padding: 0.5rem 1.125rem;
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
		scroll-behavior: smooth;
	}

	.chat-panel__messages::-webkit-scrollbar { width: 3px; }
	.chat-panel__messages::-webkit-scrollbar-track { background: transparent; }
	.chat-panel__messages::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }

	/* ── Bubble ──────────────────────────────────────────────────────────────── */
	.chat-panel__bubble {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		max-width: 84%;
	}

	.chat-panel__bubble--user {
		align-self: flex-end;
		align-items: flex-end;
	}

	.chat-panel__bubble--assistant {
		align-self: flex-start;
		align-items: flex-start;
	}

	.chat-panel__bubble-text {
		margin: 0;
		padding: 0.625rem 0.875rem;
		border-radius: 1rem;
		font-size: 0.9375rem;
		line-height: 1.5;
		white-space: pre-wrap;
	}

	.chat-panel__bubble--user .chat-panel__bubble-text {
		background: rgba(37, 99, 235, 0.22);
		color: #bfdbfe;
		border: 1px solid rgba(59, 130, 246, 0.2);
		border-bottom-right-radius: 0.25rem;
	}

	.chat-panel__bubble--assistant .chat-panel__bubble-text {
		background: rgba(255, 255, 255, 0.05);
		color: #e2e8f0;
		border: 1px solid rgba(255, 255, 255, 0.07);
		border-bottom-left-radius: 0.25rem;
	}

	.chat-panel__bubble-time {
		font-size: 0.6875rem;
		color: #475569;
		padding: 0 0.25rem;
	}

	/* ── Outcome pills ───────────────────────────────────────────────────────── */
	.chat-panel__outcome-pill {
		align-self: center;
		padding: 0.3125rem 0.875rem;
		border-radius: 999px;
		font-size: 0.8125rem;
		font-weight: 600;
		letter-spacing: 0.02em;
	}

	.chat-panel__outcome-pill--correct {
		background: rgba(22, 163, 74, 0.15);
		color: #86efac;
		border: 1px solid rgba(22, 163, 74, 0.3);
	}

	.chat-panel__outcome-pill--incorrect {
		background: rgba(220, 38, 38, 0.12);
		color: #fca5a5;
		border: 1px solid rgba(220, 38, 38, 0.28);
	}

	/* ── Typing indicator ────────────────────────────────────────────────────── */
	.chat-panel__typing {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 0.625rem 0.875rem;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.07);
		border-radius: 1rem;
		border-bottom-left-radius: 0.25rem;
		width: fit-content;
		align-self: flex-start;
	}

	.chat-panel__typing span {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #475569;
		animation: bounce-dot 1.1s ease-in-out infinite;
	}

	.chat-panel__typing span:nth-child(2) { animation-delay: 0.16s; }
	.chat-panel__typing span:nth-child(3) { animation-delay: 0.32s; }

	/* ── Input row ───────────────────────────────────────────────────────────── */
	.chat-panel__input-row {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.75rem 1.125rem;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		flex-shrink: 0;
		background: #090e1a;
	}

	.chat-panel__input {
		flex: 1 1 0;
		padding: 0.625rem 0.875rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 0.625rem;
		font-size: 0.9375rem;
		color: #e2e8f0;
		outline: none;
		transition: border-color 0.18s;
	}

	.chat-panel__input::placeholder { color: #475569; }

	.chat-panel__input:focus {
		border-color: rgba(59, 130, 246, 0.5);
	}

	.chat-panel__input:disabled {
		opacity: 0.5;
	}

	.chat-panel__send-btn {
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #2563eb;
		color: #ffffff;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.18s, transform 0.12s;
	}

	.chat-panel__send-btn:hover:not(:disabled) { background: #1d4ed8; }
	.chat-panel__send-btn:active:not(:disabled) { transform: scale(0.92); }
	.chat-panel__send-btn:disabled { background: #1e293b; color: #475569; cursor: not-allowed; }
</style>
