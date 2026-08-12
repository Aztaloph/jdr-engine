<script lang="ts">
  import Icon from "./Icon.svelte";

  /**
   * Scène tactique — représentation purement VISUELLE et statique.
   * Aucune donnée de position réelle : les jetons ci-dessous sont décoratifs,
   * ils montrent l'apparence cible avant le branchement du moteur tactique (C4).
   * Ne jamais connecter ces positions à la logique de combat.
   */
  const DEMO_TOKENS: Array<{ x: number; y: number; side: "ally" | "enemy"; size: number }> = [
    { x: 38, y: 62, side: "ally", size: 46 },
    { x: 47, y: 71, side: "ally", size: 42 },
    { x: 30, y: 74, side: "ally", size: 40 },
    { x: 58, y: 34, side: "enemy", size: 48 },
    { x: 68, y: 44, side: "enemy", size: 40 },
  ];

  const GRID_COLS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];
</script>

<section class="map" aria-label="Carte tactique — aperçu visuel, moteur en développement">
  <header class="map-head">
    <span class="map-title">
      <Icon name="map" size={13} />
      Carte tactique
    </span>
    <div class="map-tools">
      <button type="button" class="tool" disabled title="Vision — à venir">
        <Icon name="eye" size={12} />
        Vision
      </button>
      <button type="button" class="tool" disabled title="Grille — à venir">
        <Icon name="grid" size={12} />
        Grille
      </button>
      <span class="dev-chip">En développement</span>
    </div>
  </header>

  <div class="scene" aria-hidden="true">
    <!-- Décor : pierre, grille, cercle rituel, lumière — purement CSS -->
    <div class="layer stone"></div>
    <div class="layer grid-lines"></div>

    <div class="ritual">
      <div class="ring ring-outer"></div>
      <div class="ring ring-mid"></div>
      <div class="ring ring-inner"></div>
      {#each Array.from({ length: 8 }) as _, i (i)}
        <span class="glyph" style="transform: rotate({i * 45}deg) translateY(-172px) rotate(45deg)"></span>
      {/each}
      <div class="ring-glow"></div>
    </div>

    <!-- Jetons décoratifs (aucune position réelle) -->
    {#each DEMO_TOKENS as token, i (i)}
      <span
        class="token {token.side}"
        style="left: {token.x}%; top: {token.y}%; width: {token.size}px; height: {token.size}px"
      >
        <span class="token-core"></span>
      </span>
    {/each}

    <!-- Coordonnées de grille -->
    <div class="coords coords-top">
      {#each GRID_COLS as c (c)}<span>{c}</span>{/each}
    </div>
    <div class="coords coords-left">
      {#each Array.from({ length: 8 }) as _, i (i)}<span>{i + 1}</span>{/each}
    </div>

    <div class="layer vignette"></div>
  </div>

  <footer class="map-foot">
    <span class="foot-note">Aperçu visuel — les jetons sont décoratifs, le moteur tactique arrive avec le lot C4.</span>
    <span class="foot-scale mono">1 case = 1,5 m</span>
  </footer>
</section>

<style>
  .map {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 540px;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 8px 24px rgb(0 0 0 / 0.4);
    overflow: hidden;
  }

  .map-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: linear-gradient(rgb(255 255 255 / 0.02), transparent), var(--color-bg-panel);
  }

  .map-title {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-family: var(--font-display);
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .map-title :global(svg) {
    color: var(--color-accent);
  }

  .map-tools {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .tool {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    padding: 0.22rem 0.5rem;
  }

  .tool:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .dev-chip {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.4);
    border-radius: 999px;
    padding: 0.14rem 0.5rem;
    background: rgb(245 158 11 / 0.07);
  }

  .scene {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    background: #0b0a08;
  }

  .layer {
    position: absolute;
    inset: 0;
  }

  /* Sol de pierre : nappes sombres irrégulières + lueur ambrée centrale */
  .stone {
    background:
      radial-gradient(ellipse 90% 70% at 50% 52%, rgb(245 158 11 / 0.07), transparent 62%),
      radial-gradient(ellipse 40% 30% at 22% 20%, rgb(255 255 255 / 0.02), transparent),
      radial-gradient(ellipse 35% 28% at 80% 78%, rgb(255 255 255 / 0.015), transparent),
      repeating-linear-gradient(37deg, rgb(255 255 255 / 0.008) 0 2px, transparent 2px 9px),
      repeating-linear-gradient(-52deg, rgb(0 0 0 / 0.22) 0 3px, transparent 3px 13px),
      linear-gradient(#141210, #0c0b09);
  }

  .grid-lines {
    background-image:
      linear-gradient(rgb(255 255 255 / 0.035) 1px, transparent 1px),
      linear-gradient(90deg, rgb(255 255 255 / 0.035) 1px, transparent 1px);
    background-size: 52px 52px;
    background-position: center;
    mask-image: radial-gradient(ellipse 85% 80% at 50% 50%, #000 55%, transparent 95%);
  }

  /* Cercle rituel central */
  .ritual {
    position: absolute;
    left: 50%;
    top: 52%;
    width: 0;
    height: 0;
  }

  .ring {
    position: absolute;
    left: 50%;
    top: 50%;
    translate: -50% -50%;
    border-radius: 50%;
  }

  .ring-outer {
    width: 400px;
    height: 400px;
    border: 1px solid rgb(245 158 11 / 0.22);
    box-shadow:
      0 0 32px rgb(245 158 11 / 0.06),
      inset 0 0 40px rgb(245 158 11 / 0.05);
  }

  .ring-mid {
    width: 320px;
    height: 320px;
    border: 1px dashed rgb(245 158 11 / 0.28);
  }

  .ring-inner {
    width: 190px;
    height: 190px;
    border: 1px solid rgb(245 158 11 / 0.35);
    background:
      radial-gradient(circle, rgb(245 158 11 / 0.08), transparent 70%);
  }

  .glyph {
    position: absolute;
    left: -5px;
    top: -5px;
    width: 10px;
    height: 10px;
    background: rgb(245 158 11 / 0.5);
    box-shadow: 0 0 8px rgb(245 158 11 / 0.5);
  }

  .ring-glow {
    position: absolute;
    left: 50%;
    top: 50%;
    translate: -50% -50%;
    width: 480px;
    height: 480px;
    border-radius: 50%;
    background: radial-gradient(circle, rgb(245 158 11 / 0.06), transparent 60%);
    pointer-events: none;
  }

  /* Jetons décoratifs */
  .token {
    position: absolute;
    translate: -50% -50%;
    border-radius: 50%;
    display: grid;
    place-items: center;
    box-shadow: 0 4px 12px rgb(0 0 0 / 0.6);
  }

  .token.ally {
    border: 2px solid rgb(74 222 128 / 0.8);
    box-shadow:
      0 4px 12px rgb(0 0 0 / 0.6),
      0 0 12px rgb(74 222 128 / 0.25);
  }

  .token.enemy {
    border: 2px solid rgb(239 68 68 / 0.8);
    box-shadow:
      0 4px 12px rgb(0 0 0 / 0.6),
      0 0 12px rgb(239 68 68 / 0.25);
  }

  .token-core {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background:
      radial-gradient(circle at 35% 30%, #2a2825, #131211 75%);
    box-shadow: inset 0 0 0 2px rgb(0 0 0 / 0.5);
  }

  .token-core::after {
    content: "";
    position: absolute;
    left: 50%;
    top: 50%;
    translate: -50% -50%;
    width: 8px;
    height: 8px;
    rotate: 45deg;
  }

  .token.ally .token-core::after {
    background: rgb(74 222 128 / 0.55);
  }

  .token.enemy .token-core::after {
    background: rgb(239 68 68 / 0.55);
  }

  /* Coordonnées */
  .coords {
    position: absolute;
    display: flex;
    font-family: var(--font-mono);
    font-size: 0.58rem;
    letter-spacing: 0.05em;
    color: rgb(255 255 255 / 0.18);
  }

  .coords-top {
    top: 6px;
    left: 34px;
    right: 10px;
    justify-content: space-between;
  }

  .coords-left {
    top: 26px;
    bottom: 12px;
    left: 10px;
    flex-direction: column;
    justify-content: space-between;
  }

  .vignette {
    background:
      radial-gradient(ellipse 120% 105% at 50% 48%, transparent 55%, rgb(0 0 0 / 0.55) 100%);
    pointer-events: none;
  }

  .map-foot {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.4rem 0.8rem;
    border-top: 1px solid var(--color-border-subtle);
    background: var(--color-bg-panel);
  }

  .foot-note {
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  .foot-scale {
    margin-left: auto;
    font-size: 0.66rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .mono {
    font-family: var(--font-mono);
  }
</style>
