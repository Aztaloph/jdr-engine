<script lang="ts">
  import { link } from "svelte-spa-router";
  import { reveal } from "../../actions/reveal";
</script>

<section class="final">
  <div class="final-inner" use:reveal>
    <h2 class="final-title">Forgez votre propre univers de jeu</h2>
    <p class="final-text">
      Rejoignez le développement de JDR Engine : lancez une rencontre sur le
      banc de jeu, ou déployez le moteur sur votre propre serveur.
    </p>
    <div class="cta-row">
      <a href="/lobby" use:link class="cta-primary">Commencer gratuitement</a>
    </div>
  </div>
</section>

<style>
  .final {
    position: relative;
    overflow: hidden;
    padding: clamp(4rem, 9vw, 7rem) var(--space-lg);
    background:
      radial-gradient(50% 70% at 50% 100%, rgb(245 158 11 / 0.1), transparent 70%),
      linear-gradient(rgb(255 255 255 / 0.014) 1px, transparent 1px),
      linear-gradient(90deg, rgb(255 255 255 / 0.014) 1px, transparent 1px),
      var(--color-bg-base);
    background-size: auto, 48px 48px, 48px 48px, auto;
    border-top: 1px solid var(--color-border-subtle);
    text-align: center;
  }

  .final-inner {
    max-width: 40rem;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-lg);
  }

  .final-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.7rem, 4vw, 2.6rem);
    font-weight: 700;
    color: var(--color-text-primary);
    text-shadow: 0 0 60px rgb(245 158 11 / 0.2);
  }

  .final-text {
    margin: 0;
    font-size: 0.98rem;
    line-height: 1.65;
    color: var(--color-text-muted);
  }

  .cta-row {
    display: flex;
    gap: var(--space-md);
    flex-wrap: wrap;
    justify-content: center;
  }

  .cta-primary {
    text-decoration: none;
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--color-accent-text);
    background: var(--color-accent);
    border: 1px solid var(--color-accent);
    border-radius: var(--radius-md);
    padding: 0.7rem 1.5rem;
    box-shadow: var(--glow-accent);
    transition: background 0.15s ease, transform 0.15s ease;
  }

  .cta-primary:hover {
    background: var(--color-accent-hover);
    border-color: var(--color-accent-hover);
    transform: translateY(-1px);
  }
</style>
