<script lang="ts">
  import { reveal } from "../../actions/reveal";

  const REQUEST = `POST /v1/combats/42/attack
{
  "attacker_id": "85dd281c",
  "target_id":   "488acff2",
  "weapon_id":   "longsword"
}`;

  const RESPONSE = `{
  "attack": {
    "d20":     { "total": 19, "natural_20": false },
    "outcome": { "hit": true, "target_ac": 13 }
  },
  "damage": { "total": 7, "hp_before": 16, "hp_after": 9 },
  "target": { "combatant_id": "488acff2", "hp_current": 9 }
}`;
</script>

<section class="api" id="api">
  <div class="section-inner">
    <div class="api-copy" use:reveal>
      <p class="kicker">Interface développeur</p>
      <h2 class="section-title">Un appel API, un destin forgé</h2>
      <p class="api-text">
        Déclarez une attaque, le moteur fait le reste : jet, modificateurs
        dérivés de la fiche, dégâts et points de vie — résolus côté serveur,
        renvoyés en JSON structuré. Aucune règle ne vit dans le client.
      </p>
      <ul class="api-points">
        <li>Réponses JSON stables, identifiants pérennes</li>
        <li>Résolution déterministe côté moteur — pas de triche possible</li>
        <li>Auto-hébergeable, votre serveur, vos données</li>
      </ul>
    </div>
    <figure class="code-window" use:reveal={{ delay: 120 }}>
      <figcaption class="code-bar">
        <span class="dot" aria-hidden="true"></span>
        <span class="dot" aria-hidden="true"></span>
        <span class="dot" aria-hidden="true"></span>
        <span class="code-title">jdr-engine — API v1</span>
      </figcaption>
      <pre class="code-body"><code
          ><span class="c-comment"># Attaque d'arme — extrait représentatif</span>
{REQUEST}

<span class="c-comment"># 200 OK</span>
{RESPONSE}</code></pre>
    </figure>
  </div>
</section>

<style>
  .api {
    padding: clamp(3.5rem, 8vw, 6rem) var(--space-lg);
    background: var(--color-bg-base);
    border-top: 1px solid var(--color-border-subtle);
  }

  .section-inner {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    display: grid;
    grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.15fr);
    gap: clamp(2rem, 5vw, 4rem);
    align-items: center;
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
    margin: 0 0 var(--space-lg);
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 3.2vw, 2.2rem);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .api-text {
    margin: 0 0 var(--space-lg);
    font-size: 0.95rem;
    line-height: 1.65;
    color: var(--color-text-muted);
  }

  .api-points {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .api-points li {
    position: relative;
    padding-left: 1.3rem;
    font-size: 0.9rem;
    color: var(--color-text-primary);
  }

  .api-points li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.42em;
    width: 0.5rem;
    height: 0.5rem;
    border: 1.5px solid var(--color-accent);
    transform: rotate(45deg);
  }

  .code-window {
    margin: 0;
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-lg);
    background: #0d0d0d;
    box-shadow: 0 20px 60px rgb(0 0 0 / 0.5), var(--glow-accent);
    overflow: hidden;
  }

  .code-bar {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.55rem 0.9rem;
    background: var(--color-bg-panel);
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .dot {
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 50%;
    background: var(--color-border-default);
  }

  .code-title {
    margin-left: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--color-text-muted);
  }

  .code-body {
    margin: 0;
    padding: var(--space-lg);
    font-family: var(--font-mono);
    font-size: 0.78rem;
    line-height: 1.6;
    color: #d8d4c8;
    overflow-x: auto;
  }

  .c-comment {
    color: var(--color-text-muted);
  }

  @media (max-width: 900px) {
    .section-inner {
      grid-template-columns: 1fr;
    }
  }
</style>
