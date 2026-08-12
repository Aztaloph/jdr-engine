<script lang="ts">
  import Icon from "./Icon.svelte";

  let {
    kind,
    summary,
    detail,
    time = "",
  }: {
    kind: "attack" | "spell";
    summary: string;
    detail: string;
    /** Heure locale du client au moment de l'action — cosmétique, jamais serveur. */
    time?: string;
  } = $props();
</script>

<li class="entry" class:spell={kind === "spell"}>
  <span class="entry-kind" aria-hidden="true">
    <Icon name={kind === "attack" ? "sword" : "sparkle"} size={13} />
  </span>
  <div class="entry-body">
    <div class="entry-top">
      <p class="entry-summary">{summary}</p>
      {#if time}
        <span class="entry-time mono">{time}</span>
      {/if}
    </div>
    <p class="entry-detail">{detail}</p>
  </div>
</li>

<style>
  .entry {
    display: flex;
    gap: 0.55rem;
    padding: 0.5rem 0.65rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border-subtle);
    border-left: 3px solid var(--color-border-default);
    background:
      linear-gradient(rgb(255 255 255 / 0.012), transparent),
      var(--color-bg-panel);
    font-size: 0.85rem;
  }

  .entry.spell {
    border-left-color: var(--color-accent);
  }

  .entry-kind {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-subtle);
  }

  .entry.spell .entry-kind {
    color: var(--color-accent);
  }

  .entry-body {
    min-width: 0;
    flex: 1;
  }

  .entry-top {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .entry-summary {
    margin: 0;
    flex: 1;
    min-width: 0;
    font-weight: 500;
  }

  .entry-time {
    flex-shrink: 0;
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .entry-detail {
    margin: 0.18rem 0 0;
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--color-text-muted);
  }
</style>
