<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    title,
    badge = "",
    children,
  }: {
    title: string;
    badge?: string;
    children?: Snippet;
  } = $props();
</script>

<section class="panel" aria-label={title}>
  <header class="panel-head">
    <h2 class="panel-title">{title}</h2>
    {#if badge}
      <span class="panel-badge">{badge}</span>
    {/if}
  </header>
  <div class="panel-body">
    {@render children?.()}
  </div>
</section>

<style>
  .panel {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  .panel-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.9rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: var(--color-bg-panel);
  }

  .panel-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--color-text-primary);
  }

  .panel-badge {
    margin-left: auto;
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    white-space: nowrap;
  }

  .panel-body {
    padding: 0.75rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
</style>
