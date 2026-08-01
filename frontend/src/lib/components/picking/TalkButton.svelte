<script lang="ts">
	import { fade } from 'svelte/transition';
	import type { RemitoState } from '$lib/api/client';
	import { askPickingAssistant, getTtsAudio } from '$lib/api/client';
	import { say, sayFallback } from '$lib/audio/speaker';

	interface Props {
		remito: RemitoState;
		scannerRef: { pause: () => void; resume: () => void } | null;
	}

	let { remito, scannerRef }: Props = $props();

	let open = $state(false);
	let asking = $state(false);
	let lastAnswer = $state<string | null>(null);
	let lastFuente = $state<'n8n' | 'fallback' | null>(null);
	let inputText = $state('');
	let sttSupported = $state(false);
	let listening = $state(false);
	let errorMsg = $state<string | null>(null);

	// STT setup
	type SpeechRec = typeof window.SpeechRecognition;
	let recognition: InstanceType<SpeechRec> | null = null;

	$effect(() => {
		if (typeof window !== 'undefined') {
			const SpeechRecognition = window.SpeechRecognition ?? (window as any).webkitSpeechRecognition;
			sttSupported = !!SpeechRecognition;
		}
	});

	const CHIPS = [
		'¿Qué me falta?',
		'¿Dónde está el siguiente?',
		'¿Cuánto llevo?'
	];

	function openSheet() {
		open = true;
		lastAnswer = null;
		errorMsg = null;
		scannerRef?.pause();
	}

	function closeSheet() {
		open = false;
		stopListening();
		scannerRef?.resume();
	}

	async function ask(pregunta: string) {
		if (asking || !pregunta.trim()) return;
		asking = true;
		lastAnswer = null;
		errorMsg = null;
		inputText = '';

		try {
			const res = await askPickingAssistant(remito.remito_id, pregunta.trim());
			lastAnswer = res.respuesta;
			lastFuente = res.fuente;

			// Speak the answer — try TTS endpoint first, fall back to Web Speech
			try {
				const blob = await getTtsAudio(res.respuesta);
				await say(blob);
			} catch {
				sayFallback(res.respuesta);
			}
		} catch (err) {
			errorMsg = err instanceof Error ? err.message : 'Error al consultar al asistente.';
		} finally {
			asking = false;
		}
	}

	function startListening() {
		if (!sttSupported || listening) return;
		const SpeechRecognition = window.SpeechRecognition ?? (window as any).webkitSpeechRecognition;
		recognition = new SpeechRecognition();
		recognition.lang = 'es-AR';
		recognition.continuous = false;
		recognition.interimResults = false;

		recognition.onstart = () => {
			listening = true;
		};

		recognition.onresult = (event: SpeechRecognitionEvent) => {
			const transcript = event.results[0]?.[0]?.transcript ?? '';
			if (transcript.trim()) {
				ask(transcript.trim());
			}
		};

		recognition.onerror = () => {
			listening = false;
		};

		recognition.onend = () => {
			listening = false;
		};

		recognition.start();
	}

	function stopListening() {
		try {
			recognition?.stop();
		} catch {
			// ignore
		}
		listening = false;
	}

	function handleInputKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && !(e as any).isComposing) {
			ask(inputText);
		}
	}
</script>

<button
	type="button"
	class="talk-trigger"
	onclick={openSheet}
	aria-label="Abrir asistente de voz"
>
	<svg class="talk-trigger__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
		<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
		<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
		<line x1="12" y1="19" x2="12" y2="23"></line>
		<line x1="8" y1="23" x2="16" y2="23"></line>
	</svg>
	<span class="talk-trigger__label">Preguntar a IA</span>
</button>

