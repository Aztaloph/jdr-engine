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
  import { link, router } from "svelte-spa-router";
  import { navigateToCombat, navigateToLobby, viewerFromQuerystring } from "../navigation";
  import ErrorAlert from "../components/ErrorAlert.svelte";
  import Panel from "../components/combat/Panel.svelte";
  import CombatantCard from "../components/combat/CombatantCard.svelte";
  import CharacterPortrait from "../components/combat/CharacterPortrait.svelte";
  import Icon from "../components/combat/Icon.svelte";
  import JournalItem from "../components/combat/JournalItem.svelte";
  import MapPlaceholder from "../components/combat/MapPlaceholder.svelte";
  import DiceBar from "../components/combat/DiceBar.svelte";

  type JournalEntry = {
    id: number;
    kind: "attack" | "spell";
    summary: string;
    detail: string;
    /** Heure locale du client au moment de l'action — cosmétique. */
    time: string;
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

  function applyCombatState(state: CombatState) {
    combat = state;
    syncAttackSelectors(state);
  }

  function pushJournal(entry: Omit<JournalEntry, "id" | "time">) {
    journalSeq += 1;
    const time = new Date().toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    journal = [{ ...entry, id: journalSeq, time }, ...journal];
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

  const ABILITY_LABELS = ["FOR", "DEX", "CON", "INT", "SAG", "CHA"] as const;
</script>

<div class="combat-screen">
  <header class="topbar">
    <div class="topbar-brand">
      <a href="/" use:link class="brand">JDR Engine</a>
      <span class="sep" aria-hidden="true"></span>
      <div class="encounter-block">
        <h1 class="encounter">Rencontre <span class="mono">#{combatId}</span></h1>
        <span class="encounter-sub">Campagne — à venir</span>
      </div>
    </div>

    {#if combat}
      <div class="topbar-pills">
        <span class="pill pill-accent">
          <Icon name="flag" size={11} />
          Round {combat.round_number}
        </span>
        {#if currentTurnCombatant}
          <span class="pill pill-turn">
            Tour de <strong>{currentTurnCombatant.display_name}</strong>
          </span>
        {/if}
        <span class="pill pill-muted" class:pill-live={combat.status === "active"}>
          <span class="status-dot" aria-hidden="true"></span>
          {combat.status}
        </span>
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
      <button
        type="button"
        class="top-btn"
        onclick={reload}
        disabled={loading}
        title="Round et initiative mis à jour après chaque action"
      >
        <Icon name="refresh" size={13} />
        {loading ? "Chargement…" : "Recharger"}
      </button>
      <button
        type="button"
        class="top-btn danger"
        onclick={closeAndReturnToLobby}
        disabled={loading || !combatId}
      >
        <Icon name="exit" size={13} />
        Clôturer
      </button>
      <a href="/lobby" use:link class="top-link">Lobby</a>
    </div>
  </header>

  {#if error}
    <ErrorAlert {error} />
  {/if}

  {#if combat}
    <div class="hud-grid" aria-live="polite">
      <div class="col col-left">
        <Panel title="Membres du groupe" icon="users" badge={`${groupOrder.length}`}>
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

        <Panel title="Ordre d'initiative" icon="flag">
          {#if combat.initiative_order.length === 0}
            <p class="hint">Ordre vide.</p>
          {:else}
            <ol class="init-track">
              {#each combat.initiative_order as cid, idx (cid)}
                {@const c = combat.combatants[cid]}
                <li
                  class="init-token"
                  class:is-turn={cid === combat.current_combatant_id}
                  class:is-inactive={c !== undefined && !c.is_active}
                >
                  <span class="init-rank mono">{idx + 1}</span>
                  <CharacterPortrait
                    name={c?.display_name ?? cid}
                    size={32}
                    active={cid === combat.current_combatant_id}
                  />
                  <span class="init-name">{c?.display_name ?? cid}</span>
                  {#if c?.initiative_total !== undefined}
                    <span class="init-score mono">{c.initiative_total}</span>
                  {/if}
                </li>
              {/each}
            </ol>
          {/if}
        </Panel>

        {#if combat.active_effects.length > 0}
          <Panel title="Effets actifs" icon="wand" badge={`${combat.active_effects.length}`}>
            <ul class="effects-list">
              {#each combat.active_effects as effect (effect.effect_id + effect.target_id + effect.applied_at_round)}
                <li class="effect-row">
                  <span class="effect-name mono">{effect.effect_id}</span>
                  <span class="effect-target">→ {combatantName(effect.target_id, combat)}</span>
                  <span class="effect-meta">round {effect.applied_at_round} · {effect.expiry_mode}</span>
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
        <Panel title="Fiche active" icon="user">
          {#if currentTurnCombatant}
            <div class="active-head">
              <CharacterPortrait name={currentTurnCombatant.display_name} size={44} active />
              <div class="active-id">
                <strong class="active-name">{currentTurnCombatant.display_name}</strong>
                <span class="active-sub">Classe et niveau — à venir</span>
              </div>
            </div>

            <div class="vital-chips">
              <div class="vital">
                <span class="vital-label">PV</span>
                <span class="vital-value mono">
                  {currentTurnCombatant.hp_current !== undefined
                    ? `${currentTurnCombatant.hp_current}${currentTurnCombatant.hp_max !== undefined ? ` / ${currentTurnCombatant.hp_max}` : ""}`
                    : "—"}
                </span>
              </div>
              <div class="vital">
                <span class="vital-label">CA</span>
                <span class="vital-value mono">
                  {currentTurnCombatant.ac !== undefined ? currentTurnCombatant.ac : "—"}
                </span>
              </div>
            </div>

            {#if currentTurnCombatant.action_budget}
              {@const b = currentTurnCombatant.action_budget}
              <div class="budget-chips">
                <span class="budget-chip" class:used={!b.has_action}>Action</span>
                <span class="budget-chip" class:used={!b.has_bonus_action}>Bonus</span>
                <span class="budget-chip" class:used={!b.has_reaction}>Réaction</span>
                <span class="budget-chip" class:used={!b.has_movement}>Mouvement</span>
              </div>
            {:else}
              <p class="hint">Budget d'action non exposé pour ce combattant.</p>
            {/if}

            {#if currentTurnCombatant.concentration_spell_name}
              <p class="conc-line">
                <Icon name="sparkle" size={12} />
                Concentration : <strong>{currentTurnCombatant.concentration_spell_name}</strong>
                {#if currentTurnCombatant.concentration_spell_id}
                  <span class="mono conc-id">({currentTurnCombatant.concentration_spell_id})</span>
                {/if}
              </p>
            {/if}
          {:else}
            <p class="hint">Aucun tour actif.</p>
          {/if}

          <div class="abilities">
            {#each ABILITY_LABELS as ab (ab)}
              <div class="ability" title="Caractéristiques — à venir">
                <span class="ability-name">{ab}</span>
                <span class="ability-value">—</span>
              </div>
            {/each}
          </div>
          <p class="abilities-note">Caractéristiques — à venir</p>
        </Panel>

        <Panel title="Actions rapides" icon="sword">
          {#if combat.status === "active"}
            <div class="action-block">
              <h3 class="action-title">
                <Icon name="sword" size={12} />
                Attaque d'arme
              </h3>
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
              <button
                type="button"
                class="btn-strike"
                onclick={launchAttack}
                disabled={!canAttack}
              >
                <Icon name="sword" size={14} />
                {loading ? "Attaque…" : "Attaquer"}
              </button>
            </div>

            <div class="action-sep" aria-hidden="true"></div>

            <div class="action-block">
              <h3 class="action-title">
                <Icon name="sparkle" size={12} />
                Lancer un sort
              </h3>
              {#if castableSpells.length > 0}
                <div class="spell-actions">
                  {#each castableSpells as spellId (spellId)}
                    <button
                      type="button"
                      class="btn-spell"
                      onclick={() => launchSpell(spellId)}
                      disabled={!canCastSpell}
                    >
                      <Icon name="sparkle" size={12} />
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
              <p class="hint spell-help">
                Sorts combat (overlay v1) : <code>hunters_mark</code> rôdeur ·
                <code>bless</code> clerc · <code>hex</code>. Au tour du viewer,
                avec le budget requis (<code>shield</code> = réaction, hors panneau).
              </p>
            </div>

            <div class="action-sep" aria-hidden="true"></div>

            <button type="button" class="btn-skill" disabled title="En développement">
              <Icon name="wand" size={13} />
              Compétences
              <span class="soon-tag">À venir</span>
            </button>

            <button
              type="button"
              class="btn-endturn"
              onclick={advanceTurn}
              disabled={!canAdvance}
            >
              <Icon name="next" size={14} />
              Fin de tour
            </button>
          {:else if combat.status === "preparing"}
            <p class="hint">Combat en préparation — activez depuis le lobby.</p>
          {:else}
            <p class="hint">Combat terminé.</p>
          {/if}
        </Panel>

        <Panel title="Journal de combat" icon="scroll" badge={`${journal.length}`}>
          {#if journal.length === 0}
            <p class="hint journal-empty">
              Aucune action enregistrée cette session — les attaques et sorts
              apparaîtront ici.
            </p>
          {:else}
            <ol class="journal-list">
              {#each journal as entry (entry.id)}
                <JournalItem
                  kind={entry.kind}
                  summary={entry.summary}
                  detail={entry.detail}
                  time={entry.time}
                />
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
    min-height: 100vh;
    padding: var(--space-md) var(--space-md) var(--space-lg);
    background:
      radial-gradient(ellipse 60% 40% at 50% 0%, rgb(245 158 11 / 0.04), transparent 70%),
      linear-gradient(rgb(255 255 255 / 0.008) 1px, transparent 1px),
      linear-gradient(90deg, rgb(255 255 255 / 0.008) 1px, transparent 1px),
      var(--color-bg-base);
    background-size:
      100% 100%,
      44px 44px,
      44px 44px,
      100% 100%;
  }

  /* ---- barre supérieure ---- */

  .topbar {
    display: flex;
    align-items: center;
    gap: var(--space-md) var(--space-lg);
    flex-wrap: wrap;
    padding: 0.5rem 0.9rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background:
      linear-gradient(rgb(255 255 255 / 0.02), transparent 60%),
      var(--color-bg-elevated);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 6px 18px rgb(0 0 0 / 0.35);
  }

  .topbar-brand {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    min-width: 0;
  }

  .brand {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-accent);
    white-space: nowrap;
    text-decoration: none;
  }

  .brand:hover {
    color: var(--color-accent-hover);
  }

  .sep {
    width: 1px;
    height: 1.8rem;
    background: var(--color-border-subtle);
  }

  .encounter-block {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
  }

  .encounter {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.2;
    white-space: nowrap;
  }

  .encounter-sub {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .topbar-pills {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.76rem;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--color-border-default);
    background: var(--color-bg-panel);
    white-space: nowrap;
  }

  .pill-accent {
    border-color: rgb(245 158 11 / 0.5);
    background: rgb(245 158 11 / 0.08);
    color: var(--color-accent);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.7rem;
  }

  .pill-turn strong {
    color: var(--color-accent);
  }

  .pill-muted {
    color: var(--color-text-muted);
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-text-muted);
  }

  .pill-live .status-dot {
    background: var(--color-success);
    box-shadow: 0 0 6px rgb(74 222 128 / 0.6);
  }

  .pill-live {
    color: var(--color-success);
  }

  .topbar-controls {
    display: flex;
    align-items: flex-end;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-left: auto;
  }

  .top-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.38rem 0.7rem;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--color-text-secondary);
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-md);
  }

  .top-btn:hover:not(:disabled) {
    background: var(--color-bg-input);
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .top-btn.danger:hover:not(:disabled) {
    border-color: var(--color-danger);
    color: var(--color-danger);
    background: var(--color-error-bg);
  }

  .top-link {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-decoration: none;
    padding: 0.42rem 0.55rem;
    border-radius: var(--radius-md);
  }

  .top-link:hover {
    color: var(--color-accent);
    background: var(--color-accent-muted);
  }

  .viewer-control {
    margin: 0;
    min-width: 14rem;
  }

  .viewer-label {
    display: block;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    margin-bottom: 0.15rem;
  }

  .viewer-control select,
  .viewer-control input {
    margin-top: 0;
    padding: 0.32rem 0.5rem;
    font-size: 0.82rem;
  }

  /* ---- grille trois colonnes ---- */

  .hud-grid {
    display: grid;
    grid-template-columns: minmax(260px, 305px) minmax(0, 1fr) minmax(300px, 355px);
    gap: var(--space-md);
    align-items: stretch;
    flex: 1;
    min-height: 0;
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
    flex-direction: column;
    gap: 0.3rem;
  }

  .init-token {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.32rem 0.5rem;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
  }

  .init-token.is-turn {
    border-color: rgb(245 158 11 / 0.5);
    background:
      linear-gradient(90deg, rgb(245 158 11 / 0.1), transparent 70%);
  }

  .init-token.is-inactive {
    opacity: 0.45;
    filter: saturate(0.4);
  }

  .init-rank {
    flex-shrink: 0;
    width: 1.2rem;
    text-align: center;
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  .init-token.is-turn .init-rank {
    color: var(--color-accent);
    font-weight: 700;
  }

  .init-name {
    flex: 1;
    min-width: 0;
    font-size: 0.82rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .init-token.is-turn .init-name {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .init-score {
    flex-shrink: 0;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--color-accent);
    background: rgb(245 158 11 / 0.08);
    border: 1px solid rgb(245 158 11 / 0.3);
    border-radius: var(--radius-sm);
    padding: 0.08rem 0.35rem;
    min-width: 1.6rem;
    text-align: center;
  }

  /* ---- effets ---- */

  .effects-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .effect-row {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    flex-wrap: wrap;
    font-size: 0.8rem;
    padding: 0.3rem 0.45rem;
    border-radius: var(--radius-sm);
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border-subtle);
  }

  .effect-name {
    color: var(--color-accent);
    font-size: 0.76rem;
  }

  .effect-meta {
    margin-left: auto;
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  /* ---- fiche active ---- */

  .active-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .active-id {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .active-name {
    font-family: var(--font-display);
    font-size: 1.05rem;
    letter-spacing: 0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .active-sub {
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .vital-chips {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.45rem;
  }

  .vital {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background:
      linear-gradient(rgb(255 255 255 / 0.015), transparent),
      var(--color-bg-panel);
  }

  .vital-label {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .vital-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .budget-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .budget-chip {
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    color: var(--color-success);
    border: 1px solid rgb(74 222 128 / 0.4);
    background: rgb(34 197 94 / 0.08);
  }

  .budget-chip.used {
    color: var(--color-text-muted);
    border-color: var(--color-border-subtle);
    background: transparent;
    text-decoration: line-through;
    opacity: 0.7;
  }

  .conc-line {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    margin: 0;
    font-size: 0.8rem;
    color: var(--color-accent);
  }

  .conc-line strong {
    color: var(--color-text-primary);
  }

  .conc-id {
    color: var(--color-text-muted);
    font-size: 0.72rem;
  }

  .abilities {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 0.3rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border-subtle);
  }

  .ability {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.05rem;
    padding: 0.3rem 0.1rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    background: var(--color-bg-panel);
  }

  .ability-name {
    font-size: 0.56rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  .ability-value {
    font-family: var(--font-display);
    font-size: 0.85rem;
    color: var(--color-text-muted);
    opacity: 0.6;
  }

  .abilities-note {
    margin: -0.2rem 0 0;
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    text-align: right;
    opacity: 0.7;
  }

  /* ---- actions rapides ---- */

  .action-block {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .action-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-secondary);
  }

  .action-title :global(svg) {
    color: var(--color-accent);
    opacity: 0.85;
  }

  .action-sep {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--color-border-default), transparent);
  }

  .attack-form {
    display: grid;
    gap: 0.4rem;
  }

  .attack-form label {
    margin-bottom: 0;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .attack-form select {
    font-size: 0.84rem;
    text-transform: none;
    letter-spacing: normal;
    font-weight: 400;
  }

  .btn-strike {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    padding: 0.55rem 0.9rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    background: linear-gradient(180deg, var(--color-accent), #d97706);
    color: var(--color-accent-text);
    border: 1px solid #b45309;
    border-radius: var(--radius-md);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.25),
      0 2px 8px rgb(245 158 11 / 0.2);
  }

  .btn-strike:hover:not(:disabled) {
    background: linear-gradient(180deg, var(--color-accent-hover), var(--color-accent));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.25),
      0 2px 12px rgb(245 158 11 / 0.35);
  }

  .spell-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .btn-spell {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.4rem 0.7rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--color-accent);
    background: rgb(245 158 11 / 0.06);
    border: 1px solid rgb(245 158 11 / 0.45);
    border-radius: var(--radius-md);
  }

  .btn-spell:hover:not(:disabled) {
    background: var(--color-accent-muted);
    border-color: var(--color-accent);
  }

  .spell-help {
    font-size: 0.72rem;
    line-height: 1.5;
    opacity: 0.85;
  }

  .btn-skill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.7rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--color-text-muted);
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-md);
  }

  .btn-skill .soon-tag {
    margin-left: auto;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    border: 1px solid rgb(245 158 11 / 0.4);
    background: rgb(245 158 11 / 0.07);
    border-radius: 999px;
    padding: 0.1rem 0.4rem;
  }

  .btn-endturn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    width: 100%;
    padding: 0.6rem 0.9rem;
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-accent);
    background: rgb(245 158 11 / 0.07);
    border: 1px solid var(--color-accent);
    border-radius: var(--radius-md);
    box-shadow: inset 0 0 12px rgb(245 158 11 / 0.05);
  }

  .btn-endturn:hover:not(:disabled) {
    background: var(--color-accent);
    color: var(--color-accent-text);
    box-shadow: 0 2px 14px rgb(245 158 11 / 0.3);
  }

  /* ---- journal ---- */

  .journal-empty {
    font-style: italic;
    opacity: 0.8;
  }

  .journal-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    max-height: 22rem;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--color-border-default) transparent;
  }

  /* ---- responsive ---- */

  @media (max-width: 1280px) {
    .hud-grid {
      grid-template-columns: minmax(240px, 280px) minmax(0, 1fr) minmax(280px, 320px);
    }
  }

  @media (max-width: 1080px) {
    .hud-grid {
      grid-template-columns: 1fr;
    }

    .col-center {
      order: -1;
      min-height: 420px;
    }

    .topbar-controls {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
