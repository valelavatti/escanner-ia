<script lang="ts">
	import { fade, fly } from 'svelte/transition';

	interface Message {
		role: 'user' | 'assistant';
		content: string;
		isOutcome?: 'correct' | 'incorrect';
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

	let messages = $state<Message[]>([
		{
			role: 'assistant',
			content:
				'Hola, soy tu asistente de depósito. Podés preguntarme dónde guardar o encontrar un producto, o usá los botones para registrar si el escaneo fue correcto o incorrecto.'
		}
	]);

	let input = $state('');
	let loading = $state(false);
	let muted = $state(false);
	let chatListEl: HTMLUListElement | undefined = $state(undefined);

	function buildSystemPrompt(): string {
		const lines = [
			'Sos un asistente experto en operaciones de depósito y logística.',
			'Respondés en español, de forma breve y directa.',
			'El operario está usando un scanner para almacenar o recoger productos.',
			'Ayudás a encontrar productos, confirmar ubicaciones, y entender errores de escaneo.',
			'Nunca inventés datos. Si no tenés información, decilo con claridad.',
			'Respondés en máximo 3 oraciones cortas.'
		];

		if (context.sku) lines.push(`Producto escaneado actualmente: SKU ${context.sku}${context.descripcion ? ` — ${context.descripcion}` : ''}.`);
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
		window.speechSynthesis.speak(utterance);
	}

	async function sendToGemini(userMessage: string): Promise<string> {
		const systemPrompt = buildSystemPrompt();

		// Build the last N turns from history (skip the initial greeting, take real turns)
		const historyMessages = messages
			.filter((m) => !m.isOutcome)
			.slice(-MAX_HISTORY_TURNS * 2);

		const geminiContents = historyMessages.map((m) => ({
			role: m.role === 'assistant' ? 'model' : 'user',
			parts: [{ text: m.content }]
		}));

		geminiContents.push({ role: 'user', parts: [{ text: userMessage }] });

		const body = {
			system_instruction: { parts: [{ text: systemPrompt }] },
			contents: geminiContents,
			generationConfig: {
				temperature: 0.4,
				maxOutputTokens: 256
			}
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

	async function handleSend(text: string) {
		if (!text.trim() || loading) return;

		messages = [...messages, { role: 'user', content: text }];
		input = '';
		loading = true;

		scrollToBottom();

		try {
			const reply = await sendToGemini(text);
			messages = [...messages, { role: 'assistant', content: reply }];
			speak(reply);
		} catch (err) {
			const errorText = 'Error al conectar con el asistente. Verificá la clave de API.';
			messages = [...messages, { role: 'assistant', content: errorText }];
		} finally {
			loading = false;
			scrollToBottom();
		}
	}

	async function handleOutcome(outcome: 'correct' | 'incorrect') {
		const label = outcome === 'correct' ? 'ESCANEO CORRECTO' : 'ESCANEO INCORRECTO';
		const prompt =
			outcome === 'correct'
				? `El operario confirmó que el escaneo fue correcto. Dá una confirmación breve y alentadora.`
				: `El operario reportó que el escaneo fue incorrecto. Ayudá con los pasos para corregirlo.`;

		messages = [
			...messages,
			{
				role: 'user',
				content: label,
				isOutcome: outcome
			}
		];

		loading = true;
		scrollToBottom();

		try {
			const reply = await sendToGemini(prompt);
			messages = [...messages, { role: 'assistant', content: reply }];
			speak(reply);
		} catch {
			messages = [
				...messages,
				{ role: 'assistant', content: 'Error al conectar con el asistente.' }
			];
		} finally {
			loading = false;
			scrollToBottom();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && e.keyCode !== 229) {
			e.preventDefault();
			handleSend(input);
		}
	}

	function scrollToBottom() {
		// Use requestAnimationFrame to wait for DOM update
		requestAnimationFrame(() => {
			if (chatListEl) {
				chatListEl.scrollTop = chatListEl.scrollHeight;
			}
		});
	}

	function toggleMute() {
		muted = !muted;
		if (muted) window.speechSynthesis?.cancel();
	}
</script>

<div class="chat-panel" transition:fly={{ y: 300, duration: 280 }} role="dialog" aria-modal="true" aria-label="Asistente IA">
	<!-- Header -->
	<div class="chat-panel__header">
		<div class="chat-panel__header-left">
			<div class="chat-panel__avatar" aria-hidden="true">IA</div>
			<div>
				<div class="chat-panel__title">Asistente de Depósito</div>
				{#if context.ubicacion}
					<div class="chat-panel__subtitle">{context.ubicacion}</div>
				{/if}
			</div>
		</div>
		<div class="chat-panel__header-actions">
			<button
				type="button"
				class="chat-panel__icon-btn"
				onclick={toggleMute}
				aria-label={muted ? 'Activar voz' : 'Silenciar voz'}
				title={muted ? 'Activar voz' : 'Silenciar voz'}
			>
				{#if muted}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<line x1="1" y1="1" x2="23" y2="23"/>
						<path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
						<path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
						<line x1="12" y1="19" x2="12" y2="23"/>
						<line x1="8" y1="23" x2="16" y2="23"/>
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
						<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
						<line x1="12" y1="19" x2="12" y2="23"/>
						<line x1="8" y1="23" x2="16" y2="23"/>
					</svg>
				{/if}
			</button>
			<button
				type="button"
				class="chat-panel__icon-btn"
				onclick={onClose}
				aria-label="Cerrar asistente"
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<line x1="18" y1="6" x2="6" y2="18"/>
					<line x1="6" y1="6" x2="18" y2="18"/>
				</svg>
			</button>
		</div>
	</div>

	<!-- Outcome buttons -->
	<div class="chat-panel__outcomes">
		<button
			type="button"
			class="chat-panel__outcome-btn chat-panel__outcome-btn--correct"
			onclick={() => handleOutcome('correct')}
			disabled={loading}
			aria-label="Escaneo correcto"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<polyline points="20 6 9 17 4 12"/>
			</svg>
			Correcto
		</button>
		<button
			type="button"
			class="chat-panel__outcome-btn chat-panel__outcome-btn--incorrect"
			onclick={() => handleOutcome('incorrect')}
			disabled={loading}
			aria-label="Escaneo incorrecto"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="18" y1="6" x2="6" y2="18"/>
				<line x1="6" y1="6" x2="18" y2="18"/>
			</svg>
			Incorrecto
		</button>
	</div>

	<!-- Message list -->
	<ul class="chat-panel__messages" bind:this={chatListEl} aria-live="polite" aria-label="Conversación">
		{#each messages as msg (msg)}
			<li
				class="chat-panel__message"
				class:chat-panel__message--user={msg.role === 'user'}
				class:chat-panel__message--assistant={msg.role === 'assistant'}
				class:chat-panel__message--correct={msg.isOutcome === 'correct'}
				class:chat-panel__message--incorrect={msg.isOutcome === 'incorrect'}
				transition:fade={{ duration: 150 }}
			>
				{msg.content}
			</li>
		{/each}

		{#if loading}
			<li class="chat-panel__message chat-panel__message--assistant chat-panel__message--typing" aria-label="El asistente está escribiendo">
				<span class="typing-dot"></span>
				<span class="typing-dot"></span>
				<span class="typing-dot"></span>
			</li>
		{/if}
	</ul>

	<!-- Input -->
	<div class="chat-panel__input-row">
		<input
			type="text"
			class="chat-panel__input"
			placeholder="Preguntá algo..."
			bind:value={input}
			onkeydown={handleKeydown}
			disabled={loading}
			aria-label="Mensaje al asistente"
		/>
		<button
			type="button"
			class="chat-panel__send-btn"
			onclick={() => handleSend(input)}
			disabled={loading || !input.trim()}
			aria-label="Enviar mensaje"
		>
			<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="22" y1="2" x2="11" y2="13"/>
				<polygon points="22 2 15 22 11 13 2 9 22 2"/>
			</svg>
		</button>
	</div>
</div>

<style>
	.chat-panel {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		height: 75%;
		display: flex;
		flex-direction: column;
		background-color: #0f172a;
		border-top: 1px solid #1e293b;
		border-radius: 1rem 1rem 0 0;
		z-index: 100;
		overflow: hidden;
	}

	/* Header */
	.chat-panel__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.875rem 1rem;
		border-bottom: 1px solid #1e293b;
		flex-shrink: 0;
	}

	.chat-panel__header-left {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	.chat-panel__avatar {
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background-color: #2563eb;
		color: #ffffff;
		font-size: 0.6875rem;
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.chat-panel__title {
		font-size: 0.9375rem;
		font-weight: 700;
		color: #f1f5f9;
	}

	.chat-panel__subtitle {
		font-size: 0.75rem;
		color: #64748b;
		margin-top: 0.125rem;
	}

	.chat-panel__header-actions {
		display: flex;
		gap: 0.25rem;
	}

	.chat-panel__icon-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border: none;
		border-radius: 0.5rem;
		background: transparent;
		color: #64748b;
		cursor: pointer;
		touch-action: manipulation;
		transition: background-color 0.15s, color 0.15s;
	}

	.chat-panel__icon-btn:hover {
		background-color: #1e293b;
		color: #f1f5f9;
	}

	/* Outcome buttons */
	.chat-panel__outcomes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
		padding: 0.625rem 0.875rem;
		border-bottom: 1px solid #1e293b;
		flex-shrink: 0;
	}

	.chat-panel__outcome-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.375rem;
		min-height: 2.75rem;
		padding: 0.625rem 0.75rem;
		font-size: 0.9375rem;
		font-weight: 700;
		border: none;
		border-radius: 0.625rem;
		cursor: pointer;
		touch-action: manipulation;
		transition: opacity 0.15s, transform 0.1s;
	}

	.chat-panel__outcome-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.chat-panel__outcome-btn:not(:disabled):active {
		transform: scale(0.96);
	}

	.chat-panel__outcome-btn--correct {
		background-color: #16a34a;
		color: #ffffff;
	}

	.chat-panel__outcome-btn--correct:not(:disabled):hover {
		background-color: #15803d;
	}

	.chat-panel__outcome-btn--incorrect {
		background-color: #dc2626;
		color: #ffffff;
	}

	.chat-panel__outcome-btn--incorrect:not(:disabled):hover {
		background-color: #b91c1c;
	}

	/* Message list */
	.chat-panel__messages {
		flex: 1 1 auto;
		overflow-y: auto;
		padding: 0.75rem 0.875rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		scroll-behavior: smooth;
	}

	.chat-panel__message {
		max-width: 82%;
		padding: 0.625rem 0.875rem;
		border-radius: 1rem;
		font-size: 0.9375rem;
		line-height: 1.45;
		word-break: break-word;
	}

	.chat-panel__message--user {
		align-self: flex-end;
		background-color: #2563eb;
		color: #ffffff;
		border-bottom-right-radius: 0.25rem;
	}

	.chat-panel__message--assistant {
		align-self: flex-start;
		background-color: #1e293b;
		color: #e2e8f0;
		border-bottom-left-radius: 0.25rem;
	}

	.chat-panel__message--correct {
		background-color: #166534;
		color: #dcfce7;
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	.chat-panel__message--incorrect {
		background-color: #7f1d1d;
		color: #fee2e2;
		font-weight: 700;
		letter-spacing: 0.02em;
	}

	/* Typing indicator */
	.chat-panel__message--typing {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.75rem 1rem;
		min-width: 3rem;
	}

	.typing-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background-color: #475569;
		animation: typing-bounce 1.2s ease-in-out infinite;
	}

	.typing-dot:nth-child(2) {
		animation-delay: 0.2s;
	}

	.typing-dot:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes typing-bounce {
		0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
		30% { transform: translateY(-6px); opacity: 1; }
	}

	/* Input row */
	.chat-panel__input-row {
		display: flex;
		gap: 0.5rem;
		padding: 0.75rem 0.875rem;
		border-top: 1px solid #1e293b;
		flex-shrink: 0;
	}

	.chat-panel__input {
		flex: 1 1 auto;
		min-height: 2.75rem;
		padding: 0.625rem 0.875rem;
		font-size: 1rem;
		color: #f1f5f9;
		background-color: #1e293b;
		border: 1px solid #334155;
		border-radius: 0.625rem;
		outline: none;
		transition: border-color 0.15s;
	}

	.chat-panel__input:focus {
		border-color: #2563eb;
	}

	.chat-panel__input::placeholder {
		color: #475569;
	}

	.chat-panel__input:disabled {
		opacity: 0.6;
	}

	.chat-panel__send-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.75rem;
		height: 2.75rem;
		flex-shrink: 0;
		border: none;
		border-radius: 0.625rem;
		background-color: #2563eb;
		color: #ffffff;
		cursor: pointer;
		touch-action: manipulation;
		transition: background-color 0.15s;
	}

	.chat-panel__send-btn:disabled {
		background-color: #1e293b;
		color: #475569;
		cursor: not-allowed;
	}

	.chat-panel__send-btn:not(:disabled):hover {
		background-color: #1d4ed8;
	}
</style>
