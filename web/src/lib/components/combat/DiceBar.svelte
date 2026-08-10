<script lang="ts">
  const DICE = ["d4", "d6", "d8", "d10", "d12", "d20"] as const;
</script>

<footer class="dice-bar" aria-label="Bassin de dés (en développement)">
  <span class="dice-label">Bassin de dés</span>
  <div class="dice-buttons">
    {#each DICE as die (die)}
      <button type="button" disabled title="En développement">{die}</button>
    {/each}
  </div>
  <span class="dice-dev">EN DÉVELOPPEMENT — jets manuels et historique à venir</span>
</footer>

<style>
  .dice-bar {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    flex-wrap: wrap;
    padding: 0.6rem 0.9rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .dice-label {
    font-family: var(--font-display);
    font-size: 0.9rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .dice-buttons {
    display: flex;
    gap: 0.4rem;
  }

  .dice-buttons button {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    padding: 0.35rem 0.55rem;
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-md);
    background: var(--color-bg-panel);
    color: var(--color-text-muted);
  }

  .dice-dev {
    margin-left: auto;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  @media (max-width: 800px) {
    .dice-dev {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
