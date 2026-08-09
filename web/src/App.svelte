<script lang="ts">
  import {
    advanceCombatTurn,
    fetchCombatState,
    isLoadError,
  } from "./lib/api/combat";
  import type { CombatState, LoadError } from "./lib/types/combat";

  let combatId = $state("");
  let viewer = $state("");
  let combat = $state<CombatState | null>(null);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);

  const canAdvance = $derived(
    combat !== null && combat.status === "active" && !loading,
  );

  function formatBudget(
    budget: NonNullable<
      CombatState["combatants"][string]["action_budget"]
    >,
  ): string {
    const parts: string[] = [];
    if (budget.has_action) parts.push("action");
    if (budget.has_bonus_action) parts.push("bonus");
    if (budget.has_reaction) parts.push("réaction");
    if (budget.has_movement) parts.push("mouvement");
    return parts.length ? parts.join(", ") : "aucune";
  }

  async function reload() {
    error = null;
    loading = true;
    try {
      combat = await fetchCombatState(combatId, viewer);
    } catch (e) {
      combat = null;
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function advanceTurn() {
    if (!canAdvance) {
      return;
    }
    error = null;
    loading = true;
    try {
      combat = await advanceCombatTurn(combatId, viewer);
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }
</script>

<h1>Combat — banc de test API</h1>
<p class="hint">
  Proxy Vite vers <code>http://127.0.0.1:8000</code>. L'API doit tourner avant
  de recharger.
</p>

<fieldset>
  <legend>Connexion</legend>
  <label>
    combat_id
    <input type="text" bind:value={combatId} placeholder="ex. 1" autocomplete="off" />
  </label>
  <label>
    viewer (character_id, vide = MJ)
    <input
      type="text"
      bind:value={viewer}
      placeholder="ex. e2e_alice"
      autocomplete="off"
    />
  </label>
</fieldset>

<div class="actions">
  <button type="button" onclick={reload} disabled={loading || !combatId.trim()}>
    {loading ? "Chargement…" : "Recharger"}
  </button>
  <button type="button" onclick={advanceTurn} disabled={!canAdvance}>
    Tour suivant
  </button>
</div>

{#if error}
  <div class="error-box" role="alert">
    {#if error.kind === "api"}
      <strong>{error.code} (HTTP {error.status})</strong>
      <span>{error.message}</span>
      {#if error.code === "VIEWER_NOT_IN_COMBAT"}
        <span class="hint">
          Le combat peut exister — le character_id saisi ne participe pas à cette
          rencontre. Vérifiez viewer ou laissez vide pour la vue MJ.
        </span>
      {:else if error.code === "COMBAT_NOT_FOUND"}
        <span class="hint">Aucune rencontre pour ce combat_id.</span>
      {/if}
    {:else}
      <strong>Réseau</strong>
      <span>{error.message}</span>
    {/if}
  </div>
{/if}

{#if combat}
  {@const currentId = combat.current_combatant_id}
  <section aria-live="polite">
    <dl class="meta">
      <div>
        <dt>status</dt>
        <dd>{combat.status}</dd>
      </div>
      <div>
        <dt>round</dt>
        <dd>{combat.round_number}</dd>
      </div>
      <div>
        <dt>turn_index</dt>
        <dd>{combat.turn_index}</dd>
      </div>
    </dl>

    <h2>Ordre d'initiative</h2>
    {#if combat.initiative_order.length === 0}
      <p class="hint">Ordre vide (combat non activé ?).</p>
    {:else}
      <ol class="initiative-list">
        {#each combat.initiative_order as cid (cid)}
          {@const c = combat.combatants[cid]}
          <li
            class:current={cid === currentId}
            class:inactive={c && !c.is_active}
          >
            {#if c}
              <div class="combatant-name">
                {c.display_name}
                {#if cid === currentId}
                  <span aria-label="tour courant"> → tour</span>
                {/if}
              </div>
              <div class="combatant-meta">
                <span>init {c.initiative_total ?? "—"}</span>
                <span>{c.is_active ? "actif" : "inactif"}</span>
                {#if c.hp_current !== undefined}
                  <span>PV {c.hp_current}{c.hp_max !== undefined ? `/${c.hp_max}` : ""}</span>
                {/if}
                {#if c.ac !== undefined}
                  <span>CA {c.ac}</span>
                {/if}
                {#if c.action_budget}
                  <span>Budget : {formatBudget(c.action_budget)}</span>
                {/if}
                {#if c.concentration_spell_name}
                  <span>Conc. {c.concentration_spell_name}</span>
                {/if}
              </div>
            {:else}
              <div class="combatant-name">{cid}</div>
              <p class="hint">Combattant absent de la map combatants.</p>
            {/if}
          </li>
        {/each}
      </ol>
    {/if}

    {#if combat.active_effects.length > 0}
      <section class="effects">
        <h2>Effets actifs</h2>
        <ul>
          {#each combat.active_effects as effect (effect.effect_id + effect.target_id + effect.applied_at_round)}
            <li>
              {effect.effect_id} — cible {effect.target_id}, source {effect.source_id},
              round {effect.applied_at_round}
              {#if effect.duration_rounds !== undefined}
                , durée {effect.duration_rounds} ({effect.expiry_mode})
              {:else}
                ({effect.expiry_mode})
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  </section>
{/if}
