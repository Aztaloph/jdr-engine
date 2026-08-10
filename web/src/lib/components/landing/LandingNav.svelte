<script lang="ts">
  import { link } from "svelte-spa-router";

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
</script>

<header class="nav-wrap">
  <nav class="nav" aria-label="Navigation landing">
    <span class="brand">
      <span class="brand-mark" aria-hidden="true"></span>
      JDR Engine
    </span>
    <div class="nav-links">
      <button type="button" onclick={() => scrollTo("fonctionnement")}>Fonctionnement</button>
      <button type="button" onclick={() => scrollTo("fonctionnalites")}>Fonctionnalités</button>
      <button type="button" onclick={() => scrollTo("api")}>API</button>
    </div>
    <a href="/lobby" use:link class="nav-cta">Ouvrir l'application</a>
  </nav>
</header>

<style>
  .nav-wrap {
    position: sticky;
    top: 0;
    z-index: 20;
    background: rgb(10 10 10 / 0.82);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .nav {
    max-width: var(--landing-max-width);
    margin: 0 auto;
    padding: 0.7rem var(--space-lg);
    display: flex;
    align-items: center;
    gap: var(--space-lg);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.02rem;
    letter-spacing: 0.04em;
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .brand-mark {
    width: 0.85rem;
    height: 0.85rem;
    border: 1.5px solid var(--color-accent);
    transform: rotate(45deg);
    display: inline-block;
  }

  .nav-links {
    display: flex;
    gap: 0.25rem;
    margin-left: auto;
  }

  .nav-links button {
    border: none;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.88rem;
    padding: 0.35rem 0.7rem;
    border-radius: var(--radius-sm);
  }

  .nav-links button:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-elevated);
  }

  .nav-cta {
    flex-shrink: 0;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-accent-text);
    background: var(--color-accent);
    border: 1px solid var(--color-accent);
    border-radius: var(--radius-md);
    padding: 0.45rem 0.9rem;
    transition: background 0.15s ease;
  }

  .nav-cta:hover {
    background: var(--color-accent-hover);
    border-color: var(--color-accent-hover);
  }

  @media (max-width: 720px) {
    .nav-links {
      display: none;
    }

    .nav-cta {
      margin-left: auto;
    }
  }
</style>
