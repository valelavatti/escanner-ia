/**
 * speaker.ts — thin wrapper around HTMLAudioElement + Web Speech API fallback.
 *
 * The unlock() call MUST happen inside a direct user gesture (e.g. the onclick
 * of "Comenzar remito"). Without it, iOS/Android refuse programmatic play()
 * with NotAllowedError — the app goes mute while everything else works fine.
 *
 * Pattern mirrors QrPrintModal: blob → createObjectURL → play() → revokeObjectURL.
 */

// ~200-byte silent mp3 used to unlock the audio context on first tap.
const SILENT_MP3 =
	'data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAADhgCenp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6e////////////////////////////////////////////////////////////////AAAAAExhdmM1OC41NAAAAAAAAAAAAAAAACQAAAAAAAAAAA4GBqjuAAAAAAAAAAAAAAAAAAAA//sQZAAP8AAAaQAAAAgAAA0gAAABAAABpAAAACAAADSAAAAETEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';

let audio: HTMLAudioElement | null = null;
let unlocked = false;

function getAudio(): HTMLAudioElement {
	if (!audio) {
		audio = new Audio();
		audio.preload = 'none';
	}
	return audio;
}

/**
 * Call once from a real click handler (e.g. "Comenzar remito" button).
 * Plays a silent mp3 to satisfy the browser autoplay policy.
 */
export async function unlock(): Promise<void> {
	if (unlocked) return;
	const el = getAudio();
	el.muted = true;
	el.src = SILENT_MP3;
	try {
		await el.play();
	} catch {
		// Some browsers still reject even with muted — that is fine.
	} finally {
		el.muted = false;
		el.src = '';
		unlocked = true;
	}
}

/**
 * Play an audio Blob (mp3 from the TTS endpoint).
 * Revokes the object URL once playback ends or errors.
 */
export function say(blob: Blob): Promise<void> {
	return new Promise((resolve) => {
		const el = getAudio();
		const url = URL.createObjectURL(blob);

		function cleanup() {
			URL.revokeObjectURL(url);
			el.removeEventListener('ended', cleanup);
			el.removeEventListener('error', cleanup);
			resolve();
		}

		el.addEventListener('ended', cleanup, { once: true });
		el.addEventListener('error', cleanup, { once: true });

		el.src = url;
		el.play().catch(() => {
			// If autoplay is still blocked, fall through to the cleanup.
			cleanup();
		});
	});
}

/**
 * Web Speech API fallback — no network required, no backend dependency.
 * Uses es-AR voice when available, otherwise the first Spanish voice, then default.
 */
export function sayFallback(text: string): void {
	if (typeof window === 'undefined' || !window.speechSynthesis) return;

	window.speechSynthesis.cancel();

	const utterance = new SpeechSynthesisUtterance(text);
	utterance.lang = 'es-AR';
	utterance.rate = 1.05;

	const voices = window.speechSynthesis.getVoices();
	const arVoice = voices.find((v) => v.lang === 'es-AR');
	const esVoice = voices.find((v) => v.lang.startsWith('es'));
	if (arVoice) utterance.voice = arVoice;
	else if (esVoice) utterance.voice = esVoice;

	window.speechSynthesis.speak(utterance);
}

/**
 * Vibrate the device (no-op on iOS).
 * pattern: [pause, vibrate, pause, vibrate, ...]
 */
export function vibrate(pattern: number[]): void {
	if (typeof navigator !== 'undefined' && navigator.vibrate) {
		navigator.vibrate(pattern);
	}
}
