<script lang="ts">
  import { link } from "svelte-spa-router";
  import type { ActiveEffect, Combatant } from "../../types/combat";
  import StatusBadge from "./StatusBadge.svelte";

  let {
    combatant,
    isTurn = false,
    effects = [],
  }: {
    combatant: Combatant;
    isTurn?: boolean;
    effects?: ActiveEffect[];
  } = $props();

  const initials = $derived(
    combatant.display_name
      .split(/\s+/)
      .map((word) => word[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase(),
  );

  /** Ratio PV — uniquement si le serveur expose courant ET max (visibilité viewer). */
  const hpRatio = $derived(
    combatant.hp_current !== undefined &&
      combatant.hp_max !== undefined &&
      combatant.hp_max > 0
      ? Math.max(0, Math.min(1, combatant.hp_current / combatant.hp_max))
      : null,
  );
</script>

<article class="card" class:is-turn={isTurn} class:is-inactive={!combatant.is_active}>
  <span class="avatar" aria-hidden="true" title="Avatar — à venir">{initials}</span>
  <div class="card-main">
    <div class="card-head">
      <strong class="card-name">{combatant.display_name}</strong>
      {#if combatant.ac !== undefined}
        <span class="ac-chip">CA {combatant.ac}</span>
      {/if}
    </div>
    {#if isTurn}
      <div class="turn-row"><StatusBadge label="Tour" variant="accent" /></div>
    {/if}
    {#if combatant.hp_current !== undefined}
      <div class="hp-text">
        PV {combatant.hp_current}{combatant.hp_max !== undefined ? ` / ${combatant.hp_max}` : ""}
      </div>
      {#if hpRatio !== null}
        <div class="hp-bar">
          <div
            class="hp-fill"
            class:low={hpRatio <= 0.35}
            style="width: {Math.round(hpRatio * 100)}%"
          ></div>
        </div>
      {/if}
    {/if}
    {#if combatant.concentration_spell_name}
      <p class="conc">Concentration : {combatant.concentration_spell_name}</p>
    {/if}
    {#if effects.length > 0}
      <div class="effect-badges">
        {#each effects as effect (effect.effect_id + effect.source_id + effect.applied_at_round)}
          <StatusBadge label={effect.effect_id} variant="success" />
        {/each}
      </div>
    {/if}
    {#if combatant.character_id}
      <a
        href="/character/{encodeURIComponent(combatant.character_id)}"
        use:link
        class="sheet-link"
      >fiche</a>
    {/if}
  </div>
</article>

<style>
  .card {
    display: flex;
    gap: 0.65rem;
    align-items: flex-start;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-panel);
  }

  .card.is-turn {
    border-color: var(--color-accent);
    background: var(--color-accent-muted);
  }

  .card.is-inactive {
    opacity: 0.55;
  }

  .avatar {
    flex-shrink: 0;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 0.9rem;
    color: var(--color-text-muted);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-default);
  }

  .card.is-turn .avatar {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .card-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .card-head {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .card-name {
    font-size: 0.95rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ac-chip {
    margin-left: auto;
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-sm);
    padding: 0.05rem 0.35rem;
  }

  .turn-row {
    line-height: 1;
  }

  .hp-text {
    font-size: 0.85rem;
  }

  .hp-bar {
    height: 6px;
    border-radius: 999px;
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-subtle);
    overflow: hidden;
  }

  .hp-fill {
    height: 100%;
    background: var(--color-success);
    border-radius: inherit;
    transition: width 0.25s ease;
  }

  .hp-fill.low {
    background: var(--color-danger);
  }

  .conc {
    margin: 0;
    font-size: 0.8rem;
    color: var(--color-text-muted);
  }

  .effect-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .sheet-link {
    align-self: flex-start;
    font-size: 0.78rem;
    color: var(--color-accent);
  }

  .sheet-link:hover {
    color: var(--color-accent-hover);
  }
</style>
