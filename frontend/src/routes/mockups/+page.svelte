<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';

	// ── Types ─────────────────────────────────────────────────────────────────────
	type OutcomeKind = 'correct' | 'incorrect';
	type AiStatus   = 'idle' | 'thinking' | 'speaking';

	interface Message {
		id:       number;
		role:     'user' | 'assistant' | 'outcome';
		content:  string;
		outcome?: OutcomeKind;
		ts:       Date;
	}

	// ── Demo context ──────────────────────────────────────────────────────────────
	const PRODUCT = {
		sku:       'LPT-0042-A',
		desc:      'Laptop Acer Aspire 5 · Intel i5-1235U · 15.6"',
		ubicacion: 'Estante B3 · F2-C4',
		deposito:  'Depósito Central',
	};

	const CANNED: Record<OutcomeKind | 'question', string[]> = {
		correct: [
			`Perfecto. ${PRODUCT.sku} registrado en ${PRODUCT.ubicacion}. Avanzá al siguiente ítem del remito.`,
			'Confirmado. Quedan 9 ítems. Continuá por el pasillo B hacia el estante C1.',
			'Escaneo ok. Stock actualizado. Próximo: SKU MON-1190-C en EST-C1 F1-C2.',
		],
		incorrect: [
			`Ese no es el producto correcto. El SKU esperado es ${PRODUCT.sku}. Verificá que la etiqueta coincida y volvé a escanear.`,
			`Error de ubicación. ${PRODUCT.sku} está en ${PRODUCT.ubicacion}, no en la fila 3. Bajá un nivel en el estante B3.`,
			'Producto equivocado. Comprobá que el código de barras no esté dañado y que el lector haya capturado el QR completo.',
		],
		question: [
			`${PRODUCT.sku} está en ${PRODUCT.ubicacion}. Pasillo B, tercer estante desde la entrada, segunda fila.`,
			'Llevás 6 de 15 ítems confirmados. Todos los restantes están en el ala B del depósito.',
			'Hay 14 unidades disponibles. El mínimo de stock es 10, así que estás dentro del rango.',
		],
	};

	function pick<T>(arr: T[]): T {
		return arr[Math.floor(Math.random() * arr.length)];
	}

	// ── AI config ─────────────────────────────────────────────────────────────────
	const GEMINI_KEY = import.meta.env.VITE_GEMINI_API_KEY ?? '';
	const MODEL      = 'gemini-2.0-flash';

	// ── State ─────────────────────────────────────────────────────────────────────
	let seq         = 0;
	let status      = $state<AiStatus>('idle');
	let messages    = $state<Message[]>([{
		id: seq++, role: 'assistant', ts: new Date(),
		content: `Hola. Remito REM-2847 activo · 15 ítems. Primer producto: **${PRODUCT.sku}** en ${PRODUCT.ubicacion}. Usá los botones para registrar el resultado del escaneo.`,
	}]);
	let input       = $state('');
	let muted       = $state(false);
	let listEl      = $state<HTMLElement | undefined>(undefined);

	// Scan flash on phone frame
	let flashResult = $state<OutcomeKind | null>(null);
	let flashTimer: ReturnType<typeof setTimeout> | null = null;

	// Waveform
	let wave        = $state<number[]>(Array.from({ length: 18 }, () => 4));
	let waveTimer: ReturnType<typeof setInterval> | null = null;

	// ── Audio helpers ─────────────────────────────────────────────────────────────
	function startWave() {
		status = 'speaking';
		waveTimer = setInterval(() => {
			wave = Array.from({ length: 18 }, () => 4 + Math.random() * 22);
		}, 110);
	}

	function stopWave() {
		status = 'idle';
		if (waveTimer) { clearInterval(waveTimer); waveTimer = null; }
		wave = Array.from({ length: 18 }, () => 4);
	}

	function speak(text: string) {
		if (muted || typeof window === 'undefined') return;
		window.speechSynthesis.cancel();
		const u = new SpeechSynthesisUtterance(text.replace(/\*\*/g, ''));
		u.lang = 'es-AR';
		u.rate = 1.05;
		const voices = window.speechSynthesis.getVoices();
		const esVoice = voices.find(v => v.lang.startsWith('es') && !v.name.toLowerCase().includes('compact'));
		if (esVoice) u.voice = esVoice;
		u.onstart = startWave;
		u.onend   = stopWave;
		u.onerror = stopWave;
		window.speechSynthesis.speak(u);
	}

	function stopSpeaking() {
		if (typeof window !== 'undefined') window.speechSynthesis.cancel();
		stopWave();
	}

	// ── Scroll ────────────────────────────────────────────────────────────────────
	function scrollDown() {
		if (listEl) setTimeout(() => { if (listEl) listEl.scrollTop = listEl.scrollHeight; }, 60);
	}

	// ── Gemini or mock ────────────────────────────────────────────────────────────
	function buildSystem(): string {
		return [
			'Sos un asistente experto en operaciones de depósito y logística.',
			'Respondés en español rioplatense, de forma muy breve y directa (máximo 2 oraciones).',
			'El operario tiene el scanner en la mano. Priorizá claridad sobre completitud.',
			'Nunca inventés datos. Si no tenés información, decilo en una oración.',
			`Producto activo: ${PRODUCT.sku} — ${PRODUCT.desc}. Ubicación: ${PRODUCT.ubicacion}. Depósito: ${PRODUCT.deposito}.`,
		].join('\n');
	}

	async function callGemini(text: string): Promise<string> {
		const history = messages
			.filter(m => m.role === 'user' || m.role === 'assistant')
			.slice(-20)
			.map(m => ({ role: m.role === 'user' ? 'user' : 'model', parts: [{ text: m.content }] }));

		const body = {
			system_instruction: { parts: [{ text: buildSystem() }] },
			contents: [...history, { role: 'user', parts: [{ text }] }],
			generationConfig: { temperature: 0.3, maxOutputTokens: 120 },
		};
		const res = await fetch(
			`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_KEY}`,
			{ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
		);
		if (!res.ok) throw new Error(`HTTP ${res.status}`);
		const data = await res.json();
		return data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? '(Sin respuesta)';
	}

	async function getReply(kind: 'correct' | 'incorrect' | 'question', context: string): Promise<string> {
		if (GEMINI_KEY) {
			try { return await callGemini(context); } catch { /* fall through */ }
		}
		await new Promise(r => setTimeout(r, 800 + Math.random() * 500));
		return pick(CANNED[kind]);
	}

	// ── Actions ───────────────────────────────────────────────────────────────────
	async function handleOutcome(kind: OutcomeKind) {
		if (status === 'thinking') return;

		// Flash the phone frame
		flashResult = kind;
		if (flashTimer) clearTimeout(flashTimer);
		flashTimer = setTimeout(() => { flashResult = null; }, kind === 'correct' ? 1000 : 2200);

		// Outcome pill in chat
		messages = [...messages, { id: seq++, role: 'outcome', outcome: kind, content: '', ts: new Date() }];
		status = 'thinking';
		scrollDown();

		const ctx = kind === 'correct'
			? `El operario confirmó escaneo correcto del SKU ${PRODUCT.sku}. Dá una confirmación breve y motivadora.`
			: `El operario reportó escaneo incorrecto. SKU esperado: ${PRODUCT.sku}. Guialo en 1-2 pasos concretos para corregirlo.`;

		const reply = await getReply(kind, ctx);
		messages = [...messages, { id: seq++, role: 'assistant', content: reply, ts: new Date() }];
		speak(reply);
		scrollDown();
	}

	async function sendMessage(text: string) {
		const t = text.trim();
		if (!t || status === 'thinking') return;
		messages = [...messages, { id: seq++, role: 'user', content: t, ts: new Date() }];
		input = '';
		status = 'thinking';
		scrollDown();
		const reply = await getReply('question', t);
		messages = [...messages, { id: seq++, role: 'assistant', content: reply, ts: new Date() }];
		speak(reply);
		scrollDown();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.nativeEvent?.isComposing && (e as any).keyCode !== 229) {
			sendMessage(input);
		}
	}

	// Format time helper
	function fmt(d: Date) {
		return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
	}
