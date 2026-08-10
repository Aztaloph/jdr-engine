<script lang="ts">
  import { reveal } from "../../actions/reveal";

  /** Chiffres réels du dépôt — pas de social proof inventée. */
  const STATS = [
    { value: "SRD 5.1", label: "Règles implémentées" },
    { value: "945+", label: "Tests automatisés du moteur" },
    { value: "v1", label: "API REST versionnée" },
    { value: "100 %", label: "Gratuit et auto-hébergeable" },
  ] as const;
</script>

<section class="stats">
  <div class="section-inner" use:reveal>
    {#each STATS as stat (stat.label)}
      <div class="stat">
        <span class="stat-value">{stat.value}</span>
        <span class="stat-label">{stat.label}</span>
      </div>
    {/each}
  </div>
</section>

<style>
  .stats {
    padding: clamp(2.5rem, 6vw, 4rem) var(--space-lg);
    background: var(--color-bg-elevated);
    border-top: 1px solid var(--color-border-subtle);
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .section-inner {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-lg);
    text-align: center;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .stat-value {
    font-family: var(--font-display);
    font-size: clamp(1.6rem, 3.5vw, 2.4rem);
    font-weight: 700;
    color: var(--color-accent);
  }

  .stat-label {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
</style>
