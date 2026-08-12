<script lang="ts">
  import { link } from "svelte-spa-router";
  import type { ActiveEffect, Combatant } from "../../types/combat";
  import CharacterPortrait from "./CharacterPortrait.svelte";
  import Icon from "./Icon.svelte";
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
  {#if isTurn}
    <span class="turn-ribbon">Tour actif</span>
  {/if}

  <div class="card-row">
    <CharacterPortrait name={combatant.display_name} size={46} active={isTurn} />
    <div class="card-id">
      <strong class="card-name">{combatant.display_name}</strong>
      <span class="card-sub">
        {#if combatant.initiative_total !== undefined}
          <span class="sub-item" title="Initiative">
            <Icon name="flag" size={11} />
            {combatant.initiative_total}
          </span>
        {/if}
        {#if !combatant.is_active}
          <span class="sub-item down">Hors combat</span>
        {/if}
      </span>
    </div>
    {#if combatant.ac !== undefined}
      <span class="ac-chip" title="Classe d'armure">
        <Icon name="shield" size={12} />
        {combatant.ac}
      </span>
    {/if}
  </div>

  {#if combatant.hp_current !== undefined}
    <div class="hp-block">
      <div class="hp-line">
        <span class="hp-label">PV</span>
        <span class="hp-value mono">
          {combatant.hp_current}{combatant.hp_max !== undefined ? ` / ${combatant.hp_max}` : ""}
        </span>
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
    </div>
  {/if}

  {#if combatant.concentration_spell_name || effects.length > 0}
    <div class="card-tags">
      {#if combatant.concentration_spell_name}
        <StatusBadge label="⟡ {combatant.concentration_spell_name}" variant="accent" />
      {/if}
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
    >
      <Icon name="user" size={11} />
      Fiche de personnage
    </a>
  {/if}
</article>

<style>
  .card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background:
      linear-gradient(rgb(255 255 255 / 0.015), transparent 55%),
      var(--color-bg-panel);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.02);
  }

  .card.is-turn {
    border-color: rgb(245 158 11 / 0.55);
    background:
      linear-gradient(135deg, rgb(245 158 11 / 0.1), transparent 45%),
      var(--color-bg-panel);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 0 18px rgb(245 158 11 / 0.08);
  }

  .card.is-inactive {
    opacity: 0.5;
    filter: saturate(0.4);
  }

  .turn-ribbon {
    position: absolute;
    top: -1px;
    right: 0.7rem;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #0c0a09;
    background: var(--color-accent);
    padding: 0.14rem 0.5rem;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  }

  .card-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .card-id {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .card-name {
    font-family: var(--font-display);
    font-size: 0.95rem;
    letter-spacing: 0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-sub {
    display: flex;
    gap: 0.55rem;
    font-size: 0.72rem;
    color: var(--color-text-muted);
  }

  .sub-item {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }

  .sub-item.down {
    color: var(--color-danger);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 0.62rem;
  }

  .ac-chip {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--color-text-secondary);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-sm);
    padding: 0.15rem 0.4rem;
  }

  .hp-block {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .hp-line {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .hp-label {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .hp-value {
    font-size: 0.82rem;
    color: var(--color-text-secondary);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .hp-bar {
    height: 7px;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.55);
    border: 1px solid var(--color-border-subtle);
    overflow: hidden;
  }

  .hp-fill {
    height: 100%;
    background: linear-gradient(90deg, #16a34a, #4ade80);
    border-radius: inherit;
    box-shadow: 0 0 6px rgb(74 222 128 / 0.35);
    transition: width 0.25s ease;
  }

  .hp-fill.low {
    background: linear-gradient(90deg, #b91c1c, #ef4444);
    box-shadow: 0 0 6px rgb(239 68 68 / 0.4);
  }

  .card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .sheet-link {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    text-decoration: none;
    border-bottom: 1px dotted var(--color-border-default);
    padding-bottom: 0.05rem;
  }

  .sheet-link:hover {
    color: var(--color-accent);
    border-bottom-color: var(--color-accent);
  }
</style>