</script>

<svelte:head>
	<title>InvenTIA — Demo asistente de voz</title>
</svelte:head>

<div class="page">

	<!-- ── Left column: phone mockup ─────────────────────────────────────────── -->
	<div class="col col--phone" aria-label="Vista del scanner">
		<div class="phone">
			<!-- Notch -->
			<div class="phone__notch" aria-hidden="true">
				<span class="phone__notch-pill"></span>
			</div>

			<!-- Status bar -->
			<div class="phone__statusbar" aria-hidden="true">
				<span class="phone__time">9:41</span>
				<span class="phone__icons">
					<!-- signal -->
					<svg width="15" height="11" viewBox="0 0 15 11" fill="currentColor">
						<rect x="0" y="6" width="3" height="5" rx="0.5"/>
						<rect x="4" y="4" width="3" height="7" rx="0.5"/>
						<rect x="8" y="2" width="3" height="9" rx="0.5"/>
						<rect x="12" y="0" width="3" height="11" rx="0.5" opacity="0.3"/>
					</svg>
					<!-- wifi -->
					<svg width="16" height="12" viewBox="0 0 16 12" fill="currentColor">
						<path d="M8 9.5a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/>
						<path d="M4.5 6.5C5.6 5.4 6.7 4.8 8 4.8s2.4.6 3.5 1.7l1.3-1.3C11.4 3.8 9.8 3 8 3S4.6 3.8 3.2 5.2l1.3 1.3z" opacity="0.7"/>
						<path d="M1.5 3.5C3.3 1.7 5.5.8 8 .8s4.7.9 6.5 2.7l1.3-1.3C13.7.8 11 0 8 0S2.3.8.2 2.2L1.5 3.5z" opacity="0.4"/>
					</svg>
					<!-- battery -->
					<svg width="26" height="13" viewBox="0 0 26 13" fill="none">
						<rect x="0.5" y="0.5" width="22" height="12" rx="3.5" stroke="currentColor" stroke-opacity="0.4"/>
						<rect x="1.5" y="1.5" width="17" height="10" rx="2.5" fill="currentColor"/>
						<path d="M24 4.5v4a2 2 0 000-4z" fill="currentColor" fill-opacity="0.4"/>
					</svg>
				</span>
			</div>

			<!-- Viewfinder -->
			<div
				class="phone__viewfinder"
				class:phone__viewfinder--correct={flashResult === 'correct'}
				class:phone__viewfinder--incorrect={flashResult === 'incorrect'}
				aria-label="Visor del scanner"
			>
				<div class="vf__corners" aria-hidden="true">
					<span class="vf__c vf__c--tl"></span>
					<span class="vf__c vf__c--tr"></span>
					<span class="vf__c vf__c--bl"></span>
					<span class="vf__c vf__c--br"></span>
				</div>

				{#if flashResult === 'correct'}
					<div class="vf__result vf__result--correct" transition:fade={{ duration: 100 }}>
						<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
					</div>
				{:else if flashResult === 'incorrect'}
					<div class="vf__result vf__result--incorrect" transition:fade={{ duration: 100 }}>
						<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
					</div>
				{:else}
					<div class="vf__scanline" aria-hidden="true"></div>
				{/if}
			</div>

			<!-- Product strip -->
			<div class="phone__strip" aria-label="Producto activo">
				<p class="strip__label">PRODUCTO ACTIVO</p>
				<p class="strip__sku">{PRODUCT.sku}</p>
				<p class="strip__desc">{PRODUCT.desc}</p>
				<p class="strip__loc">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
					{PRODUCT.ubicacion}
				</p>
			</div>

			<!-- Home bar -->
			<div class="phone__bar" aria-hidden="true"></div>
		</div>
	</div>

	<!-- ── Right column: voice panel ─────────────────────────────────────────── -->
	<div class="col col--panel" aria-label="Asistente IA de voz">
		<div class="panel">

			<!-- Header -->
			<header class="panel__header">
				<div class="panel__header-left">
					<div
						class="panel__orb"
						class:panel__orb--thinking={status === 'thinking'}
						class:panel__orb--speaking={status === 'speaking'}
						aria-hidden="true"
					>
						{#if status === 'thinking'}
							<span class="dots"><span></span><span></span><span></span></span>
						{:else if status === 'speaking'}
							<div class="waveform">
								{#each wave as h}
									<span class="waveform__bar" style="height:{h}px"></span>
								{/each}
							</div>
						{:else}
							<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
								<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
								<line x1="12" y1="19" x2="12" y2="22"/>
							</svg>
						{/if}
					</div>

					<div class="panel__title-wrap">
						<span class="panel__title">InvenTIA</span>
						<span class="panel__status" aria-live="polite">
							{status === 'thinking' ? 'Pensando...' : status === 'speaking' ? 'Hablando' : 'Listo'}
						</span>
					</div>
				</div>

				<div class="panel__header-right">
					<span class="panel__demo-badge">DEMO</span>
					<button
						type="button"
						class="icon-btn"
						onclick={() => { muted = !muted; if (muted) stopSpeaking(); }}
						aria-label={muted ? 'Activar voz' : 'Silenciar'}
					>
						{#if muted}
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
						{:else}
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
						{/if}
					</button>
				</div>
			</header>

			<!-- Context chips -->
			<div class="panel__chips" role="list" aria-label="Contexto activo">
				<span class="chip chip--blue" role="listitem">{PRODUCT.sku}</span>
				<span class="chip chip--green" role="listitem">{PRODUCT.ubicacion}</span>
			</div>

			<!-- Outcome buttons — the two primary CTAs -->
			<div class="panel__outcomes" role="group" aria-label="Resultado del escaneo">
				<button
					type="button"
					class="outcome outcome--incorrect"
					onclick={() => handleOutcome('incorrect')}
					disabled={status === 'thinking'}
					aria-label="Registrar escaneo incorrecto"
				>
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
						<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
					</svg>
					<span>Incorrecto</span>
				</button>

				<button
					type="button"
					class="outcome outcome--correct"
					onclick={() => handleOutcome('correct')}
					disabled={status === 'thinking'}
					aria-label="Registrar escaneo correcto"
				>
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<polyline points="20 6 9 17 4 12"/>
					</svg>
					<span>Correcto</span>
				</button>
			</div>

			<!-- Messages feed -->
			<div
				class="panel__messages"
				bind:this={listEl}
				role="log"
				aria-live="polite"
				aria-label="Conversación con el asistente"
			>
				{#each messages as msg (msg.id)}
					{#if msg.role === 'outcome'}
						<div
							class="pill pill--{msg.outcome}"
							role="status"
							transition:fade={{ duration: 180 }}
						>
							{msg.outcome === 'correct' ? '✓ Escaneo correcto' : '✗ Escaneo incorrecto'}
						</div>
					{:else}
						<div
							class="bubble bubble--{msg.role}"
							transition:fly={{ y: 10, duration: 220, easing: cubicOut }}
						>
							<p class="bubble__text">{msg.content}</p>
							<time class="bubble__time" datetime={msg.ts.toISOString()}>{fmt(msg.ts)}</time>
						</div>
					{/if}
				{/each}

				{#if status === 'thinking'}
					<div class="typing" transition:fade={{ duration: 150 }} aria-label="El asistente está escribiendo">
						<span></span><span></span><span></span>
					</div>
				{/if}
			</div>

			<!-- Quick-ask chips -->
			<div class="panel__quick" role="group" aria-label="Preguntas rápidas">
				{#each ['¿Qué me falta?', '¿Dónde está el siguiente?', '¿Cuánto stock hay?'] as q}
					<button
						type="button"
						class="quick"
						onclick={() => sendMessage(q)}
						disabled={status === 'thinking'}
					>{q}</button>
				{/each}
			</div>

			<!-- Input row -->
			<div class="panel__input-row">
				<input
					type="text"
					class="panel__input"
					bind:value={input}
					onkeydown={handleKeydown}
					placeholder="Preguntá algo..."
					autocomplete="off"
					spellcheck={false}
					disabled={status === 'thinking'}
					aria-label="Mensaje al asistente"
				/>
				<button
					type="button"
					class="send-btn"
					onclick={() => sendMessage(input)}
					disabled={!input.trim() || status === 'thinking'}
					aria-label="Enviar"
				>
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<line x1="22" y1="2" x2="11" y2="13"/>
						<polygon points="22 2 15 22 11 13 2 9 22 2"/>
					</svg>
				</button>
			</div>
		</div>
	</div>
</div>

<style>
	/* ── Page ──────────────────────────────────────────────────────────────────── */
	:global(html), :global(body) { background: #060b14; }

	.page {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2.5rem;
		min-height: 100dvh;
		padding: 2rem 2.5rem;
		max-width: 1120px;
		margin: 0 auto;
		align-items: center;
		font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
		-webkit-font-smoothing: antialiased;
		color: #e2e8f0;
	}

	@media (max-width: 740px) {
		.page { grid-template-columns: 1fr; padding: 1rem; gap: 1.5rem; }
	}

	.col { display: flex; justify-content: center; align-items: center; }

	/* ── Phone frame ───────────────────────────────────────────────────────────── */
	.phone {
		width: 288px;
		background: #0d1117;
		border-radius: 2.75rem;
		border: 1.5px solid rgba(255,255,255,0.09);
		box-shadow:
			0 0 0 7px rgba(255,255,255,0.025),
			0 36px 90px rgba(0,0,0,0.75),
			inset 0 1px 0 rgba(255,255,255,0.07);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	/* Notch */
	.phone__notch {
		display: flex;
		justify-content: center;
		padding: 0.625rem 0 0;
	}
	.phone__notch-pill {
		width: 7rem;
		height: 1.625rem;
		background: #000;
		border-radius: 0 0 1.125rem 1.125rem;
	}

	/* Status bar */
	.phone__statusbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.25rem 1.375rem 0.375rem;
		font-size: 0.6875rem;
		font-weight: 700;
		color: rgba(255,255,255,0.85);
		letter-spacing: -0.01em;
	}
	.phone__icons {
		display: flex;
		align-items: center;
		gap: 0.3125rem;
	}

	/* Viewfinder */
	.phone__viewfinder {
		position: relative;
		aspect-ratio: 1;
		background: #000;
		overflow: hidden;
		transition: box-shadow 0.15s;
	}
	.phone__viewfinder--correct  { box-shadow: inset 0 0 0 3px rgba(22,163,74,0.8); }
	.phone__viewfinder--incorrect { box-shadow: inset 0 0 0 3px rgba(220,38,38,0.8); }

	/* Corner guides */
	.vf__corners { position: absolute; inset: 0; z-index: 2; pointer-events: none; }
	.vf__c {
		position: absolute;
		width: 26px;
		height: 26px;
		border-style: solid;
		border-color: rgba(255,255,255,0.7);
	}
	.vf__c--tl { top: 18px; left: 18px; border-width: 2.5px 0 0 2.5px; border-radius: 3px 0 0 0; }
	.vf__c--tr { top: 18px; right: 18px; border-width: 2.5px 2.5px 0 0; border-radius: 0 3px 0 0; }
	.vf__c--bl { bottom: 18px; left: 18px; border-width: 0 0 2.5px 2.5px; border-radius: 0 0 0 3px; }
	.vf__c--br { bottom: 18px; right: 18px; border-width: 0 2.5px 2.5px 0; border-radius: 0 0 3px 0; }

	/* Scan line */
	.vf__scanline {
		position: absolute;
		inset-inline: 18px;
		height: 2px;
		background: linear-gradient(90deg, transparent, #22d3ee 50%, transparent);
		animation: scan 2.4s ease-in-out infinite;
		z-index: 3;
	}
	@keyframes scan {
		0%   { top: 18px; opacity: 0.3; }
		50%  { opacity: 1; }
		100% { top: calc(100% - 20px); opacity: 0.3; }
	}

	/* Result overlay */
	.vf__result {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 10;
	}
	.vf__result--correct   { background: rgba(22,163,74,0.22);  color: #4ade80; }
	.vf__result--incorrect { background: rgba(220,38,38,0.2);   color: #f87171; }

	/* Product strip */
	.phone__strip {
		padding: 0.875rem 1.125rem;
		border-top: 1px solid rgba(255,255,255,0.06);
		display: flex;
		flex-direction: column;
		gap: 0.1875rem;
	}
	.strip__label {
		font-size: 0.5625rem;
		font-weight: 800;
		letter-spacing: 0.1em;
		color: #475569;
	}
	.strip__sku {
		font-size: 1.0625rem;
		font-weight: 800;
		color: #f1f5f9;
		letter-spacing: 0.04em;
	}
	.strip__desc {
		font-size: 0.71875rem;
		color: #94a3b8;
		line-height: 1.35;
	}
	.strip__loc {
		display: flex;
		align-items: center;
		gap: 0.3125rem;
		font-size: 0.71875rem;
		font-weight: 600;
		color: #4ade80;
		margin-top: 0.25rem;
	}

	/* Home bar */
	.phone__bar {
		width: 7rem;
		height: 4px;
		background: rgba(255,255,255,0.2);
		border-radius: 999px;
		margin: 0.625rem auto 0.9375rem;
	}

	/* ── Voice panel ───────────────────────────────────────────────────────────── */
	.panel {
		background: #090e1a;
		border-radius: 1.5rem;
		border: 1px solid rgba(255,255,255,0.07);
		box-shadow: 0 24px 64px rgba(0,0,0,0.55);
		display: flex;
		flex-direction: column;
		overflow: hidden;
		width: 100%;
		max-width: 480px;
		height: 640px;
		max-height: 90dvh;
	}

	/* Header */
	.panel__header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.0625rem 1.125rem 0.8125rem;
		border-bottom: 1px solid rgba(255,255,255,0.06);
		flex-shrink: 0;
	}
	.panel__header-left  { display: flex; align-items: center; gap: 0.75rem; }
	.panel__header-right { display: flex; align-items: center; gap: 0.5rem; }

	/* Orb */
	.panel__orb {
		width: 2.875rem;
		height: 2.875rem;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		background: radial-gradient(circle at 35% 35%, #1d4ed8, #1e3a8a);
		box-shadow: 0 0 0 1px rgba(59,130,246,0.3), 0 0 20px rgba(37,99,235,0.25);
		color: #93c5fd;
		transition: background 0.4s, box-shadow 0.4s;
	}
	.panel__orb--thinking {
		background: radial-gradient(circle at 35% 35%, #7c3aed, #4c1d95);
		box-shadow: 0 0 0 1px rgba(139,92,246,0.4), 0 0 24px rgba(124,58,237,0.35);
		color: #c4b5fd;
		animation: orb-pulse 1.4s ease-in-out infinite;
	}
	.panel__orb--speaking {
		background: radial-gradient(circle at 35% 35%, #0891b2, #0e7490);
		box-shadow: 0 0 0 1px rgba(6,182,212,0.4), 0 0 28px rgba(8,145,178,0.4);
		color: #67e8f9;
	}
	@keyframes orb-pulse {
		0%,100% { transform: scale(1); opacity: 1; }
		50%      { transform: scale(1.06); opacity: 0.85; }
	}

	/* Dots / waveform inside orb */
	.dots { display: flex; align-items: center; gap: 3px; }
	.dots span {
		width: 5px; height: 5px; border-radius: 50%; background: currentColor;
		animation: bdot 1.1s ease-in-out infinite;
	}
	.dots span:nth-child(2) { animation-delay: 0.16s; }
	.dots span:nth-child(3) { animation-delay: 0.32s; }

	.waveform { display: flex; align-items: center; gap: 2px; height: 20px; }
	.waveform__bar {
		display: block; width: 2px; min-height: 4px; border-radius: 2px;
		background: currentColor; transition: height 0.1s ease;
	}

	@keyframes bdot {
		0%,80%,100% { transform: translateY(0); }
		40%          { transform: translateY(-5px); }
	}

	.panel__title-wrap { display: flex; flex-direction: column; gap: 1px; }
	.panel__title  { font-size: 0.9375rem; font-weight: 700; color: #f1f5f9; letter-spacing: 0.01em; }
	.panel__status { font-size: 0.75rem; color: #64748b; }

	.panel__demo-badge {
		font-size: 0.625rem;
		font-weight: 800;
		letter-spacing: 0.1em;
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
		background: rgba(234,179,8,0.13);
		color: #fde047;
		border: 1px solid rgba(234,179,8,0.22);
	}

	.icon-btn {
		width: 2rem; height: 2rem; border-radius: 50%; border: none;
		display: flex; align-items: center; justify-content: center;
		background: rgba(255,255,255,0.05); color: #94a3b8; cursor: pointer;
		transition: background 0.18s, color 0.18s;
	}
	.icon-btn:hover { background: rgba(255,255,255,0.1); color: #e2e8f0; }

	/* Context chips */
	.panel__chips {
		display: flex; flex-wrap: wrap; gap: 0.375rem;
		padding: 0.5rem 1.125rem; flex-shrink: 0;
	}
	.chip {
		display: inline-flex; align-items: center;
		padding: 0.25rem 0.625rem; border-radius: 999px;
		font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
	}
	.chip--blue { background: rgba(37,99,235,0.18); color: #93c5fd; border: 1px solid rgba(59,130,246,0.25); }
	.chip--green { background: rgba(22,163,74,0.15); color: #86efac; border: 1px solid rgba(34,197,94,0.22); }

	/* Outcome buttons */
	.panel__outcomes {
		display: grid; grid-template-columns: 1fr 1fr;
		gap: 0.625rem; padding: 0 1.125rem 0.75rem; flex-shrink: 0;
	}
	.outcome {
		display: flex; align-items: center; justify-content: center;
		gap: 0.5rem; padding: 0.9375rem 1rem;
		border: none; border-radius: 0.875rem;
		font-size: 1rem; font-weight: 700; cursor: pointer;
		transition: transform 0.12s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.18s, opacity 0.15s, background 0.18s;
		touch-action: manipulation; letter-spacing: 0.01em;
	}
	.outcome:active { transform: scale(0.95); }
	.outcome:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

	.outcome--incorrect {
		background: rgba(220,38,38,0.1); color: #fca5a5;
		border: 1.5px solid rgba(220,38,38,0.32);
		box-shadow: 0 0 20px rgba(220,38,38,0.07);
	}
	.outcome--incorrect:hover:not(:disabled) {
		background: rgba(220,38,38,0.2);
		box-shadow: 0 0 28px rgba(220,38,38,0.22);
		transform: scale(1.02);
	}
	.outcome--correct {
		background: rgba(22,163,74,0.1); color: #86efac;
		border: 1.5px solid rgba(22,163,74,0.32);
		box-shadow: 0 0 20px rgba(22,163,74,0.07);
	}
	.outcome--correct:hover:not(:disabled) {
		background: rgba(22,163,74,0.2);
		box-shadow: 0 0 28px rgba(22,163,74,0.22);
		transform: scale(1.02);
	}

	/* Messages */
	.panel__messages {
		flex: 1 1 0; overflow-y: auto;
		padding: 0.5rem 1.125rem;
		display: flex; flex-direction: column; gap: 0.625rem;
		scroll-behavior: smooth;
	}
	.panel__messages::-webkit-scrollbar { width: 3px; }
	.panel__messages::-webkit-scrollbar-track { background: transparent; }
	.panel__messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

	/* Bubbles */
	.bubble { display: flex; flex-direction: column; gap: 0.25rem; max-width: 84%; }
	.bubble--user      { align-self: flex-end; align-items: flex-end; }
	.bubble--assistant { align-self: flex-start; align-items: flex-start; }

	.bubble__text {
		margin: 0; padding: 0.625rem 0.9375rem;
		border-radius: 1rem; font-size: 0.9375rem; line-height: 1.5;
		white-space: pre-wrap;
	}
	.bubble--user .bubble__text {
		background: rgba(37,99,235,0.22); color: #bfdbfe;
		border: 1px solid rgba(59,130,246,0.2); border-bottom-right-radius: 0.25rem;
	}
	.bubble--assistant .bubble__text {
		background: rgba(255,255,255,0.05); color: #e2e8f0;
		border: 1px solid rgba(255,255,255,0.07); border-bottom-left-radius: 0.25rem;
	}
	.bubble__time { font-size: 0.6875rem; color: #475569; padding: 0 0.25rem; }

	/* Outcome pills */
	.pill {
		align-self: center; padding: 0.3125rem 0.9375rem;
		border-radius: 999px; font-size: 0.8125rem; font-weight: 600;
		letter-spacing: 0.02em;
	}
	.pill--correct   { background: rgba(22,163,74,0.15);   color: #86efac; border: 1px solid rgba(22,163,74,0.3); }
	.pill--incorrect { background: rgba(220,38,38,0.12); color: #fca5a5; border: 1px solid rgba(220,38,38,0.28); }

	/* Typing indicator */
	.typing {
		display: flex; align-items: center; gap: 5px;
		padding: 0.625rem 0.875rem;
		background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.07);
		border-radius: 1rem; border-bottom-left-radius: 0.25rem;
		width: fit-content; align-self: flex-start;
	}
	.typing span {
		width: 7px; height: 7px; border-radius: 50%; background: #475569;
		animation: bdot 1.1s ease-in-out infinite;
	}
	.typing span:nth-child(2) { animation-delay: 0.16s; }
	.typing span:nth-child(3) { animation-delay: 0.32s; }

	/* Quick chips */
	.panel__quick {
		display: flex; flex-wrap: wrap; gap: 0.375rem;
		padding: 0.625rem 1.125rem 0.5rem;
		border-top: 1px solid rgba(255,255,255,0.05); flex-shrink: 0;
	}
	.quick {
		padding: 0.3125rem 0.75rem; border-radius: 999px;
		border: 1px solid rgba(255,255,255,0.1);
		background: rgba(255,255,255,0.04); color: #94a3b8;
		font-size: 0.8125rem; cursor: pointer;
		transition: background 0.16s, color 0.16s;
	}
	.quick:hover:not(:disabled) { background: rgba(255,255,255,0.09); color: #e2e8f0; }
	.quick:disabled { opacity: 0.4; cursor: not-allowed; }

	/* Input row */
	.panel__input-row {
		display: flex; align-items: center; gap: 0.625rem;
		padding: 0.75rem 1.125rem;
		border-top: 1px solid rgba(255,255,255,0.06);
		flex-shrink: 0; background: #090e1a;
	}
	.panel__input {
		flex: 1 1 0; padding: 0.625rem 0.9375rem;
		background: rgba(255,255,255,0.06);
		border: 1px solid rgba(255,255,255,0.1); border-radius: 0.625rem;
		font-size: 0.9375rem; color: #e2e8f0; outline: none;
		transition: border-color 0.18s;
	}
	.panel__input::placeholder { color: #475569; }
	.panel__input:focus   { border-color: rgba(59,130,246,0.5); }
	.panel__input:disabled { opacity: 0.5; }

	.send-btn {
		width: 2.5rem; height: 2.5rem; border-radius: 50%; border: none;
		display: flex; align-items: center; justify-content: center;
		background: #2563eb; color: #fff; cursor: pointer; flex-shrink: 0;
		transition: background 0.18s, transform 0.12s;
	}
	.send-btn:hover:not(:disabled)  { background: #1d4ed8; }
	.send-btn:active:not(:disabled) { transform: scale(0.92); }
	.send-btn:disabled { background: #1e293b; color: #475569; cursor: not-allowed; }
</style>
