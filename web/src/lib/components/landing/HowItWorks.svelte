<script lang="ts">
  import { reveal } from "../../actions/reveal";

  const STEPS = [
    {
      num: "01",
      title: "Forgez vos héros",
      text: "Créez des fiches complètes — caractéristiques, sauvegardes, compétences, sorts — dérivées des règles, jamais saisies au hasard.",
    },
    {
      num: "02",
      title: "Préparez la rencontre",
      text: "Assemblez le groupe dans le lobby, lancez l'initiative : le moteur fige l'ordre du tour et arbitre chaque budget d'action.",
    },
    {
      num: "03",
      title: "Jouez en direct",
      text: "Attaques, sorts, concentration : chaque action est résolue côté moteur et l'état de la rencontre reste la seule vérité.",
    },
  ] as const;
</script>

<section class="how" id="fonctionnement">
  <div class="section-inner">
    <p class="kicker">Protocole de jeu</p>
    <h2 class="section-title">Comment fonctionne JDR Engine</h2>
    <div class="steps">
      {#each STEPS as step, i (step.num)}
        <article class="step" use:reveal={{ delay: i * 90 }}>
          <span class="step-num">{step.num}</span>
          <h3 class="step-title">{step.title}</h3>
          <p class="step-text">{step.text}</p>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .how {
    padding: clamp(3.5rem, 8vw, 6rem) var(--space-lg);
    background: var(--color-bg-base);
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

  .steps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: var(--space-lg);
    text-align: left;
  }

  .step {
    padding: var(--space-xl) var(--space-lg);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    transition: border-color 0.2s ease, transform 0.2s ease;
  }

  .step:hover {
    border-color: rgb(245 158 11 / 0.45);
    transform: translateY(-2px);
  }

  .step-num {
    display: block;
    font-family: var(--font-display);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--color-accent);
    margin-bottom: var(--space-md);
  }

  .step-title {
    margin: 0 0 var(--space-sm);
    font-family: var(--font-display);
    font-size: 1.08rem;
    color: var(--color-text-primary);
  }

  .step-text {
    margin: 0;
    font-size: 0.9rem;
    line-height: 1.6;
    color: var(--color-text-muted);
  }
</style>
