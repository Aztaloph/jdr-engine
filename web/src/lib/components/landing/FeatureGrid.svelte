<script lang="ts">
  import { reveal } from "../../actions/reveal";

  const FEATURES = [
    {
      title: "Moteur de règles SRD 5.1",
      text: "Classes, sorts, progression, repos : les règles vivent dans un compendium validé, pas dans des if épars. Les stats sont dérivées, jamais improvisées.",
      soon: false,
    },
    {
      title: "Combat structuré",
      text: "Initiative figée, budgets d'action, attaques d'arme résolues jet + dégâts en une requête, sorts avec concentration et effets suivis round par round.",
      soon: false,
    },
    {
      title: "API-first par nature",
      text: "Chaque fiche, chaque rencontre, chaque action passe par l'API REST v1. Le web n'est qu'un client parmi d'autres possibles.",
      soon: false,
    },
    {
      title: "Carte tactique en direct",
      text: "Plans partagés, jetons, vision par joueur et mise à jour temps réel : la table virtuelle arrive dans un prochain lot.",
      soon: true,
    },
    {
      title: "Sessions multi-joueurs",
      text: "Chaque joueur verra la partie à travers les yeux de son personnage — le MJ garde la vue d'ensemble. Les fondations « viewer » sont déjà dans l'API.",
      soon: true,
    },
    {
      title: "Auto-hébergeable",
      text: "Le moteur et les fonctionnalités de jeu sont gratuits et auto-hébergeables. Votre table, vos données, votre serveur.",
      soon: false,
    },
  ] as const;
</script>

<section class="features" id="fonctionnalites">
  <div class="section-inner">
    <p class="kicker">Arsenal du maître de jeu</p>
    <h2 class="section-title">Conçu pour la précision, forgé pour l'immersion</h2>
    <div class="grid">
      {#each FEATURES as feature, i (feature.title)}
        <article class="card" use:reveal={{ delay: (i % 3) * 80 }}>
          <span class="card-mark" aria-hidden="true"></span>
          <div class="card-head">
            <h3 class="card-title">{feature.title}</h3>
            {#if feature.soon}
              <span class="soon">À venir</span>
            {/if}
          </div>
          <p class="card-text">{feature.text}</p>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .features {
    padding: clamp(3.5rem, 8vw, 6rem) var(--space-lg);
    background:
      radial-gradient(45% 55% at 15% 10%, rgb(245 158 11 / 0.04), transparent 60%),
      var(--color-bg-base);
    border-top: 1px solid var(--color-border-subtle);
  }

  .section-inner {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    text-align: center;
  }

  .kicker {
    margin: 0 0 0.5rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--color-accent);
  }

  .section-title {
    margin: 0 0 clamp(2rem, 5vw, 3rem);
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 3.2vw, 2.2rem);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--space-lg);
    text-align: left;
  }

  .card {
    position: relative;
    padding: var(--space-xl) var(--space-lg);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    transition: border-color 0.2s ease, transform 0.2s ease;
  }

  .card:hover {
    border-color: rgb(245 158 11 / 0.45);
    transform: translateY(-2px);
  }

  .card-mark {
    display: block;
    width: 0.7rem;
    height: 0.7rem;
    border: 1.5px solid var(--color-accent);
    transform: rotate(45deg);
    margin-bottom: var(--space-md);
  }

  .card-head {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: var(--space-sm);
  }

  .card-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.05rem;
    color: var(--color-text-primary);
  }

  .soon {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.4);
    border-radius: 999px;
    padding: 0.08rem 0.45rem;
  }

  .card-text {
    margin: 0;
    font-size: 0.9rem;
    line-height: 1.6;
    color: var(--color-text-muted);
  }
</style>
