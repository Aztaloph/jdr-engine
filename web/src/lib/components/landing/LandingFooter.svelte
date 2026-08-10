<script lang="ts">
  import { link } from "svelte-spa-router";
</script>

<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <span class="brand">
        <span class="brand-mark" aria-hidden="true"></span>
        JDR Engine
      </span>
      <p class="tagline">
        Le moteur open des aventures de jeu de rôle — règles SRD 5.1,
        combat structuré, API-first.
      </p>
    </div>
    <div class="footer-cols">
      <div class="footer-col">
        <h3>Produit</h3>
        <ul>
          <li><a href="/lobby" use:link>Banc de jeu</a></li>
          <li><a href="/lobby" use:link>Fiches de personnage</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h3>Ressources</h3>
        <ul>
          <li><span class="soon-item">Documentation API <span class="soon">à venir</span></span></li>
          <li><span class="soon-item">Guide du MJ <span class="soon">à venir</span></span></li>
        </ul>
      </div>
      <div class="footer-col">
        <h3>Projet</h3>
        <ul>
          <li><span class="soon-item">Feuille de route <span class="soon">à venir</span></span></li>
          <li><span class="soon-item">Communauté <span class="soon">à venir</span></span></li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footer-legal">
    <p>
      © 2026 JDR Engine — règles issues du SRD 5.1 (Creative Commons BY 4.0).
      Produit en développement actif.
    </p>
  </div>
</footer>

<style>
  .footer {
    background: var(--color-bg-elevated);
    border-top: 1px solid var(--color-border-subtle);
  }

  .footer-inner {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    padding: clamp(2.5rem, 6vw, 4rem) var(--space-lg);
    display: grid;
    grid-template-columns: minmax(240px, 1.2fr) 2fr;
    gap: clamp(2rem, 5vw, 4rem);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: 0.04em;
    color: var(--color-text-primary);
  }

  .brand-mark {
    width: 0.8rem;
    height: 0.8rem;
    border: 1.5px solid var(--color-accent);
    transform: rotate(45deg);
    display: inline-block;
  }

  .tagline {
    margin: var(--space-md) 0 0;
    font-size: 0.85rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    max-width: 22rem;
  }

  .footer-cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: var(--space-lg);
  }

  .footer-col h3 {
    margin: 0 0 var(--space-md);
    font-family: var(--font-body);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .footer-col ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    font-size: 0.88rem;
  }

  .footer-col a {
    color: var(--color-text-primary);
    text-decoration: none;
  }

  .footer-col a:hover {
    color: var(--color-accent);
  }

  .soon-item {
    color: var(--color-text-muted);
  }

  .soon {
    font-size: 0.6rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.4);
    border-radius: 999px;
    padding: 0.05rem 0.4rem;
    margin-left: 0.3rem;
  }

  .footer-legal {
    border-top: 1px solid var(--color-border-subtle);
  }

  .footer-legal p {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    padding: var(--space-lg);
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  @media (max-width: 800px) {
    .footer-inner {
      grid-template-columns: 1fr;
    }
  }
</style>
