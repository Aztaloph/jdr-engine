<script lang="ts">
  import Icon from "./Icon.svelte";

  /** Barre d'outils inférieure — interface visuelle uniquement, jets manuels non branchés. */
  const DICE = ["d4", "d6", "d8", "d10", "d12", "d20"] as const;
</script>

<footer class="dice-bar" aria-label="Outils de table — bassin de dés en développement">
  <div class="bar-group pool">
    <span class="group-label">
      <Icon name="dice" size={13} />
      Bassin de dés
    </span>
    <div class="dice-buttons">
      {#each DICE as die (die)}
        <button type="button" class="die" disabled title="Jets manuels — à venir">
          <span class="die-shape" aria-hidden="true"></span>
          <span class="die-name">{die}</span>
        </button>
      {/each}
    </div>
    <span class="soon-tag">À venir</span>
  </div>

  <div class="bar-sep" aria-hidden="true"></div>

  <div class="bar-group history">
    <span class="group-label">
      <Icon name="scroll" size={13} />
      Historique des jets
    </span>
    <span class="history-empty">Les jets manuels apparaîtront ici.</span>
  </div>

  <div class="bar-sep" aria-hidden="true"></div>

  <div class="bar-group tools">
    <button type="button" class="tool" disabled title="Vision — à venir">
      <Icon name="eye" size={13} />
    </button>
    <button type="button" class="tool" disabled title="Grille — à venir">
      <Icon name="grid" size={13} />
    </button>
  </div>
</footer>

<style>
  .dice-bar {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    flex-wrap: wrap;
    padding: 0.55rem 0.9rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background:
      linear-gradient(rgb(255 255 255 / 0.015), transparent 60%),
      var(--color-bg-elevated);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 6px 18px rgb(0 0 0 / 0.35);
  }

  .bar-group {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .bar-group.history {
    flex: 1;
    min-width: 200px;
  }

  .group-label {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-display);
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .group-label :global(svg) {
    color: var(--color-accent);
    opacity: 0.8;
  }

  .dice-buttons {
    display: flex;
    gap: 0.35rem;
  }

  .die {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
    padding: 0.3rem 0.45rem;
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-md);
    background:
      linear-gradient(rgb(255 255 255 / 0.02), transparent),
      var(--color-bg-panel);
    color: var(--color-text-muted);
  }

  .die:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }

  .die-shape {
    width: 14px;
    height: 14px;
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-default);
    rotate: 45deg;
    border-radius: 2px;
  }

  .die-name {
    font-family: var(--font-mono);
    font-size: 0.66rem;
  }

  .soon-tag {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.4);
    background: rgb(245 158 11 / 0.07);
    border-radius: 999px;
    padding: 0.12rem 0.45rem;
    white-space: nowrap;
  }

  .bar-sep {
    align-self: stretch;
    width: 1px;
    background: var(--color-border-subtle);
  }

  .history-empty {
    font-size: 0.74rem;
    font-style: italic;
    color: var(--color-text-muted);
    opacity: 0.8;
  }

  .tool {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-md);
    background: var(--color-bg-panel);
    color: var(--color-text-muted);
  }

  .tool:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }

  @media (max-width: 900px) {
    .bar-sep {
      display: none;
    }

    .bar-group.history {
      order: 3;
      width: 100%;
    }
  }
</style>
