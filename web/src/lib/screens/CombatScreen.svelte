<script lang="ts">
  import {
    advanceCombatTurn,
    closeCombat,
    fetchCombatState,
    isLoadError,
    postCombatCast,
    postWeaponAttack,
  } from "../api/combat";
  import type { ActiveEffect, CombatState, LoadError } from "../types/combat";
  import {
    WEAPON_IDS,
    type WeaponAttackResult,
    type WeaponId,
  } from "../types/attack";
  import { router } from "svelte-spa-router";
  import { navigateToCombat, navigateToLobby, viewerFromQuerystring } from "../navigation";
  import ErrorAlert from "../components/ErrorAlert.svelte";
  import Panel from "../components/combat/Panel.svelte";
  import CombatantCard from "../components/combat/CombatantCard.svelte";
  import JournalItem from "../components/combat/JournalItem.svelte";
  import MapPlaceholder from "../components/combat/MapPlaceholder.svelte";
  import DiceBar from "../components/combat/DiceBar.svelte";

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

  const combatParticipants = $derived(
    combat
      ? Object.values(combat.combatants).map((c) => ({
          character_id: c.character_id,
          display_name: c.display_name,
        }))
      : [],
  );

  const isViewerTurn = $derived(
    combat?.viewer?.combatant_id != null &&
      combat.current_combatant_id === combat.viewer.combatant_id,
  );

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

  /** Effets actifs regroupés par combattant ciblé — pour les badges des cartes. */
  const effectsByTarget = $derived.by(() => {
    const map = new Map<string, ActiveEffect[]>();
    if (combat) {
      for (const effect of combat.active_effects) {
        const list = map.get(effect.target_id) ?? [];
        list.push(effect);
        map.set(effect.target_id, list);
      }
    }
    return map;
  });

  /** Ordre d'affichage du groupe — initiative si établie, sinon tous les combattants. */
  const groupOrder = $derived(
    combat
      ? combat.initiative_order.length > 0
        ? combat.initiative_order
        : Object.keys(combat.combatants)
      : [],
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

  function initialsOf(name: string): string {
    return name
      .split(/\s+/)
      .map((word) => word[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
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

  function onViewerSelect() {
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

  async function closeAndReturnToLobby() {
    if (!combatId) {
      return;
    }
    error = null;
    loading = true;
    try {
      await closeCombat(combatId);
      navigateToLobby();
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

<div class="combat-screen">
  <header class="topbar">
    <div class="topbar-brand">
      <span class="brand">JDR Engine</span>
      <span class="sep" aria-hidden="true">·</span>
      <h1 class="encounter">Rencontre <span class="mono">#{combatId}</span></h1>
      <span class="soon-chip">Campagne — à venir</span>
    </div>

    {#if combat}
      <div class="topbar-pills">
        <span class="pill pill-accent">Round {combat.round_number}</span>
        {#if currentTurnCombatant}
          <span class="pill">Tour de : <strong>{currentTurnCombatant.display_name}</strong></span>
        {/if}
        <span class="pill pill-muted">{combat.status}</span>
      </div>
    {/if}

    <div class="topbar-controls">
      {#if combatParticipants.length > 0}
        <label class="viewer-control">
          <span class="viewer-label">Vue joueur</span>
          <select bind:value={viewer} onchange={onViewerSelect}>
            <option value="">— Vue MJ —</option>
            {#each combatParticipants as p (p.character_id)}
              <option value={p.character_id}>
                {p.display_name} ({p.character_id})
              </option>
            {/each}
          </select>
        </label>
      {:else}
        <label class="viewer-control">
          <span class="viewer-label">Vue joueur (character_id)</span>
          <input
            type="text"
            bind:value={viewer}
            oninput={onViewerSelect}
            placeholder="ex. a505d6d5"
            autocomplete="off"
          />
        </label>
      {/if}
      <button type="button" onclick={reload} disabled={loading}>
        {loading ? "Chargement…" : "Recharger"}
      </button>
      <button type="button" onclick={closeAndReturnToLobby} disabled={loading || !combatId}>
        Clôturer
      </button>
    </div>
  </header>
  <p class="topbar-hint hint">
    Round et initiative mis à jour après chaque action.
  </p>

  {#if error}
    <ErrorAlert {error} />
  {/if}

  {#if combat}
    <div class="hud-grid" aria-live="polite">
      <div class="col col-left">
        <Panel title="Membres du groupe">
          {#if groupOrder.length === 0}
            <p class="hint">Aucun combattant.</p>
          {:else}
            {#each groupOrder as cid (cid)}
              {@const c = combat.combatants[cid]}
              {#if c}
                <CombatantCard
                  combatant={c}
                  isTurn={cid === combat.current_combatant_id}
                  effects={effectsByTarget.get(cid) ?? []}
                />
              {/if}
            {/each}
          {/if}
        </Panel>

        <Panel title="Ordre d'initiative">
          {#if combat.initiative_order.length === 0}
            <p class="hint">Ordre vide.</p>
          {:else}
            <ol class="init-track">
              {#each combat.initiative_order as cid (cid)}
                {@const c = combat.combatants[cid]}
                <li
                  class="init-token"
                  class:is-turn={cid === combat.current_combatant_id}
                  class:is-inactive={c !== undefined && !c.is_active}
                >
                  <span class="init-avatar" aria-hidden="true">
                    {initialsOf(c?.display_name ?? cid)}
                  </span>
                  <span class="init-name">{c?.display_name ?? cid}</span>
                  {#if c?.initiative_total !== undefined}
                    <span class="init-score">{c.initiative_total}</span>
                  {/if}
                </li>
              {/each}
            </ol>
          {/if}
        </Panel>

        {#if combat.active_effects.length > 0}
          <Panel title="Effets actifs">
            <ul class="effects-list">
              {#each combat.active_effects as effect (effect.effect_id + effect.target_id + effect.applied_at_round)}
                <li>
                  <span class="mono">{effect.effect_id}</span>
                  → {combatantName(effect.target_id, combat)}
                  <span class="hint">(round {effect.applied_at_round}, {effect.expiry_mode})</span>
                </li>
              {/each}
            </ul>
          </Panel>
        {/if}
      </div>

      <div class="col col-center">
        <MapPlaceholder />
      </div>

      <div class="col col-right">
        <Panel
          title={currentTurnCombatant
            ? `Fiche active : ${currentTurnCombatant.display_name}`
            : "Fiche active"}
        >
          {#if currentTurnCombatant}
            <div class="active-stats">
              <span>{formatHp(currentTurnCombatant)}</span>
              {#if currentTurnCombatant.ac !== undefined}
                <span>CA {currentTurnCombatant.ac}</span>
              {/if}
            </div>
            {#if currentTurnCombatant.action_budget}
              <ul class="budget-list">
                <li>{budgetLine("Action", currentTurnCombatant.action_budget.has_action)}</li>
                <li>{budgetLine("Action bonus", currentTurnCombatant.action_budget.has_bonus_action)}</li>
                <li>{budgetLine("Réaction", currentTurnCombatant.action_budget.has_reaction)}</li>
                <li>{budgetLine("Mouvement", currentTurnCombatant.action_budget.has_movement)}</li>
              </ul>
            {:else}
              <p class="hint">Budget d'action non exposé pour ce combattant.</p>
            {/if}
            {#if currentTurnCombatant.concentration_spell_name}
              <p class="conc-line">
                Concentration : {currentTurnCombatant.concentration_spell_name}
                {#if currentTurnCombatant.concentration_spell_id}
                  <span class="mono">({currentTurnCombatant.concentration_spell_id})</span>
                {/if}
              </p>
            {/if}
          {:else}
            <p class="hint">Aucun tour actif.</p>
          {/if}
          <div class="stats-placeholder">
            <span class="soon-chip">À venir</span>
            <p class="hint">
              Caractéristiques (FOR, DEX, CON, INT, SAG, CHA) — prévues dans un
              lot ultérieur.
            </p>
          </div>
        </Panel>

        <Panel title="Actions rapides">
          {#if combat.status === "active"}
            <div class="action-block">
              <h3 class="action-title">Attaque d'arme</h3>
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
              <button type="button" class="btn-primary" onclick={launchAttack} disabled={!canAttack}>
                {loading ? "Attaque…" : "Attaquer"}
              </button>
            </div>

            <div class="action-block">
              <h3 class="action-title">Lancer un sort</h3>
              {#if castableSpells.length > 0}
                <div class="spell-actions">
                  {#each castableSpells as spellId (spellId)}
                    <button
                      type="button"
                      class="btn-primary"
                      onclick={() => launchSpell(spellId)}
                      disabled={!canCastSpell}
                    >
                      {spellId}
                    </button>
                  {/each}
                </div>
              {:else if viewer.trim()}
                {#if combat.viewer?.combatant_id == null}
                  <p class="hint">Ce viewer ne participe pas à ce combat.</p>
                {:else if !isViewerTurn}
                  <p class="hint">
                    Ce n'est pas le tour de {combatantName(combat.viewer.combatant_id, combat)}
                    — utilisez « Fin de tour ».
                  </p>
                {:else}
                  <p class="hint">
                    Aucun sort overlay lançable pour cette fiche (voir la liste ci-dessous).
                  </p>
                {/if}
              {:else}
                <p class="hint">
                  Choisissez un viewer (en haut) pour activer les sorts joueur.
                </p>
              {/if}
              <p class="hint">
                Sorts combat (overlay v1) : <code>hunters_mark</code> rôdeur ·
                <code>bless</code> clerc · <code>hex</code>. Au tour du viewer,
                avec le budget requis (<code>shield</code> = réaction, hors panneau).
              </p>
            </div>

            <button type="button" disabled title="En développement">
              Compétences — à venir
            </button>

            <button
              type="button"
              class="btn-primary btn-endturn"
              onclick={advanceTurn}
              disabled={!canAdvance}
            >
              Fin de tour
            </button>
          {:else if combat.status === "preparing"}
            <p class="hint">Combat en préparation — activez depuis le lobby.</p>
          {:else}
            <p class="hint">Combat terminé.</p>
          {/if}
        </Panel>

        <Panel title="Journal de combat">
          {#if journal.length === 0}
            <p class="hint">Aucune action enregistrée cette session.</p>
          {:else}
            <ol class="journal-list">
              {#each journal as entry (entry.id)}
                <JournalItem kind={entry.kind} summary={entry.summary} detail={entry.detail} />
              {/each}
            </ol>
          {/if}
        </Panel>
      </div>
    </div>

    <DiceBar />
  {/if}
</div>

<style>
  .combat-screen {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
  }

  /* ---- barre supérieure ---- */

  .topbar {
    display: flex;
    align-items: center;
    gap: var(--space-md) var(--space-lg);
    flex-wrap: wrap;
    padding: 0.6rem 0.9rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .topbar-brand {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    min-width: 0;
  }

  .brand {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-accent);
    white-space: nowrap;
  }

  .sep {
    color: var(--color-text-muted);
  }

  .encounter {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.05rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .soon-chip {
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    padding: 0.1rem 0.5rem;
    white-space: nowrap;
  }

  .topbar-pills {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .pill {
    font-size: 0.8rem;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--color-border-default);
    background: var(--color-bg-panel);
    white-space: nowrap;
  }

  .pill-accent {
    border-color: var(--color-accent);
    color: var(--color-accent);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .pill-muted {
    color: var(--color-text-muted);
  }

  .topbar-controls {
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-left: auto;
  }

  .topbar-controls button {
    padding: 0.4rem 0.7rem;
    font-size: 0.85rem;
  }

  .viewer-control {
    margin: 0;
    min-width: 15rem;
  }

  .viewer-label {
    display: block;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.15rem;
  }

  .viewer-control select,
  .viewer-control input {
    margin-top: 0;
    padding: 0.35rem 0.5rem;
    font-size: 0.85rem;
  }

  .topbar-hint {
    margin: -0.35rem 0 0 0.2rem;
  }

  /* ---- grille trois colonnes ---- */

  .hud-grid {
    display: grid;
    grid-template-columns: minmax(250px, 300px) minmax(0, 1fr) minmax(295px, 340px);
    gap: var(--space-md);
    align-items: start;
  }

  .col {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    min-width: 0;
  }

  .col-center {
    align-self: stretch;
  }

  /* ---- initiative ---- */

  .init-track {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .init-token {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.2rem;
    width: 4.2rem;
    padding: 0.4rem 0.2rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-bg-panel);
    text-align: center;
  }

  .init-token.is-turn {
    border-color: var(--color-accent);
    background: var(--color-accent-muted);
  }

  .init-token.is-inactive {
    opacity: 0.5;
  }

  .init-avatar {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-default);
  }

  .init-token.is-turn .init-avatar {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .init-name {
    font-size: 0.68rem;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .init-score {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--color-accent);
  }

  /* ---- effets ---- */

  .effects-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.88rem;
  }

  /* ---- fiche active ---- */

  .active-stats {
    display: flex;
    gap: 1rem;
    font-size: 0.95rem;
    font-weight: 600;
  }

  .budget-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.25rem 0.75rem;
    font-size: 0.85rem;
  }

  .conc-line {
    margin: 0;
    font-size: 0.88rem;
  }

  .stats-placeholder {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px dashed var(--color-border-default);
  }

  .stats-placeholder .hint {
    flex: 1;
  }

  /* ---- actions rapides ---- */

  .action-block {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .action-title {
    margin: 0;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  .attack-form {
    display: grid;
    gap: 0.5rem;
  }

  .attack-form label {
    margin-bottom: 0;
    font-size: 0.82rem;
  }

  .btn-primary {
    background: var(--color-accent);
    color: var(--color-accent-text);
    border-color: var(--color-accent);
    font-weight: 600;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-accent-hover);
    border-color: var(--color-accent-hover);
  }

  .btn-endturn {
    width: 100%;
  }

  .spell-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  /* ---- journal ---- */

  .journal-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 24rem;
    overflow-y: auto;
  }

  /* ---- responsive ---- */

  @media (max-width: 1080px) {
    .hud-grid {
      grid-template-columns: 1fr;
    }

    .col-center {
      order: -1;
    }

    .topbar-controls {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
