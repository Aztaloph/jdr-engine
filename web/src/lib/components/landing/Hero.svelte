<script lang="ts">
  import { link } from "svelte-spa-router";

  function scrollToApi() {
    document.getElementById("api")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
</script>

<section class="hero">
  <div class="hero-inner">
    <p class="eyebrow">
      <span class="eyebrow-dot" aria-hidden="true"></span>
      API v1 — en développement actif
    </p>
    <h1 class="title">
      Le moteur de vos aventures<br />de jeu de rôle
    </h1>
    <p class="subtitle">
      JDR Engine orchestre les règles du SRD 5.1 — fiches, combats, sorts,
      concentration — et les expose via une API claire. Une seule source de
      vérité pour vos parties, du premier jet de dés au dernier round.
    </p>
    <div class="cta-row">
      <a href="/lobby" use:link class="cta-primary">Lancer une session</a>
      <button type="button" class="cta-secondary" onclick={scrollToApi}>
        Explorer l'API
      </button>
    </div>
  </div>
</section>

<style>
  .hero {
    position: relative;
    overflow: hidden;
    padding: clamp(4rem, 10vw, 8rem) var(--space-lg) clamp(4rem, 9vw, 7rem);
    background:
      radial-gradient(55% 60% at 50% 0%, rgb(245 158 11 / 0.11), transparent 70%),
      radial-gradient(35% 45% at 82% 25%, rgb(245 158 11 / 0.05), transparent 65%),
      linear-gradient(rgb(255 255 255 / 0.016) 1px, transparent 1px),
      linear-gradient(90deg, rgb(255 255 255 / 0.016) 1px, transparent 1px),
      var(--color-bg-base);
    background-size: auto, auto, 48px 48px, 48px 48px, auto;
  }

  .hero::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: radial-gradient(120% 90% at 50% 30%, transparent 55%, rgb(0 0 0 / 0.55));
  }

  .hero-inner {
    position: relative;
    z-index: 1;
    max-width: 46rem;
    margin: 0 auto;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-lg);
  }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.35);
    border-radius: 999px;
    padding: 0.3rem 0.85rem;
    background: rgb(245 158 11 / 0.06);
  }

  .eyebrow-dot {
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: var(--color-accent);
  }

  .title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(2.1rem, 5.4vw, 3.6rem);
    font-weight: 700;
    line-height: 1.12;
    letter-spacing: 0.005em;
    color: var(--color-text-primary);
    text-shadow: 0 0 80px rgb(245 158 11 / 0.22);
  }

  .subtitle {
    margin: 0;
    max-width: 38rem;
    font-size: clamp(0.98rem, 1.6vw, 1.1rem);
    line-height: 1.65;
    color: var(--color-text-muted);
  }

  .cta-row {
    display: flex;
    gap: var(--space-md);
    flex-wrap: wrap;
    justify-content: center;
    margin-top: var(--space-sm);
  }

  .cta-primary {
    text-decoration: none;
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--color-accent-text);
    background: var(--color-accent);
    border: 1px solid var(--color-accent);
    border-radius: var(--radius-md);
    padding: 0.7rem 1.4rem;
    box-shadow: var(--glow-accent);
    transition: background 0.15s ease, transform 0.15s ease;
  }

  .cta-primary:hover {
    background: var(--color-accent-hover);
    border-color: var(--color-accent-hover);
    transform: translateY(-1px);
  }

  .cta-secondary {
    font-size: 0.95rem;
    font-weight: 500;
    padding: 0.7rem 1.4rem;
    border-radius: var(--radius-md);
  }
</style>
