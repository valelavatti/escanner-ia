<script lang="ts">
	let activeScreen = $state(0);

	const screens = [
		{ label: 'Navegación', index: 0 },
		{ label: 'Llegada', index: 1 },
		{ label: 'Confirmación', index: 2 },
		{ label: 'Error', index: 3 },
		{ label: 'Resumen', index: 4 }
	];

	function next() {
		activeScreen = (activeScreen + 1) % screens.length;
	}
	function prev() {
		activeScreen = (activeScreen - 1 + screens.length) % screens.length;
	}
</script>

<svelte:head>
	<title>Mockups — Picking IA</title>
</svelte:head>

<div class="showcase">
	<!-- Screen selector tabs -->
	<nav class="tabs" aria-label="Pantallas">
		{#each screens as s}
			<button
				class="tab"
				class:tab--active={activeScreen === s.index}
				onclick={() => (activeScreen = s.index)}
			>
				{s.label}
			</button>
		{/each}
	</nav>

	<!-- Phone frame -->
	<div class="stage">
		<button class="arrow arrow--left" onclick={prev} aria-label="Anterior">&#8592;</button>

		<div class="phone">
			<div class="phone__frame">
				<!-- Dynamic Island notch -->
				<div class="phone__island"></div>

				<!-- STATUS BAR -->
				<div class="phone__statusbar">
					<span class="phone__time">09:41</span>
					<div class="phone__statusicons">
						<!-- Signal -->
						<svg width="16" height="11" viewBox="0 0 16 11" fill="none" aria-hidden="true">
							<rect x="0" y="8" width="3" height="3" rx="0.5" fill="currentColor" opacity="0.35"/>
							<rect x="4.5" y="5.5" width="3" height="5.5" rx="0.5" fill="currentColor" opacity="0.35"/>
							<rect x="9" y="3" width="3" height="8" rx="0.5" fill="currentColor"/>
							<rect x="13.5" y="0" width="2.5" height="11" rx="0.5" fill="currentColor"/>
						</svg>
						<!-- Wifi -->
						<svg width="16" height="12" viewBox="0 0 16 12" fill="none" aria-hidden="true">
							<path d="M8 9.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z" fill="currentColor"/>
							<path d="M3.5 6.5C5 5 6.4 4.2 8 4.2s3 .8 4.5 2.3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/>
							<path d="M1 4C3.2 1.8 5.4 0.8 8 0.8s4.8 1 7 3.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.5"/>
						</svg>
						<!-- Battery -->
						<div class="battery">
							<div class="battery__fill" style="width:82%"></div>
							<div class="battery__cap"></div>
						</div>
					</div>
				</div>

				<!-- SCREEN CONTENT -->
				<div class="phone__screen">

					<!-- ─── SCREEN 0: NAVIGATION ─── -->
					{#if activeScreen === 0}
					<div class="screen screen--nav">
						<!-- Progress bar top -->
						<div class="progress-bar">
							<div class="progress-bar__track">
								<div class="progress-bar__fill" style="width: 34%"></div>
							</div>
							<span class="progress-bar__label">12 / 35</span>
						</div>

						<!-- Product image -->
						<div class="nav__product-image">
							<img src="/mockup-product.png" alt="Caja de cartón industrial" />
						</div>

						<!-- Product info -->
						<div class="nav__product-info">
							<p class="nav__sku">SKU-00421-B</p>
							<h2 class="nav__name">Caja Corrugada 60x40</h2>
							<div class="nav__qty">
								<span class="nav__qty-label">Cantidad</span>
								<span class="nav__qty-value">3</span>
							</div>
						</div>

						<!-- Direction arrow -->
						<div class="nav__arrow-wrap">
							<div class="nav__arrow" aria-label="Girar a la derecha">
								<svg viewBox="0 0 80 80" fill="none">
									<path d="M20 40h40M45 25l15 15-15 15" stroke="currentColor" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
								</svg>
							</div>
						</div>

						<!-- Location + distance -->
						<div class="nav__location">
							<div class="nav__location-badge">
								<span class="nav__location-icon">
									<svg viewBox="0 0 24 24" fill="none" width="20" height="20"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5S13.38 11.5 12 11.5z" fill="currentColor"/></svg>
								</span>
								<span class="nav__location-text">Pasillo B · Est. 4 · Nivel 2</span>
							</div>
							<div class="nav__distance">
								<span class="nav__distance-value">18</span>
								<span class="nav__distance-unit">m</span>
							</div>
						</div>
					</div>
					{/if}

					<!-- ─── SCREEN 1: ARRIVAL ─── -->
					{#if activeScreen === 1}
					<div class="screen screen--arrival">
						<div class="arrival__pulse-ring"></div>
						<div class="arrival__image-wrap">
							<img src="/mockup-product.png" alt="Caja Corrugada 60x40" />
						</div>

						<div class="arrival__badge">
							<svg viewBox="0 0 24 24" fill="none" width="22" height="22"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="currentColor"/></svg>
							Producto encontrado
						</div>

						<h2 class="arrival__name">Caja Corrugada 60x40</h2>
						<p class="arrival__sku">SKU-00421-B</p>

						<div class="arrival__location-card">
							<div class="arrival__location-row">
								<span class="arrival__location-key">Pasillo</span>
								<span class="arrival__location-val">B</span>
							</div>
							<div class="arrival__location-row">
								<span class="arrival__location-key">Estantería</span>
								<span class="arrival__location-val">4</span>
							</div>
							<div class="arrival__location-row arrival__location-row--highlight">
								<span class="arrival__location-key">Nivel</span>
								<span class="arrival__location-val">2</span>
							</div>
						</div>

						<p class="arrival__hint">Escanea el producto para confirmar</p>
					</div>
					{/if}

					<!-- ─── SCREEN 2: CONFIRMATION ─── -->
					{#if activeScreen === 2}
					<div class="screen screen--confirm">
						<div class="confirm__circle">
							<svg class="confirm__check" viewBox="0 0 80 80" fill="none">
								<circle cx="40" cy="40" r="38" stroke="currentColor" stroke-width="4"/>
								<path d="M22 41l13 13 23-27" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
							</svg>
						</div>

						<h2 class="confirm__title">Producto confirmado</h2>
						<p class="confirm__name">Caja Corrugada 60x40</p>

						<div class="confirm__counter">
							<span class="confirm__counter-current">13</span>
							<span class="confirm__counter-sep">/</span>
							<span class="confirm__counter-total">35</span>
						</div>

						<div class="confirm__progress">
							<div class="confirm__progress-fill" style="width: 37%"></div>
						</div>

						<p class="confirm__next-label">Siguiente producto en</p>
						<div class="confirm__countdown">3</div>
					</div>
					{/if}

					<!-- ─── SCREEN 3: ERROR ─── -->
					{#if activeScreen === 3}
					<div class="screen screen--error">
						<div class="error__icon">
							<svg viewBox="0 0 80 80" fill="none">
								<circle cx="40" cy="40" r="38" stroke="currentColor" stroke-width="4"/>
								<path d="M40 22v22" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
								<circle cx="40" cy="54" r="3.5" fill="currentColor"/>
							</svg>
						</div>

						<h2 class="error__title">Producto incorrecto</h2>

						<div class="error__compare">
							<div class="error__product error__product--expected">
								<span class="error__product-tag error__product-tag--expected">Esperado</span>
								<img src="/mockup-product.png" alt="Producto esperado" />
								<p class="error__product-name">Caja Corrugada 60x40</p>
								<p class="error__product-sku">SKU-00421-B</p>
							</div>
							<div class="error__vs">&#8800;</div>
							<div class="error__product error__product--scanned">
								<span class="error__product-tag error__product-tag--scanned">Escaneado</span>
								<div class="error__product-placeholder">?</div>
								<p class="error__product-name">Caja Simple 40x30</p>
								<p class="error__product-sku">SKU-00318-A</p>
							</div>
						</div>

						<div class="error__action">
							<svg viewBox="0 0 24 24" fill="none" width="20" height="20"><path d="M19 12H5M12 5l-7 7 7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
							Volvé a Pasillo B · Est. 4 · Nivel 2
						</div>
					</div>
					{/if}

					<!-- ─── SCREEN 4: SUMMARY ─── -->
					{#if activeScreen === 4}
					<div class="screen screen--summary">
						<div class="summary__badge">
							<svg viewBox="0 0 24 24" fill="none" width="28" height="28"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
						</div>
						<h2 class="summary__title">Tarea completada</h2>
						<p class="summary__order">Orden #ORD-2024-0847</p>

						<div class="summary__stats">
							<div class="summary__stat">
								<span class="summary__stat-value">23:14</span>
								<span class="summary__stat-label">Tiempo total</span>
							</div>
							<div class="summary__stat">
								<span class="summary__stat-value">35</span>
								<span class="summary__stat-label">Productos</span>
							</div>
							<div class="summary__stat">
								<span class="summary__stat-value">840m</span>
								<span class="summary__stat-label">Recorrido</span>
							</div>
							<div class="summary__stat summary__stat--accent">
								<span class="summary__stat-value">97%</span>
								<span class="summary__stat-label">Precisión</span>
							</div>
						</div>

						<div class="summary__breakdown">
							<div class="summary__breakdown-row">
								<span>Scans correctos</span>
								<span class="summary__breakdown-good">34</span>
							</div>
							<div class="summary__breakdown-row">
								<span>Correcciones</span>
								<span class="summary__breakdown-warn">1</span>
							</div>
						</div>

						<button class="summary__cta">
							Nueva orden
						</button>
					</div>
					{/if}

				</div><!-- /phone__screen -->

				<!-- Home indicator -->
				<div class="phone__home-indicator"></div>
			</div>
		</div>

		<button class="arrow arrow--right" onclick={next} aria-label="Siguiente">&#8594;</button>
	</div>

	<p class="showcase__hint">
		{screens[activeScreen].label} &mdash; {activeScreen + 1} de {screens.length}
	</p>
</div>

<style>
	/* ── SHOWCASE WRAPPER ── */
	.showcase {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.5rem;
		padding: 2rem 1rem 3rem;
		background: #0a0a0f;
	}

	/* ── TABS ── */
	.tabs {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-content: center;
	}
	.tab {
		padding: 0.4rem 1rem;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: #6b7280;
		background: #18181b;
		border: 1px solid #27272a;
		border-radius: 999px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.tab:hover { color: #e5e7eb; border-color: #3f3f46; }
	.tab--active {
		color: #fff;
		background: #2563eb;
		border-color: #2563eb;
	}

	/* ── STAGE ── */
	.stage {
		display: flex;
		align-items: center;
		gap: 2rem;
	}
	.arrow {
		width: 2.5rem;
		height: 2.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.25rem;
		color: #9ca3af;
		background: #18181b;
		border: 1px solid #27272a;
		border-radius: 50%;
		cursor: pointer;
		transition: all 0.15s;
		flex-shrink: 0;
	}
	.arrow:hover { color: #fff; border-color: #3f3f46; }

	/* ── PHONE FRAME ── */
	.phone {
		width: 320px;
		flex-shrink: 0;
	}
	.phone__frame {
		position: relative;
		background: #111113;
		border-radius: 44px;
		border: 2px solid #2a2a2e;
		box-shadow:
			0 0 0 6px #18181b,
			0 0 0 7px #2a2a2e,
			0 30px 80px rgba(0,0,0,0.7),
			inset 0 1px 0 rgba(255,255,255,0.06);
		overflow: hidden;
		display: flex;
		flex-direction: column;
		min-height: 680px;
	}

	/* Dynamic Island */
	.phone__island {
		position: absolute;
		top: 12px;
		left: 50%;
		transform: translateX(-50%);
		width: 100px;
		height: 28px;
		background: #000;
		border-radius: 999px;
		z-index: 10;
	}

	/* Status bar */
	.phone__statusbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 22px 0;
		height: 48px;
		color: #fff;
		font-size: 0.72rem;
		font-weight: 600;
		flex-shrink: 0;
	}
	.phone__time { letter-spacing: -0.02em; }
	.phone__statusicons {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.battery {
		position: relative;
		width: 24px;
		height: 12px;
		border: 1.5px solid currentColor;
		border-radius: 2.5px;
	}
	.battery__fill {
		position: absolute;
		top: 1px;
		left: 1px;
		bottom: 1px;
		background: currentColor;
		border-radius: 1px;
	}
	.battery__cap {
		position: absolute;
		right: -4px;
		top: 50%;
		transform: translateY(-50%);
		width: 3px;
		height: 6px;
		background: currentColor;
		border-radius: 0 1px 1px 0;
		opacity: 0.4;
	}

	/* Screen area */
	.phone__screen {
		flex: 1;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	/* Home indicator */
	.phone__home-indicator {
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.phone__home-indicator::after {
		content: '';
		display: block;
		width: 120px;
		height: 4px;
		background: rgba(255,255,255,0.25);
		border-radius: 999px;
	}

	/* ── HINT ── */
	.showcase__hint {
		font-size: 0.8rem;
		color: #52525b;
		text-align: center;
		margin: 0;
	}

	/* ════════════════════════════════════════
	   SCREEN SHARED
	════════════════════════════════════════ */
	.screen {
		flex: 1;
		display: flex;
		flex-direction: column;
		padding: 0.75rem 1.1rem 0.5rem;
		color: #fff;
		overflow: hidden;
	}

	/* ════════════════════════════════════════
	   SCREEN 0 — NAVIGATION
	════════════════════════════════════════ */
	.screen--nav {
		background: #0d0d12;
		gap: 0.55rem;
	}

	/* Progress */
	.progress-bar {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.progress-bar__track {
		flex: 1;
		height: 6px;
		background: #1e1e28;
		border-radius: 999px;
		overflow: hidden;
	}
	.progress-bar__fill {
		height: 100%;
		background: #2563eb;
		border-radius: 999px;
	}
	.progress-bar__label {
		font-size: 0.72rem;
		font-weight: 700;
		color: #6b7280;
		white-space: nowrap;
	}

	/* Product image */
	.nav__product-image {
		background: #16161d;
		border-radius: 14px;
		overflow: hidden;
		height: 130px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid #1f1f2a;
	}
	.nav__product-image img {
		max-height: 110px;
		max-width: 100%;
		object-fit: contain;
	}

	/* Product info */
	.nav__product-info {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.nav__sku {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		color: #2563eb;
		text-transform: uppercase;
	}
	.nav__name {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 800;
		letter-spacing: -0.02em;
		line-height: 1.2;
		color: #f1f5f9;
	}
	.nav__qty {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin-top: 0.15rem;
	}
	.nav__qty-label {
		font-size: 0.7rem;
		color: #71717a;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.nav__qty-value {
		font-size: 1.8rem;
		font-weight: 900;
		line-height: 1;
		color: #f1f5f9;
	}

	/* Arrow */
	.nav__arrow-wrap {
		display: flex;
		justify-content: center;
	}
	.nav__arrow {
		width: 80px;
		height: 80px;
		background: #1a2744;
		border: 2px solid #2563eb;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #2563eb;
		box-shadow: 0 0 0 6px rgba(37,99,235,0.1), 0 0 24px rgba(37,99,235,0.2);
	}
	.nav__arrow svg { width: 48px; height: 48px; }

	/* Location */
	.nav__location {
		display: flex;
		align-items: center;
		justify-content: space-between;
		background: #16161d;
		border: 1px solid #1f1f2a;
		border-radius: 12px;
		padding: 0.55rem 0.8rem;
	}
	.nav__location-badge {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		color: #94a3b8;
	}
	.nav__location-icon { display: flex; color: #2563eb; }
	.nav__location-text {
		font-size: 0.78rem;
		font-weight: 600;
	}
	.nav__distance {
		display: flex;
		align-items: baseline;
		gap: 2px;
	}
	.nav__distance-value {
		font-size: 1.8rem;
		font-weight: 900;
		color: #f1f5f9;
		line-height: 1;
	}
	.nav__distance-unit {
		font-size: 0.8rem;
		font-weight: 700;
		color: #6b7280;
	}

	/* ════════════════════════════════════════
	   SCREEN 1 — ARRIVAL
	════════════════════════════════════════ */
	.screen--arrival {
		background: #0a0f1e;
		align-items: center;
		text-align: center;
		gap: 0.6rem;
		position: relative;
	}

	.arrival__pulse-ring {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -55%);
		width: 220px;
		height: 220px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(37,99,235,0.12) 0%, transparent 70%);
		pointer-events: none;
	}

	.arrival__badge {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		background: #1a2744;
		border: 1px solid #2563eb;
		color: #60a5fa;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		border-radius: 999px;
		padding: 0.3rem 0.85rem;
	}

	.arrival__image-wrap {
		width: 160px;
		height: 160px;
		background: #111827;
		border-radius: 20px;
		border: 2px solid #2563eb;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		box-shadow: 0 0 0 6px rgba(37,99,235,0.12), 0 0 40px rgba(37,99,235,0.15);
	}
	.arrival__image-wrap img {
		max-width: 90%;
		max-height: 90%;
		object-fit: contain;
	}

	.arrival__name {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 800;
		color: #f1f5f9;
		line-height: 1.2;
	}
	.arrival__sku {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		color: #2563eb;
		text-transform: uppercase;
	}

	.arrival__location-card {
		width: 100%;
		background: #111827;
		border-radius: 14px;
		border: 1px solid #1e2840;
		overflow: hidden;
	}
	.arrival__location-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid #1e2840;
	}
	.arrival__location-row:last-child { border-bottom: none; }
	.arrival__location-row--highlight {
		background: #1a2744;
	}
	.arrival__location-key {
		font-size: 0.72rem;
		color: #94a3b8;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.arrival__location-val {
		font-size: 1.3rem;
		font-weight: 900;
		color: #f1f5f9;
	}
	.arrival__location-row--highlight .arrival__location-val {
		color: #60a5fa;
	}

	.arrival__hint {
		margin: 0;
		font-size: 0.72rem;
		color: #4b5563;
		font-weight: 500;
	}

	/* ════════════════════════════════════════
	   SCREEN 2 — CONFIRMATION
	════════════════════════════════════════ */
	.screen--confirm {
		background: #041408;
		align-items: center;
		text-align: center;
		gap: 0.6rem;
		justify-content: center;
	}

	.confirm__circle {
		width: 110px;
		height: 110px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #16a34a;
		filter: drop-shadow(0 0 20px rgba(22,163,74,0.4));
	}
	.confirm__check { width: 110px; height: 110px; }

	.confirm__title {
		margin: 0;
		font-size: 1.6rem;
		font-weight: 900;
		color: #16a34a;
		letter-spacing: -0.03em;
		line-height: 1.1;
	}
	.confirm__name {
		margin: 0;
		font-size: 0.9rem;
		color: #6b7280;
		font-weight: 500;
	}

	.confirm__counter {
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
		margin-top: 0.25rem;
	}
	.confirm__counter-current {
		font-size: 3rem;
		font-weight: 900;
		color: #f1f5f9;
		line-height: 1;
	}
	.confirm__counter-sep {
		font-size: 1.5rem;
		color: #374151;
		font-weight: 700;
	}
	.confirm__counter-total {
		font-size: 1.4rem;
		font-weight: 700;
		color: #4b5563;
	}

	.confirm__progress {
		width: 100%;
		height: 6px;
		background: #1a2e1a;
		border-radius: 999px;
		overflow: hidden;
	}
	.confirm__progress-fill {
		height: 100%;
		background: #16a34a;
		border-radius: 999px;
	}

	.confirm__next-label {
		margin: 0.25rem 0 0;
		font-size: 0.72rem;
		color: #6b7280;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.confirm__countdown {
		font-size: 2.5rem;
		font-weight: 900;
		color: #22c55e;
		line-height: 1;
	}

	/* ════════════════════════════════════════
	   SCREEN 3 — ERROR
	════════════════════════════════════════ */
	.screen--error {
		background: #0f0608;
		align-items: center;
		text-align: center;
		gap: 0.65rem;
	}

	.error__icon {
		width: 72px;
		height: 72px;
		color: #dc2626;
		filter: drop-shadow(0 0 16px rgba(220,38,38,0.35));
	}
	.error__icon svg { width: 72px; height: 72px; }

	.error__title {
		margin: 0;
		font-size: 1.4rem;
		font-weight: 900;
		color: #dc2626;
		letter-spacing: -0.02em;
	}

	.error__compare {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		width: 100%;
	}
	.error__product {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.3rem;
		background: #18181b;
		border-radius: 12px;
		padding: 0.6rem 0.4rem;
		position: relative;
	}
	.error__product--expected { border: 1px solid #16a34a33; }
	.error__product--scanned  { border: 1px solid #dc262633; }

	.error__product-tag {
		position: absolute;
		top: -9px;
		font-size: 0.58rem;
		font-weight: 800;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		padding: 2px 8px;
		border-radius: 999px;
	}
	.error__product-tag--expected {
		background: #14532d;
		color: #22c55e;
	}
	.error__product-tag--scanned {
		background: #450a0a;
		color: #f87171;
	}

	.error__product img {
		width: 64px;
		height: 64px;
		object-fit: contain;
	}
	.error__product-placeholder {
		width: 64px;
		height: 64px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 2rem;
		font-weight: 900;
		color: #374151;
		background: #111113;
		border-radius: 8px;
	}
	.error__product-name {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		color: #d1d5db;
		line-height: 1.2;
		text-align: center;
	}
	.error__product-sku {
		margin: 0;
		font-size: 0.58rem;
		color: #6b7280;
		font-weight: 600;
		letter-spacing: 0.05em;
	}

	.error__vs {
		display: flex;
		align-items: center;
		padding-top: 2.5rem;
		font-size: 1.4rem;
		font-weight: 900;
		color: #374151;
		flex-shrink: 0;
	}

	.error__action {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: #1c1c22;
		border: 1px solid #27272a;
		border-radius: 12px;
		padding: 0.65rem 1rem;
		font-size: 0.78rem;
		font-weight: 600;
		color: #94a3b8;
		width: 100%;
		justify-content: center;
	}

	/* ════════════════════════════════════════
	   SCREEN 4 — SUMMARY
	════════════════════════════════════════ */
	.screen--summary {
		background: #0a0a0f;
		align-items: center;
		text-align: center;
		gap: 0.7rem;
	}

	.summary__badge {
		width: 64px;
		height: 64px;
		background: #052e16;
		border: 2px solid #16a34a;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #16a34a;
		box-shadow: 0 0 0 6px rgba(22,163,74,0.08), 0 0 24px rgba(22,163,74,0.15);
	}

	.summary__title {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 900;
		color: #f1f5f9;
		letter-spacing: -0.03em;
	}
	.summary__order {
		margin: 0;
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		color: #4b5563;
		text-transform: uppercase;
	}

	.summary__stats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
		width: 100%;
	}
	.summary__stat {
		background: #111116;
		border: 1px solid #1f1f28;
		border-radius: 12px;
		padding: 0.65rem 0.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.15rem;
	}
	.summary__stat--accent {
		border-color: #1a3a1a;
		background: #0b1f0b;
	}
	.summary__stat-value {
		font-size: 1.4rem;
		font-weight: 900;
		color: #f1f5f9;
		line-height: 1;
	}
	.summary__stat--accent .summary__stat-value { color: #22c55e; }
	.summary__stat-label {
		font-size: 0.62rem;
		font-weight: 600;
		color: #52525b;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.summary__breakdown {
		width: 100%;
		background: #111116;
		border: 1px solid #1f1f28;
		border-radius: 12px;
		overflow: hidden;
	}
	.summary__breakdown-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.55rem 1rem;
		font-size: 0.75rem;
		font-weight: 600;
		color: #71717a;
		border-bottom: 1px solid #1f1f28;
	}
	.summary__breakdown-row:last-child { border-bottom: none; }
	.summary__breakdown-good { color: #22c55e; font-size: 1rem; font-weight: 800; }
	.summary__breakdown-warn { color: #f59e0b; font-size: 1rem; font-weight: 800; }

	.summary__cta {
		width: 100%;
		padding: 0.85rem;
		font-size: 0.95rem;
		font-weight: 800;
		color: #fff;
		background: #2563eb;
		border: none;
		border-radius: 14px;
		cursor: pointer;
		letter-spacing: 0.02em;
		transition: background 0.15s;
	}
	.summary__cta:hover { background: #1d4ed8; }
</style>
