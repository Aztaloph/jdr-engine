<script lang="ts">
  import {
    advanceCombatTurn,
    fetchCombatState,
    isLoadError,
    postCombatCast,
    postWeaponAttack,
  } from "../api/combat";
  import type { CombatState, LoadError } from "../types/combat";
  import {
    WEAPON_IDS,
    type WeaponAttackResult,
    type WeaponId,
  } from "../types/attack";
  import { link, router } from "svelte-spa-router";
  import { navigateToCombat, viewerFromQuerystring } from "../navigation";
  import ErrorAlert from "../components/ErrorAlert.svelte";

  type JournalEntry =
    | {
        id: number;
        kind: "attack";
        summary: string;
        detail: string;
      }
    | {
        id: number;
        kind: "spell";
        summary: string;
        detail: string;
      };

  let {
    params = {},
    onRouteEvent: _onRouteEvent,
  }: {
    params?: { id?: string | null };
    onRouteEvent?: (detail: unknown) => void;
  } = $props();

  const combatId = $derived(params.id ?? "");
  const initialViewer = $derived(viewerFromQuerystring(router.querystring));

  let viewer = $state("");
  let combat = $state<CombatState | null>(null);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);
  let journalSeq = $state(0);
  let journal = $state<JournalEntry[]>([]);

  let attackerId = $state("");
  let targetId = $state("");
  let weaponId = $state<WeaponId>("longsword");

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

  const castableSpells = $derived(combat?.viewer?.castable_spells ?? []);

  const canCastSpell = $derived(
    combat !== null &&
      combat.status === "active" &&
      combat.viewer?.combatant_id != null &&
      targetId !== "" &&
      targetId !== combat.viewer.combatant_id &&
      !loading,
  );

  const currentTurnCombatant = $derived(
    combat && combat.current_combatant_id
      ? combat.combatants[combat.current_combatant_id]
      : undefined,
  );

  $effect(() => {
    viewer = initialViewer;
  });

  $effect(() => {
    const id = combatId;
    const v = initialViewer;
    void loadCombat(id, v);
  });

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

  function combatantName(cid: string, state: CombatState): string {
    return state.combatants[cid]?.display_name ?? cid;
  }

  function combatantLabel(cid: string, state: CombatState): string {
    const c = state.combatants[cid];
    if (!c) {
      return cid;
    }
    return `${c.display_name} (${cid})`;
  }

  function formatHp(c: CombatState["combatants"][string]): string {
    if (c.hp_current === undefined) {
      return "PV —";
    }
    const max = c.hp_max !== undefined ? `/${c.hp_max}` : "";
    return `PV ${c.hp_current}${max}`;
  }

  function budgetLine(
    label: string,
    available: boolean | undefined,
  ): string {
    if (available === undefined) {
      return `${label} : —`;
    }
    return `${label} : ${available ? "disponible" : "consommée"}`;
  }

  function applyCombatState(state: CombatState) {
    combat = state;
    syncAttackSelectors(state);
  }

  function pushJournal(entry: Omit<JournalEntry, "id">) {
    journalSeq += 1;
    journal = [{ ...entry, id: journalSeq }, ...journal];
  }

  async function loadCombat(id: string, viewerParam: string) {
    error = null;
    loading = true;
    try {
      applyCombatState(await fetchCombatState(id, viewerParam));
    } catch (e) {
      combat = null;
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function refreshCombat() {
    if (!combatId) {
      return;
    }
    loading = true;
    try {
      applyCombatState(await fetchCombatState(combatId, viewer));
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function reload() {
    await loadCombat(combatId, viewer);
  }

  function onViewerInput() {
    navigateToCombat(combatId, viewer);
  }

  async function advanceTurn() {
    if (!canAdvance) {
      return;
    }
    error = null;
    loading = true;
    try {
      applyCombatState(await advanceCombatTurn(combatId, viewer));
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  function describeAttack(
    state: CombatState,
    result: WeaponAttackResult,
    attacker: string,
    target: string,
  ): { summary: string; detail: string } {
    const atkName = combatantName(attacker, state);
    const tgtName = combatantName(target, state);
    const hit = result.attack.outcome.hit;
    const summary = hit
      ? `${atkName} touche ${tgtName} (${result.attack.d20.total} vs CA ${result.attack.outcome.target_ac})`
      : `${atkName} manque ${tgtName} (${result.attack.d20.total} vs CA ${result.attack.outcome.target_ac})`;
    let detail = `Arme · d20=${result.attack.d20.kept_value}, mod ${result.attack.d20.modifier >= 0 ? "+" : ""}${result.attack.d20.modifier}`;
    if (result.damage) {
      detail += ` · dégâts ${result.damage.total ?? result.damage.damage_dealt}`;
      if (result.damage.hp_before !== undefined && result.damage.hp_after !== undefined) {
        detail += ` · PV ${result.damage.hp_before}→${result.damage.hp_after}`;
      }
    }
    return { summary, detail };
  }

  async function launchAttack() {
    if (!canAttack || !combat) {
      return;
    }
    error = null;
    loading = true;
    const stateSnapshot = combat;
    const atk = attackerId;
    const tgt = targetId;
    try {
      const result = await postWeaponAttack(
        combatId,
        {
          attacker_id: attackerId,
          target_id: targetId,
          weapon_id: weaponId,
        },
        viewer,
      );
      const { summary, detail } = describeAttack(stateSnapshot, result, atk, tgt);
      pushJournal({ kind: "attack", summary, detail });
      await refreshCombat();
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function launchSpell(spellId: string) {
    if (!canCastSpell || !combat?.viewer?.combatant_id) {
      return;
    }
    error = null;
    loading = true;
    const casterId = combat.viewer.combatant_id;
    const tgt = targetId;
    try {
      const next = await postCombatCast(
        combatId,
        {
          caster_id: casterId,
          spell_id: spellId,
          target_ids: [targetId],
        },
        viewer,
      );
      applyCombatState(next);
      const casterName = combatantName(casterId, next);
      const targetName = combatantName(tgt, next);
      pushJournal({
        kind: "spell",
        summary: `${casterName} lance ${spellId} sur ${targetName}`,
        detail: `Sort overlay · cible ${tgt}`,
      });
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }
</script>

<h1>Combat</h1>
<p class="hint">
  combat_id <span class="mono">{combatId}</span> — round et initiative mis à jour
  après chaque action.
</p>

<fieldset>
  <legend>Vue</legend>
  <label>
    viewer (character_id — requis pour les sorts du joueur)
    <input
      type="text"
      bind:value={viewer}
      oninput={onViewerInput}
      placeholder="ex. a505d6d5 (rodeur)"
      autocomplete="off"
    />
  </label>
</fieldset>

<div class="actions">
  <button type="button" onclick={reload} disabled={loading}>
    {loading ? "Chargement…" : "Recharger"}
  </button>
  <button type="button" onclick={advanceTurn} disabled={!canAdvance}>
    Tour suivant
  </button>
</div>

{#if error}
  <ErrorAlert {error} />
{/if}

{#if combat}
  {@const currentId = combat.current_combatant_id}
  <section class="hud" aria-live="polite">
    <header class="hud-header">
      <span>Statut {combat.status}</span>
      <span>Round {combat.round_number}</span>
    </header>

    {#if currentTurnCombatant && currentId}
      <section class="hud-turn" aria-label="Tour courant">
        <h2 class="hud-turn-title">
          Tour — {currentTurnCombatant.display_name}
        </h2>
        <div class="hud-turn-stats">
          <span>{formatHp(currentTurnCombatant)}</span>
          {#if currentTurnCombatant.ac !== undefined}
            <span>CA {currentTurnCombatant.ac}</span>
          {/if}
        </div>
        {#if currentTurnCombatant.action_budget}
          <div class="hud-budget">
            <span>{budgetLine("Action", currentTurnCombatant.action_budget.has_action)}</span>
            <span>{budgetLine("Action bonus", currentTurnCombatant.action_budget.has_bonus_action)}</span>
          </div>
        {:else}
          <p class="hint">Budget d'action non exposé pour ce combattant.</p>
        {/if}
        {#if currentTurnCombatant.concentration_spell_name}
          <p class="hud-concentration">
            Concentration : {currentTurnCombatant.concentration_spell_name}
            {#if currentTurnCombatant.concentration_spell_id}
              <span class="mono">({currentTurnCombatant.concentration_spell_id})</span>
            {/if}
          </p>
        {/if}
      </section>
    {/if}

    <section class="hud-initiative" aria-label="Ordre d'initiative">
      <h2 class="hud-section-title">Initiative</h2>
      {#if combat.initiative_order.length === 0}
        <p class="hint">Ordre vide.</p>
      {:else}
        <ol class="hud-initiative-list">
          {#each combat.initiative_order as cid (cid)}
            {@const c = combat.combatants[cid]}
            <li class="hud-initiative-item" class:is-turn={cid === currentId} class:is-inactive={c && !c.is_active}>
              <div class="hud-initiative-head">
                <strong>{c?.display_name ?? cid}</strong>
                {#if cid === currentId}
                  <span class="hud-turn-badge">tour</span>
                {/if}
              </div>
              {#if c}
                <div class="hud-initiative-meta">
                  <span>{formatHp(c)}</span>
                  {#if c.ac !== undefined}
                    <span>CA {c.ac}</span>
                  {/if}
                  {#if c.concentration_spell_name}
                    <span>Conc. {c.concentration_spell_name}</span>
                  {/if}
                  {#if c.character_id}
                    <a
                      href="/character/{encodeURIComponent(c.character_id)}"
                      use:link
                      class="inline-link"
                    >fiche</a>
                  {/if}
                </div>
              {/if}
            </li>
          {/each}
        </ol>
      {/if}
    </section>

    {#if combat.active_effects.length > 0}
      <section class="hud-effects" aria-label="Effets actifs">
        <h2 class="hud-section-title">Effets actifs</h2>
        <ul class="hud-effects-list">
          {#each combat.active_effects as effect (effect.effect_id + effect.target_id + effect.applied_at_round)}
            <li>
              <span class="mono">{effect.effect_id}</span>
              → {effect.target_id}
              <span class="hint">(round {effect.applied_at_round}, {effect.expiry_mode})</span>
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if combat.status === "active"}
      <section class="hud-actions">
        <h2 class="hud-section-title">Actions</h2>
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

        {#if castableSpells.length > 0}
          <div class="spell-actions">
            {#each castableSpells as spellId (spellId)}
              <button
                type="button"
                onclick={() => launchSpell(spellId)}
                disabled={!canCastSpell}
              >
                {spellId}
              </button>
            {/each}
          </div>
        {:else if viewer.trim()}
          <p class="hint">
            Aucun sort lançable pour ce viewer (hors tour, budget, ou fiche).
          </p>
        {:else}
          <p class="hint">
            Renseignez viewer (character_id) pour voir les sorts lançables.
          </p>
        {/if}
      </section>
    {:else if combat.status === "preparing"}
      <p class="hint">Combat en préparation — activez depuis le lobby.</p>
    {/if}

    <section class="hud-journal" aria-label="Journal de session">
      <h2 class="hud-section-title">Journal</h2>
      {#if journal.length === 0}
        <p class="hint">Aucune action enregistrée cette session.</p>
      {:else}
        <ol class="hud-journal-list">
          {#each journal as entry (entry.id)}
            <li class="hud-journal-item" class:spell={entry.kind === "spell"}>
              <span class="hud-journal-kind">{entry.kind === "attack" ? "⚔" : "✨"}</span>
              <div>
                <div>{entry.summary}</div>
                <div class="hint">{entry.detail}</div>
              </div>
            </li>
          {/each}
        </ol>
      {/if}
    </section>
  </section>
{/if}

<style>
  .hud {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 1rem;
  }

  .hud-header {
    display: flex;
    gap: 1.25rem;
    font-weight: 600;
  }

  .hud-turn {
    border: 2px solid var(--current-border, #3b82f6);
    background: var(--current-bg, #3b82f622);
    border-radius: 8px;
    padding: 0.85rem 1rem;
  }

  .hud-turn-title {
    margin: 0 0 0.35rem;
    font-size: 1.05rem;
  }

  .hud-turn-stats,
  .hud-budget,
  .hud-initiative-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem 1rem;
    font-size: 0.95rem;
  }

  .hud-budget {
    margin-top: 0.35rem;
  }

  .hud-concentration {
    margin: 0.5rem 0 0;
    font-size: 0.95rem;
  }

  .hud-section-title {
    font-size: 0.95rem;
    margin: 0 0 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    opacity: 0.85;
  }

  .hud-initiative-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .hud-initiative-item {
    border: 1px solid var(--border, #8884);
    border-radius: 6px;
    padding: 0.55rem 0.75rem;
  }

  .hud-initiative-item.is-turn {
    border-color: var(--current-border, #3b82f6);
    background: var(--current-bg, #3b82f622);
  }

  .hud-initiative-item.is-inactive {
    opacity: 0.55;
  }

  .hud-initiative-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .hud-turn-badge {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    background: var(--current-border, #3b82f6);
    color: #fff;
  }

  .hud-effects-list,
  .hud-journal-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .hud-effects-list li {
    margin-bottom: 0.35rem;
    font-size: 0.92rem;
  }

  .hud-actions {
    border-top: 1px solid var(--border, #8884);
    padding-top: 0.75rem;
  }

  .hud-journal-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .hud-journal-item {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 0.65rem;
    border-radius: 6px;
    border: 1px solid var(--border, #8884);
    font-size: 0.92rem;
  }

  .hud-journal-item.spell {
    border-color: #7c3aed66;
  }

  .hud-journal-kind {
    flex-shrink: 0;
    width: 1.25rem;
    text-align: center;
  }
</style>
