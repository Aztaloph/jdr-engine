<script lang="ts">
  import {
    advanceCombatTurn,
    fetchCombatState,
    isLoadError,
    postWeaponAttack,
  } from "./lib/api/combat";
  import type { CombatState, LoadError } from "./lib/types/combat";
  import {
    WEAPON_IDS,
    type WeaponAttackResult,
    type WeaponId,
  } from "./lib/types/attack";

  let combatId = $state("");
  let viewer = $state("");
  let combat = $state<CombatState | null>(null);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);

  let attackerId = $state("");
  let targetId = $state("");
  let weaponId = $state<WeaponId>("longsword");
  let lastAttack = $state<WeaponAttackResult | null>(null);

  const canAdvance = $derived(
    combat !== null && combat.status === "active" && !loading,
  );

  const canAttack = $derived(
    combat !== null &&
      combat.status === "active" &&
      attackerId !== "" &&
      targetId !== "" &&
      attackerId !== targetId &&
      !loading,
  );

  const currentTurnCombatant = $derived(
    combat && combat.current_combatant_id
      ? combat.combatants[combat.current_combatant_id]
      : undefined,
  );

  function syncAttackSelectors(state: CombatState) {
    const current = state.current_combatant_id;
    if (current && state.combatants[current]) {
      attackerId = current;
    } else if (state.initiative_order.length > 0) {
      attackerId = state.initiative_order[0];
    } else {
      attackerId = "";
    }

    const others = state.initiative_order.filter((cid) => cid !== attackerId);
    if (others.length > 0) {
      targetId = others[0];
    } else {
      const keys = Object.keys(state.combatants).filter((cid) => cid !== attackerId);
      targetId = keys[0] ?? "";
    }
  }

  function combatantLabel(cid: string, state: CombatState): string {
    const c = state.combatants[cid];
    if (!c) {
      return cid;
    }
    return `${c.display_name} (${cid})`;
  }

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

  function applyCombatState(state: CombatState) {
    combat = state;
    syncAttackSelectors(state);
  }

  async function reload() {
    error = null;
    lastAttack = null;
    loading = true;
    try {
      applyCombatState(await fetchCombatState(combatId, viewer));
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
    lastAttack = null;
    loading = true;
    try {
      applyCombatState(await advanceCombatTurn(combatId, viewer));
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function launchAttack() {
    if (!canAttack) {
      return;
    }
    error = null;
    loading = true;
    try {
      lastAttack = await postWeaponAttack(combatId, {
        attacker_id: attackerId,
        target_id: targetId,
        weapon_id: weaponId,
      });
    } catch (e) {
      lastAttack = null;
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
      {:else if error.code === "NOT_COMBATANT_TURN"}
        <span class="hint">L'attaquant sélectionné n'est pas au tour courant.</span>
      {:else if error.code === "ACTION_BUDGET_EXHAUSTED"}
        <span class="hint">Le budget d'action de l'attaquant est épuisé pour ce tour.</span>
      {:else if error.code === "COMBAT_STATUS_INVALID"}
        <span class="hint">Action impossible dans le statut actuel du combat.</span>
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
      <div>
        <dt>current_combatant_id</dt>
        <dd>{currentId ?? "—"}</dd>
      </div>
    </dl>

    {#if currentTurnCombatant}
      <section class="hud-current">
        <h2>Tour courant — {currentTurnCombatant.display_name}</h2>
        <div class="combatant-meta">
          {#if currentTurnCombatant.hp_current !== undefined}
            <span>PV {currentTurnCombatant.hp_current}{currentTurnCombatant.hp_max !== undefined ? `/${currentTurnCombatant.hp_max}` : ""}</span>
          {/if}
          {#if currentTurnCombatant.ac !== undefined}
            <span>CA {currentTurnCombatant.ac}</span>
          {/if}
          {#if currentTurnCombatant.action_budget}
            <span>Budget : {formatBudget(currentTurnCombatant.action_budget)}</span>
          {:else}
            <span class="hint">Budget non exposé pour ce combattant.</span>
          {/if}
        </div>
      </section>
    {/if}

    {#if combat.status === "active"}
      <section class="attack-panel">
        <h2>Attaque d'arme</h2>
        <p class="hint">
          attacker_id et target_id sont des <strong>combatant_id</strong> (pas
          character_id).
        </p>
        <div class="attack-form">
          <label>
            Attaquant
            <select bind:value={attackerId}>
              {#each Object.keys(combat.combatants) as cid (cid)}
                <option value={cid}>{combatantLabel(cid, combat)}</option>
              {/each}
            </select>
          </label>
          <label>
            Cible
            <select bind:value={targetId}>
              {#each Object.keys(combat.combatants) as cid (cid)}
                <option value={cid}>{combatantLabel(cid, combat)}</option>
              {/each}
            </select>
          </label>
          <label>
            Arme
            <select bind:value={weaponId}>
              {#each WEAPON_IDS as wid (wid)}
                <option value={wid}>{wid}</option>
              {/each}
            </select>
          </label>
        </div>
        <button type="button" onclick={launchAttack} disabled={!canAttack}>
          {loading ? "Attaque…" : "Attaquer"}
        </button>
      </section>
    {/if}

    {#if lastAttack}
      <section class="attack-result">
        <h2>Dernier jet</h2>
        <dl class="result-dl">
          <div>
            <dt>Jet d20</dt>
            <dd>
              {lastAttack.attack.d20.total}
              (d20={lastAttack.attack.d20.kept_value}, mod {lastAttack.attack.d20.modifier >= 0 ? "+" : ""}{lastAttack.attack.d20.modifier})
              {#if lastAttack.attack.d20.natural_20}
                — critique naturel
              {:else if lastAttack.attack.d20.natural_1}
                — échec automatique
              {/if}
            </dd>
          </div>
          <div>
            <dt>vs CA</dt>
            <dd>{lastAttack.attack.outcome.target_ac}</dd>
          </div>
          <div>
            <dt>Résultat</dt>
            <dd>
              {#if lastAttack.attack.outcome.hit}
                Touché{#if lastAttack.attack.outcome.critical} (critique){/if}
              {:else}
                Manqué
              {/if}
            </dd>
          </div>
          {#if lastAttack.damage}
            <div>
              <dt>Dégâts</dt>
              <dd>
                {lastAttack.damage.total ?? lastAttack.damage.damage_dealt}
                {#if lastAttack.damage.notation}
                  ({lastAttack.damage.notation})
                {/if}
                — PV {lastAttack.damage.hp_before} → {lastAttack.damage.hp_after}
              </dd>
            </div>
          {/if}
          <div>
            <dt>Cible (réponse)</dt>
            <dd>
              {lastAttack.target.combatant_id} — PV {lastAttack.target.hp_current}/{lastAttack.target.hp_max}
            </dd>
          </div>
        </dl>
        <p class="hint">Rechargez pour synchroniser l'état complet du combat.</p>
      </section>
    {/if}

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
                <span class="mono">({cid})</span>
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
              <span class="mono">{effect.effect_id}</span> — cible {effect.target_id}, source {effect.source_id},
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
