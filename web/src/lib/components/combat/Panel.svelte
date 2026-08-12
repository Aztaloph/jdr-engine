<script lang="ts">
  import type { Snippet } from "svelte";
  import Icon, { type IconName } from "./Icon.svelte";

  let {
    title,
    badge = "",
    icon = undefined,
    flush = false,
    children,
  }: {
    title: string;
    badge?: string;
    icon?: IconName;
    /** Sans padding interne — pour contenus pleine largeur (listes denses). */
    flush?: boolean;
    children?: Snippet;
  } = $props();
</script>

<section class="panel" aria-label={title}>
  <header class="panel-head">
    {#if icon}
      <span class="panel-icon"><Icon name={icon} size={13} /></span>
    {/if}
    <h2 class="panel-title">{title}</h2>
    {#if badge}
      <span class="panel-badge">{badge}</span>
    {/if}
  </header>
  <div class="panel-body" class:flush>
    {@render children?.()}
  </div>
</section>

<style>
  .panel {
    background:
      linear-gradient(rgb(255 255 255 / 0.012), transparent 40%),
      var(--color-bg-elevated);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 6px 18px rgb(0 0 0 / 0.35);
    overflow: hidden;
  }

  .panel-head {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: linear-gradient(rgb(255 255 255 / 0.02), transparent), var(--color-bg-panel);
  }

  .panel-icon {
    display: grid;
    place-items: center;
    color: var(--color-accent);
    opacity: 0.9;
  }

  .panel-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: var(--color-text-primary);
  }

  .panel-badge {
    margin-left: auto;
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    padding: 0.08rem 0.45rem;
    white-space: nowrap;
  }

  .panel-body {
    padding: 0.65rem 0.8rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .panel-body.flush {
    padding: 0;
    gap: 0;
  }
</style>
