<script lang="ts">
  let {
    kind,
    summary,
    detail,
  }: {
    kind: "attack" | "spell";
    summary: string;
    detail: string;
  } = $props();
</script>

<li class="entry" class:spell={kind === "spell"}>
  <span class="entry-kind" aria-hidden="true">{kind === "attack" ? "⚔" : "✨"}</span>
  <div class="entry-body">
    <p class="entry-summary">{summary}</p>
    <p class="entry-detail">{detail}</p>
  </div>
</li>

<style>
  .entry {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 0.6rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border-subtle);
    border-left: 3px solid var(--color-border-default);
    background: var(--color-bg-panel);
    font-size: 0.88rem;
  }

  .entry.spell {
    border-left-color: var(--color-accent);
  }

  .entry-kind {
    flex-shrink: 0;
    width: 1.25rem;
    text-align: center;
  }

  .entry-body {
    min-width: 0;
  }

  .entry-summary {
    margin: 0;
  }

  .entry-detail {
    margin: 0.15rem 0 0;
    font-size: 0.8rem;
    color: var(--color-text-muted);
  }
</style>