{#if open}
	<!-- Backdrop -->
	<div
		class="talk-backdrop"
		role="presentation"
		onclick={closeSheet}
		transition:fade={{ duration: 200 }}
	></div>

	<!-- Sheet -->
	<div
		class="talk-sheet"
		role="dialog"
		aria-modal="true"
		aria-label="Asistente InvenTIA"
		transition:fade={{ duration: 200 }}
	>
		<div class="talk-sheet__handle" aria-hidden="true"></div>

		<div class="talk-sheet__header">
			<span class="talk-sheet__title">Asistente InvenTIA</span>
			<button type="button" class="talk-sheet__close" onclick={closeSheet} aria-label="Cerrar asistente">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			</button>
		</div>

		<!-- Quick chips -->
		<div class="talk-sheet__chips" role="group" aria-label="Preguntas frecuentes">
			{#each CHIPS as chip}
				<button
					type="button"
					class="talk-chip"
					disabled={asking}
					onclick={() => ask(chip)}
				>
					{chip}
				</button>
			{/each}
		</div>

		<!-- STT button -->
		{#if sttSupported}
			<button
				type="button"
				class="talk-sheet__mic"
				class:talk-sheet__mic--listening={listening}
				disabled={asking}
				onpointerdown={startListening}
				onpointerup={stopListening}
				aria-label={listening ? 'Escuchando…' : 'Mantener presionado para hablar'}
			>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
					<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
					<line x1="12" y1="19" x2="12" y2="23"></line>
					<line x1="8" y1="23" x2="16" y2="23"></line>
				</svg>
				<span>{listening ? 'Escuchando…' : 'Mantener para hablar'}</span>
			</button>
		{/if}

		<!-- Text input fallback -->
		<div class="talk-sheet__input-row">
			<input
				type="text"
				class="talk-sheet__input"
				placeholder="Escribí tu pregunta…"
				bind:value={inputText}
				onkeydown={handleInputKeydown}
				disabled={asking}
				autocomplete="off"
				spellcheck={false}
			/>
			<button
				type="button"
				class="talk-sheet__send"
				disabled={asking || !inputText.trim()}
				onclick={() => ask(inputText)}
				aria-label="Enviar pregunta"
			>
				{#if asking}
					<span class="talk-sheet__spinner" aria-hidden="true"></span>
				{:else}
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<line x1="22" y1="2" x2="11" y2="13"></line>
						<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
					</svg>
				{/if}
			</button>
		</div>

		<!-- Answer -->
		{#if asking}
			<div class="talk-sheet__thinking" role="status">
				<span class="talk-sheet__dot"></span>
				<span class="talk-sheet__dot"></span>
				<span class="talk-sheet__dot"></span>
				<span class="sr-only">Consultando al asistente…</span>
			</div>
		{/if}

		{#if lastAnswer}
			<div class="talk-sheet__answer" role="status">
				<div class="talk-sheet__answer-badge">
					{lastFuente === 'n8n' ? 'InvenTIA' : 'InvenTIA (offline)'}
				</div>
				<p class="talk-sheet__answer-text">{lastAnswer}</p>
			</div>
		{/if}

		{#if errorMsg}
			<div class="talk-sheet__error" role="alert">{errorMsg}</div>
		{/if}
	</div>
{/if}

<style>
	/* ── Trigger button ── */
	.talk-trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 3rem;
		padding: 0.625rem 1rem;
		font-size: 0.9375rem;
		font-weight: 700;
		color: #ffffff;
		background-color: #0f172a;
		border: none;
		border-radius: 0.625rem;
		cursor: pointer;
		touch-action: manipulation;
		width: 100%;
		justify-content: center;
	}

	.talk-trigger:active {
		background-color: #1e293b;
	}

	.talk-trigger__icon {
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
	}

	.talk-trigger__label {
		font-size: 0.9375rem;
	}

	/* ── Backdrop ── */
	.talk-backdrop {
		position: fixed;
		inset: 0;
		z-index: 49;
		background-color: rgba(15, 23, 42, 0.5);
	}

	/* ── Sheet ── */
	.talk-sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 50;
		background-color: #ffffff;
		border-top: 1.5px solid #e2e8f0;
		border-radius: 1rem 1rem 0 0;
		padding: 0.5rem 1rem 2rem;
		box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.14);
		display: flex;
		flex-direction: column;
		gap: 0.875rem;
	}

	.talk-sheet__handle {
		width: 2.5rem;
		height: 4px;
		background-color: #cbd5e1;
		border-radius: 9999px;
		margin: 0.5rem auto 0.25rem;
	}

	.talk-sheet__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.talk-sheet__title {
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
	}

	.talk-sheet__close {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		color: #64748b;
		background: none;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		padding: 0;
	}

	.talk-sheet__close svg {
		width: 1.25rem;
		height: 1.25rem;
	}

	/* ── Chips ── */
	.talk-sheet__chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.talk-chip {
		padding: 0.5rem 0.875rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #1d4ed8;
		background-color: #eff6ff;
		border: 1.5px solid #bfdbfe;
		border-radius: 9999px;
		cursor: pointer;
		touch-action: manipulation;
		white-space: nowrap;
	}

	.talk-chip:active {
		background-color: #dbeafe;
	}

	.talk-chip:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* ── Mic ── */
	.talk-sheet__mic {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.625rem;
		min-height: 3.25rem;
		padding: 0.75rem 1.25rem;
		font-size: 0.9375rem;
		font-weight: 700;
		color: #0f172a;
		background-color: #f1f5f9;
		border: 2px solid #e2e8f0;
		border-radius: 0.75rem;
		cursor: pointer;
		touch-action: manipulation;
		user-select: none;
		-webkit-user-select: none;
		transition: background-color 0.1s ease, border-color 0.1s ease;
	}

	.talk-sheet__mic svg {
		width: 1.25rem;
		height: 1.25rem;
		flex-shrink: 0;
	}

	.talk-sheet__mic--listening {
		background-color: #fee2e2;
		border-color: #fca5a5;
		color: #dc2626;
	}

	.talk-sheet__mic:disabled {
		opacity: 0.5;
	}

	/* ── Text input ── */
	.talk-sheet__input-row {
		display: flex;
		gap: 0.5rem;
	}

	.talk-sheet__input {
		flex: 1 1 auto;
		min-height: 2.75rem;
		padding: 0.625rem 0.875rem;
		font-size: 0.9375rem;
		color: #0f172a;
		background-color: #f8fafc;
		border: 1.5px solid #e2e8f0;
		border-radius: 0.625rem;
		outline: none;
	}

	.talk-sheet__input:focus {
		border-color: #2563eb;
		background-color: #ffffff;
	}

	.talk-sheet__send {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.75rem;
		height: 2.75rem;
		color: #ffffff;
		background-color: #2563eb;
		border: none;
		border-radius: 0.625rem;
		cursor: pointer;
	}

	.talk-sheet__send svg {
		width: 1.125rem;
		height: 1.125rem;
	}

	.talk-sheet__send:disabled {
		background-color: #94a3b8;
		cursor: not-allowed;
	}

	/* ── Thinking dots ── */
	.talk-sheet__thinking {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.75rem 1rem;
		background-color: #f8fafc;
		border-radius: 0.625rem;
	}

	.talk-sheet__dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background-color: #94a3b8;
		animation: dot-bounce 1.2s ease-in-out infinite;
	}

	.talk-sheet__dot:nth-child(2) { animation-delay: 0.2s; }
	.talk-sheet__dot:nth-child(3) { animation-delay: 0.4s; }

	@keyframes dot-bounce {
		0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
		40% { transform: translateY(-6px); opacity: 1; }
	}

	/* ── Answer ── */
	.talk-sheet__answer {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		background-color: #f0fdf4;
		border: 1.5px solid #bbf7d0;
		border-radius: 0.75rem;
	}

	.talk-sheet__answer-badge {
		align-self: flex-start;
		padding: 0.125rem 0.5rem;
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: #15803d;
		background-color: #dcfce7;
		border-radius: 9999px;
	}

	.talk-sheet__answer-text {
		font-size: 1rem;
		font-weight: 600;
		line-height: 1.5;
		color: #0f172a;
		margin: 0;
	}

	/* ── Error ── */
	.talk-sheet__error {
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: #991b1b;
		background-color: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 0.625rem;
	}

	/* ── Spinner ── */
	.talk-sheet__spinner {
		display: inline-block;
		width: 1rem;
		height: 1rem;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: #ffffff;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border-width: 0;
	}
</style>
