<section class="map-panel" aria-label="Carte tactique (en développement)">
  <header class="map-head">
    <span class="map-title">Plan de la rencontre</span>
    <span class="map-dev-badge">En développement</span>
  </header>
  <div class="map-body">
    <div class="map-center">
      <span class="map-rune" aria-hidden="true"></span>
      <p class="map-name">Carte tactique</p>
      <p class="map-state">EN DÉVELOPPEMENT</p>
      <p class="map-hint">
        Grille, jetons et déplacements sont prévus dans un lot ultérieur
        (moteur de mouvement + temps réel).
      </p>
    </div>
  </div>
</section>

<style>
  .map-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 460px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  .map-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.9rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: var(--color-bg-panel);
  }

  .map-title {
    font-family: var(--font-display);
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .map-dev-badge {
    margin-left: auto;
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid var(--color-accent);
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
  }

  .map-body {
    flex: 1;
    display: grid;
    place-items: center;
    padding: var(--space-lg);
    background:
      radial-gradient(ellipse at center, rgb(245 158 11 / 0.04), transparent 65%),
      var(--color-bg-base);
  }

  .map-center {
    text-align: center;
    max-width: 26rem;
    padding: var(--space-xl);
    border: 2px dashed var(--color-border-default);
    border-radius: var(--radius-lg);
  }

  .map-rune {
    display: block;
    width: 3.5rem;
    height: 3.5rem;
    margin: 0 auto var(--space-md);
    border: 2px solid var(--color-border-default);
    border-radius: 50%;
    background:
      linear-gradient(45deg, transparent 46%, var(--color-border-default) 46%, var(--color-border-default) 54%, transparent 54%),
      linear-gradient(-45deg, transparent 46%, var(--color-border-default) 46%, var(--color-border-default) 54%, transparent 54%);
  }

  .map-name {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .map-state {
    margin: 0.25rem 0 0.6rem;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    color: var(--color-accent);
  }

  .map-hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--color-text-muted);
  }
</style>
