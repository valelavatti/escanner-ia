<script>
	import '../app.css';

	let { children } = $props();
</script>

<div class="app">
	{@render children()}
</div>

<style>
	.app {
		min-height: 100vh;
		padding: env(safe-area-inset-top) 1rem env(safe-area-inset-bottom);
	}
</style>
