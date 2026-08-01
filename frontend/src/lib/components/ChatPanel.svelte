<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';

	interface Message {
		id: number;
		role: 'user' | 'assistant';
		content: string;
		outcome?: 'correct' | 'incorrect';
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

	const GEMINI_API_KEY = import.meta.env.VITE_GEMINI_API_KEY ?? '';
	const MODEL = 'gemini-2.0-flash';
	const MAX_HISTORY_TURNS = 10;

	let msgId = 0;

	let messages = $state<Message[]>([
		{
			id: msgId++,
			role: 'assistant',
			content: context.sku
				? `Producto detectado: ${context.sku}${context.descripcion ? ` — ${context.descripcion}` : ''}. ¿En qué te ayudo?`
				: 'Listo. Podés preguntarme dónde encontrar un producto, confirmar una ubicación, o usá los botones para registrar el resultado del escaneo.',
			timestamp: new Date()
		}
	]);

	let input = $state('');
	let loading = $state(false);
	let muted = $state(false);
	let isSpeaking = $state(false);
	let messagesEl: HTMLElement | undefined = $state(undefined);

	// Waveform bars heights (animated when speaking)
	let waveHeights = $state([3, 5, 8, 5, 3, 7, 12, 7, 3, 5, 8, 5, 3]);

	let waveInterval: ReturnType<typeof setInterval> | null = null;

	function startWave() {
		isSpeaking = true;
		waveInterval = setInterval(() => {
			waveHeights = waveHeights.map(() => 3 + Math.random() * 20);
		}, 120);
	}

	function stopWave() {
		isSpeaking = false;
		if (waveInterval) {
			clearInterval(waveInterval);
			waveInterval = null;
		}
		waveHeights = [3, 5, 8, 5, 3, 7, 12, 7, 3, 5, 8, 5, 3];
	}

	function buildSystemPrompt(): string {
		const lines = [
			'Sos un asistente experto en operaciones de depósito y logística.',
			'Respondés en español rioplatense, de forma muy breve y directa.',
			'El operario está parado frente a una estantería con un scanner en la mano.',
			'Tu objetivo es ayudarlo a encontrar o almacenar el producto de la forma más rápida posible.',
			'Nunca inventés datos. Si no tenés información, decilo en una oración.',
			'Respondés en máximo 2 oraciones. Priorizá claridad sobre completitud.',
			'Si el operario reporta un error, dá pasos específicos y numerados.'
		];
		if (context.sku)
			lines.push(
				`Producto activo: SKU ${context.sku}${context.descripcion ? ` — ${context.descripcion}` : ''}.`
			);
		if (context.ubicacion) lines.push(`Ubicación anclada: ${context.ubicacion}.`);
		if (context.deposito) lines.push(`Depósito activo: ${context.deposito}.`);
		return lines.join('\n');
	}

	function speak(text: string) {
		if (muted || !('speechSynthesis' in window)) return;
		window.speechSynthesis.cancel();
		const utterance = new SpeechSynthesisUtterance(text);
		utterance.lang = 'es-AR';
		utterance.rate = 1.05;
		utterance.onstart = () => startWave();
		utterance.onend = () => stopWave();
		utterance.onerror = () => stopWave();
		window.speechSynthesis.speak(utterance);
	}

	async function sendToGemini(userMessage: string): Promise<string> {
		const systemPrompt = buildSystemPrompt();
		const historyMessages = messages
			.filter((m) => !m.outcome)
			.slice(-MAX_HISTORY_TURNS * 2);

		const geminiContents = historyMessages.map((m) => ({
			role: m.role === 'assistant' ? 'model' : 'user',
			parts: [{ text: m.content }]
		}));
		geminiContents.push({ role: 'user', parts: [{ text: userMessage }] });

		const body = {
			system_instruction: { parts: [{ text: systemPrompt }] },
			contents: geminiContents,
			generationConfig: { temperature: 0.35, maxOutputTokens: 200 }
		};

		const res = await fetch(
			`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}`,
			{
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			}
		);

		if (!res.ok) {
			const err = await res.text();
			throw new Error(`Gemini error ${res.status}: ${err}`);
		}
		const data = await res.json();
		return data.candidates?.[0]?.content?.parts?.[0]?.text ?? 'Sin respuesta del modelo.';
	}

	function pushMessage(msg: Omit<Message, 'id' | 'timestamp'>) {
		messages = [...messages, { ...msg, id: msgId++, timestamp: new Date() }];
		scrollToBottom();
	}

	async function handleSend(text: string) {
		if (!text.trim() || loading) return;
		pushMessage({ role: 'user', content: text });
		input = '';
		loading = true;
		try {
			const reply = await sendToGemini(text);
			pushMessage({ role: 'assistant', content: reply });
			speak(reply);
		} catch {
			pushMessage({
				role: 'assistant',
				content: 'No se pudo conectar con el asistente. Verificá la clave de API.'
			});
		} finally {
			loading = false;
		}
	}

	async function handleOutcome(outcome: 'correct' | 'incorrect') {
		if (loading) return;
		const label =
			outcome === 'correct'
				? 'Escaneo registrado como correcto.'
				: 'Escaneo registrado como incorrecto.';
		const prompt =
			outcome === 'correct'
				? 'El operario confirmó que el escaneo fue correcto. Dá una confirmación muy breve y positiva.'
				: 'El operario reportó que el escaneo fue incorrecto. Dá los pasos específicos para corregirlo.';

		pushMessage({ role: 'user', content: label, outcome });
		loading = true;
		try {
			const reply = await sendToGemini(prompt);
			pushMessage({ role: 'assistant', content: reply });
			speak(reply);
		} catch {
			pushMessage({ role: 'assistant', content: 'Error al conectar con el asistente.' });
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && e.keyCode !== 229) {
			e.preventDefault();
			handleSend(input);
		}
	}

	function scrollToBottom() {
		requestAnimationFrame(() => {
			if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
		});
	}

	function toggleMute() {
		muted = !muted;
		if (muted) {
			window.speechSynthesis?.cancel();
			stopWave();
		}
	}

	function formatTime(d: Date): string {
		return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
	}
</script>

<div
	class="cp"
	role="dialog"
	aria-modal="true"
	aria-label="Asistente IA de depósito"
	transition:fly={{ y: '100%', duration: 320, easing: cubicOut }}
>
	<!-- Drag handle -->
	<div class="cp__handle" aria-hidden="true"></div>

	<!-- Header -->
	<header class="cp__header">
		<div class="cp__header-brand">
			<!-- AI orb with pulse when loading/speaking -->
			<div class="cp__orb" class:cp__orb--active={loading || isSpeaking} aria-hidden="true">
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
					<path
						d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"
						fill="currentColor"
						opacity="0.3"
					/>
					<circle cx="12" cy="12" r="4" fill="currentColor" />
				</svg>
			</div>
			<div>
				<div class="cp__title">Asistente IA</div>
				<div class="cp__subtitle">
					{#if loading}
						<span class="cp__status-dot cp__status-dot--loading"></span>
						Procesando...
					{:else if isSpeaking}
						<span class="cp__status-dot cp__status-dot--speaking"></span>
						Hablando...
					{:else}
						<span class="cp__status-dot cp__status-dot--ready"></span>
						Listo
					{/if}
				</div>
			</div>
		</div>

		<div class="cp__header-actions">
			<!-- Waveform (visible while speaking) -->
			{#if isSpeaking}
				<div class="cp__waveform" aria-hidden="true" transition:fade={{ duration: 200 }}>
					{#each waveHeights as h}
						<span class="cp__wave-bar" style="height: {h}px;"></span>
					{/each}
				</div>
			{/if}

			<button
				type="button"
				class="cp__icon-btn"
				class:cp__icon-btn--muted={muted}
				onclick={toggleMute}
				aria-label={muted ? 'Activar voz' : 'Silenciar voz'}
			>
				{#if muted}
					<!-- mic-off -->
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<line x1="1" y1="1" x2="23" y2="23" />
						<path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
						<path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23" />
						<line x1="12" y1="19" x2="12" y2="23" />
						<line x1="8" y1="23" x2="16" y2="23" />
					</svg>
				{:else}
					<!-- mic -->
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
						<path d="M19 10v2a7 7 0 0 1-14 0v-2" />
						<line x1="12" y1="19" x2="12" y2="23" />
						<line x1="8" y1="23" x2="16" y2="23" />
					</svg>
				{/if}
			</button>

			<button type="button" class="cp__icon-btn" onclick={onClose} aria-label="Cerrar asistente">
				<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>
	</header>

	<!-- Context chip strip -->
	{#if context.sku || context.ubicacion}
		<div class="cp__chips">
			{#if context.sku}
				<span class="cp__chip cp__chip--sku">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<path d="M3 5h18v14H3V5zm2 2v10h14V7H5zm2 2h10v2H7V9zm0 4h6v2H7v-2z" />
					</svg>
					{context.sku}
				</span>
			{/if}
			{#if context.ubicacion}
				<span class="cp__chip cp__chip--location">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
					</svg>
					{context.ubicacion}
				</span>
			{/if}
		</div>
	{/if}

	<!-- Outcome buttons — large, thumb-friendly -->
	<div class="cp__outcomes">
		<button
			type="button"
			class="cp__outcome cp__outcome--correct"
			onclick={() => handleOutcome('correct')}
			disabled={loading}
			aria-label="Registrar escaneo correcto"
		>
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<polyline points="20 6 9 17 4 12" />
			</svg>
			<span>Correcto</span>
		</button>
		<button
			type="button"
			class="cp__outcome cp__outcome--incorrect"
			onclick={() => handleOutcome('incorrect')}
			disabled={loading}
			aria-label="Registrar escaneo incorrecto"
		>
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="18" y1="6" x2="6" y2="18" />
				<line x1="6" y1="6" x2="18" y2="18" />
			</svg>
			<span>Incorrecto</span>
		</button>
	</div>

	<!-- Messages -->
	<div class="cp__messages" bind:this={messagesEl} aria-live="polite" aria-label="Conversación">
		{#each messages as msg (msg.id)}
			<div
				class="cp__msg"
				class:cp__msg--user={msg.role === 'user'}
				class:cp__msg--ai={msg.role === 'assistant'}
				class:cp__msg--outcome-correct={msg.outcome === 'correct'}
				class:cp__msg--outcome-incorrect={msg.outcome === 'incorrect'}
				transition:fly={{ y: 10, duration: 220, easing: cubicOut }}
			>
				{#if msg.role === 'assistant'}
					<div class="cp__msg-avatar" aria-hidden="true">IA</div>
				{/if}
				<div class="cp__msg-body">
					<p class="cp__msg-text">{msg.content}</p>
					<time class="cp__msg-time" datetime={msg.timestamp.toISOString()}>
						{formatTime(msg.timestamp)}
					</time>
				</div>
			</div>
		{/each}

		{#if loading}
			<div
				class="cp__msg cp__msg--ai"
				aria-label="El asistente está procesando"
				transition:fade={{ duration: 150 }}
			>
				<div class="cp__msg-avatar" aria-hidden="true">IA</div>
				<div class="cp__msg-body">
					<div class="cp__dots">
						<span></span><span></span><span></span>
					</div>
				</div>
			</div>
		{/if}
	</div>

	<!-- Input row -->
	<div class="cp__input-row">
		<input
			type="text"
			class="cp__input"
			placeholder="Escribí una pregunta..."
			bind:value={input}
			onkeydown={handleKeydown}
			disabled={loading}
			aria-label="Mensaje al asistente"
			autocomplete="off"
			autocorrect="off"
			spellcheck="false"
		/>
		<button
			type="button"
			class="cp__send"
			onclick={() => handleSend(input)}
			disabled={loading || !input.trim()}
			aria-label="Enviar"
		>
			<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="22" y1="2" x2="11" y2="13" />
				<polygon points="22 2 15 22 11 13 2 9 22 2" />
			</svg>
		</button>
	</div>
</div>

<style>
	/* ─── Shell ───────────────────────────────────────────────── */
	.cp {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		height: 76dvh;
		display: flex;
		flex-direction: column;
		background: #090e1a;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
		border-radius: 1.25rem 1.25rem 0 0;
		z-index: 100;
		overflow: hidden;
		box-shadow: 0 -24px 64px rgba(0, 0, 0, 0.6);
	}

	/* ─── Drag handle ─────────────────────────────────────────── */
	.cp__handle {
		width: 2.5rem;
		height: 0.25rem;
		background: rgba(255, 255, 255, 0.15);
		border-radius: 99px;
		margin: 0.625rem auto 0;
		flex-shrink: 0;
	}

	/* ─── Header ──────────────────────────────────────────────── */
	.cp__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.875rem 1.125rem 0.75rem;
		flex-shrink: 0;
	}

	.cp__header-brand {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	/* AI orb */
	.cp__orb {
		width: 2.375rem;
		height: 2.375rem;
		border-radius: 50%;
		background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 60%, #3b82f6 100%);
		display: flex;
		align-items: center;
		justify-content: center;
		color: #fff;
		flex-shrink: 0;
		transition: box-shadow 0.3s ease;
	}

	.cp__orb--active {
		box-shadow:
			0 0 0 3px rgba(59, 130, 246, 0.25),
			0 0 16px rgba(59, 130, 246, 0.4);
		animation: orb-pulse 1.8s ease-in-out infinite;
	}

	@keyframes orb-pulse {
		0%, 100% { box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2), 0 0 12px rgba(59, 130, 246, 0.3); }
		50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.1), 0 0 28px rgba(59, 130, 246, 0.5); }
	}

	.cp__title {
		font-size: 0.9375rem;
		font-weight: 700;
		color: #f8fafc;
		letter-spacing: -0.01em;
	}

	.cp__subtitle {
		display: flex;
		align-items: center;
		gap: 0.3125rem;
		font-size: 0.75rem;
		color: #64748b;
		margin-top: 0.125rem;
	}

	/* Status dot */
	.cp__status-dot {
		display: inline-block;
		width: 0.4375rem;
		height: 0.4375rem;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.cp__status-dot--ready { background: #22c55e; }
	.cp__status-dot--loading {
		background: #f59e0b;
		animation: dot-blink 0.9s ease-in-out infinite;
	}
	.cp__status-dot--speaking {
		background: #3b82f6;
		animation: dot-blink 0.6s ease-in-out infinite;
	}

	@keyframes dot-blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.3; }
	}

	/* Header actions */
	.cp__header-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	/* Waveform */
	.cp__waveform {
		display: flex;
		align-items: center;
		gap: 2px;
		height: 20px;
		margin-right: 0.375rem;
	}

	.cp__wave-bar {
		display: block;
		width: 2px;
		background: #3b82f6;
		border-radius: 2px;
		transition: height 0.1s ease;
		min-height: 3px;
	}

	.cp__icon-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border: none;
		border-radius: 0.5rem;
		background: transparent;
		color: #475569;
		cursor: pointer;
		touch-action: manipulation;
		transition: background 0.15s, color 0.15s;
	}

	.cp__icon-btn:hover {
		background: rgba(255, 255, 255, 0.06);
		color: #cbd5e1;
	}

	.cp__icon-btn--muted {
		color: #ef4444;
	}

	/* ─── Context chips ───────────────────────────────────────── */
	.cp__chips {
		display: flex;
		gap: 0.375rem;
		padding: 0 1.125rem 0.625rem;
		flex-shrink: 0;
		flex-wrap: wrap;
	}

	.cp__chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3125rem;
		padding: 0.25rem 0.625rem;
		border-radius: 99px;
		font-size: 0.71875rem;
		font-weight: 600;
		letter-spacing: 0.01em;
	}

	.cp__chip--sku {
		background: rgba(37, 99, 235, 0.15);
		color: #93c5fd;
		border: 1px solid rgba(37, 99, 235, 0.3);
	}

	.cp__chip--location {
		background: rgba(22, 163, 74, 0.12);
		color: #86efac;
		border: 1px solid rgba(22, 163, 74, 0.25);
	}

	/* ─── Outcome buttons ─────────────────────────────────────── */
	.cp__outcomes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
		padding: 0 1rem 0.75rem;
		flex-shrink: 0;
	}

	.cp__outcome {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		height: 3.25rem;
		border: none;
		border-radius: 0.875rem;
		font-size: 1rem;
		font-weight: 700;
		cursor: pointer;
		touch-action: manipulation;
		transition: opacity 0.15s, transform 0.1s, box-shadow 0.15s;
		letter-spacing: -0.01em;
	}

	.cp__outcome:disabled {
		opacity: 0.38;
		cursor: not-allowed;
	}

	.cp__outcome:not(:disabled):active {
		transform: scale(0.96);
	}

	.cp__outcome--correct {
		background: #16a34a;
		color: #fff;
		box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35);
	}

	.cp__outcome--correct:not(:disabled):hover {
		background: #15803d;
		box-shadow: 0 4px 18px rgba(22, 163, 74, 0.5);
	}

	.cp__outcome--incorrect {
		background: #dc2626;
		color: #fff;
		box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
	}

	.cp__outcome--incorrect:not(:disabled):hover {
		background: #b91c1c;
		box-shadow: 0 4px 18px rgba(220, 38, 38, 0.5);
	}

	/* ─── Divider ─────────────────────────────────────────────── */
	.cp__outcomes::after {
		content: '';
		display: none;
	}

	/* ─── Messages ────────────────────────────────────────────── */
	.cp__messages {
		flex: 1 1 auto;
		overflow-y: auto;
		padding: 0.5rem 1rem 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		border-top: 1px solid rgba(255, 255, 255, 0.05);
		scroll-behavior: smooth;
	}

	.cp__messages::-webkit-scrollbar {
		width: 0.1875rem;
	}

	.cp__messages::-webkit-scrollbar-track {
		background: transparent;
	}

	.cp__messages::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.1);
		border-radius: 99px;
	}

	/* Message row */
	.cp__msg {
		display: flex;
		align-items: flex-end;
		gap: 0.5rem;
		max-width: 100%;
	}

	.cp__msg--user {
		flex-direction: row-reverse;
	}

	/* AI avatar pill */
	.cp__msg-avatar {
		width: 1.625rem;
		height: 1.625rem;
		border-radius: 50%;
		background: linear-gradient(135deg, #1d4ed8, #2563eb);
		color: #fff;
		font-size: 0.5625rem;
		font-weight: 800;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		letter-spacing: 0.02em;
	}

	/* Bubble body */
	.cp__msg-body {
		display: flex;
		flex-direction: column;
		gap: 0.1875rem;
		max-width: 80%;
	}

	.cp__msg--user .cp__msg-body {
		align-items: flex-end;
	}

	.cp__msg-text {
		margin: 0;
		padding: 0.625rem 0.875rem;
		border-radius: 1rem;
		font-size: 0.9375rem;
		line-height: 1.5;
		word-break: break-word;
	}

	.cp__msg--ai .cp__msg-text {
		background: rgba(255, 255, 255, 0.06);
		color: #e2e8f0;
		border-bottom-left-radius: 0.25rem;
		border: 1px solid rgba(255, 255, 255, 0.07);
	}

	.cp__msg--user .cp__msg-text {
		background: #2563eb;
		color: #fff;
		border-bottom-right-radius: 0.25rem;
	}

	/* Outcome overrides */
	.cp__msg--outcome-correct .cp__msg-text {
		background: rgba(22, 163, 74, 0.2);
		color: #bbf7d0;
		border: 1px solid rgba(22, 163, 74, 0.3);
		font-weight: 600;
	}

	.cp__msg--outcome-incorrect .cp__msg-text {
		background: rgba(220, 38, 38, 0.2);
		color: #fecaca;
		border: 1px solid rgba(220, 38, 38, 0.3);
		font-weight: 600;
	}

	.cp__msg-time {
		font-size: 0.6875rem;
		color: #334155;
		padding: 0 0.1875rem;
	}

	/* Typing dots */
	.cp__dots {
		display: flex;
		align-items: center;
		gap: 0.3125rem;
		padding: 0.75rem 1rem;
		background: rgba(255, 255, 255, 0.06);
		border-radius: 1rem;
		border-bottom-left-radius: 0.25rem;
		border: 1px solid rgba(255, 255, 255, 0.07);
	}

	.cp__dots span {
		width: 0.4375rem;
		height: 0.4375rem;
		background: #475569;
		border-radius: 50%;
		animation: dots-bounce 1.3s ease-in-out infinite;
	}

	.cp__dots span:nth-child(2) { animation-delay: 0.15s; }
	.cp__dots span:nth-child(3) { animation-delay: 0.3s; }

	@keyframes dots-bounce {
		0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
		30% { transform: translateY(-5px); opacity: 1; }
	}

	/* ─── Input row ───────────────────────────────────────────── */
	.cp__input-row {
		display: flex;
		gap: 0.5rem;
		padding: 0.625rem 1rem;
		padding-bottom: max(0.625rem, env(safe-area-inset-bottom));
		border-top: 1px solid rgba(255, 255, 255, 0.05);
		background: #090e1a;
		flex-shrink: 0;
	}

	.cp__input {
		flex: 1 1 auto;
		height: 2.875rem;
		padding: 0 1rem;
		font-size: 0.9375rem;
		color: #f1f5f9;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.09);
		border-radius: 0.75rem;
		outline: none;
		transition: border-color 0.15s, background 0.15s;
		caret-color: #3b82f6;
	}

	.cp__input:focus {
		border-color: rgba(59, 130, 246, 0.5);
		background: rgba(255, 255, 255, 0.07);
	}

	.cp__input::placeholder {
		color: #334155;
	}

	.cp__input:disabled {
		opacity: 0.5;
	}

	.cp__send {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.875rem;
		height: 2.875rem;
		flex-shrink: 0;
		border: none;
		border-radius: 0.75rem;
		background: #2563eb;
		color: #fff;
		cursor: pointer;
		touch-action: manipulation;
		transition: background 0.15s, opacity 0.15s;
	}

	.cp__send:disabled {
		background: rgba(255, 255, 255, 0.06);
		color: #334155;
		cursor: not-allowed;
	}

	.cp__send:not(:disabled):hover {
		background: #1d4ed8;
	}

	.cp__send:not(:disabled):active {
		transform: scale(0.94);
	}
</style>
