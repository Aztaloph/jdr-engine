<script lang="ts">
  import {
    advanceCombatTurn,
    closeCombat,
    fetchCombatJournal,
    fetchCombatState,
    healCombatant,
    isLoadError,
    postCombatCast,
    postWeaponAttack,
    syncCombatantFromSheet,
  } from "../api/combat";
  import { postLongRest } from "../api/characters";
  import {
    applyPreparedSpells,
    fetchPreparedSpells,
  } from "../api/prepared_spells";
  import type {
    AbilityId,
    ActiveEffect,
    Combatant,
    CombatState,
    LoadError,
  } from "../types/combat";
  import { COMBAT_ABILITY_IDS } from "../types/combat";
  import type { PreparedSpellsView } from "../types/prepared_spells";
  import {
    WEAPON_IDS,
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
    kind: "attack" | "spell" | "system";
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
  const castableBonusSpells = $derived(
    combat?.viewer?.castable_bonus_spells ?? [],
  );
  const castableReactionSpells = $derived(
    combat?.viewer?.castable_reaction_spells ?? [],
  );
  const OVERLAY_SPELL_IDS = new Set(["hex", "bless", "shield"]);
  const overlayCastableSpells = $derived(
    castableSpells.filter((id) => OVERLAY_SPELL_IDS.has(id)),
  );
  const resolvedCastableSpells = $derived(
    castableSpells.filter((id) => !OVERLAY_SPELL_IDS.has(id)),
  );
  const viewerSpellcasting = $derived(combat?.viewer?.spellcasting ?? null);
  const preparedRechoicePending = $derived(
    viewerSpellcasting?.prepared_rechoice_pending === true,
  );
  let preparedContext = $state<PreparedSpellsView | null>(null);
  let selectedPrepared = $state<string[]>([]);
  let preparedLoading = $state(false);
  const canConfirmPrepared = $derived(
    preparedContext?.quota != null &&
      selectedPrepared.length === preparedContext.quota &&
      !loading &&
      !preparedLoading,
  );
  const spellSlotLevels = $derived.by(() => {
    const sc = viewerSpellcasting;
    if (!sc?.slots_max) {
      return [] as string[];
    }
    return Object.keys(sc.slots_max).sort(
      (a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10),
    );
  });

  /** Sorts niv. 1+ préparés du viewer (hors cantrips) — affichage aide HUD. */
  const viewerPreparedLeveled = $derived.by(() => {
    const sc = viewerSpellcasting;
    if (!sc) {
      return [] as string[];
    }
    const cantrips = new Set(sc.cantrips_known ?? []);
    const prepared = sc.spells_prepared ?? sc.spells_known ?? [];
    return prepared.filter((id) => !cantrips.has(id));
  });

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

  const canCastReactionSpell = $derived(
    combat !== null &&
      combat.status === "active" &&
      combat.viewer?.combatant_id != null &&
      !loading,
  );

  const canRevive = $derived(
    combat !== null && combat.status === "active" && targetId !== "" && !loading,
  );

  const dmTargetCharacterId = $derived(
    combat && targetId ? combat.combatants[targetId]?.character_id ?? "" : "",
  );

  const currentTurnCombatant = $derived(
    combat && combat.current_combatant_id
      ? combat.combatants[combat.current_combatant_id]
      : undefined,
  );

  /** Fiche droite : viewer joueur si défini, sinon combattant au tour. */
  const sheetCombatant = $derived.by(() => {
    if (!combat) {
      return undefined;
    }
    const viewerCid = combat.viewer?.combatant_id;
    if (viewer.trim() && viewerCid && combat.combatants[viewerCid]) {
      return combat.combatants[viewerCid];
    }
    return currentTurnCombatant;
  });

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

  $effect(() => {
    const characterId = viewer.trim();
    const pending = preparedRechoicePending;
    if (characterId && pending) {
      void loadPreparedContext(characterId);
    } else {
      preparedContext = null;
      selectedPrepared = [];
    }
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
    void syncJournalFromServer();
  }

  async function syncJournalFromServer() {
    if (!combatId.trim()) {
      return;
    }
    try {
      const entries = await fetchCombatJournal(combatId);
      journal = entries.map((entry) => ({
        id: entry.log_id,
        kind: entry.kind,
        summary: entry.summary,
        detail: entry.detail,
        time: new Date(entry.created_at).toLocaleTimeString("fr-FR", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      }));
    } catch {
      /* journal non bloquant */
    }
  }

  function pushJournal(entry: Omit<JournalEntry, "id" | "time">) {
    journalSeq += 1;
    const time = new Date().toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    journal = [{ ...entry, id: journalSeq, time }, ...journal];
  }

  function formatModifier(value: number): string {
    return value >= 0 ? `+${value}` : String(value);
  }

  function abilityLabel(combatant: Combatant, abilityId: AbilityId): string {
    return combatant.ability_labels?.[abilityId] ?? abilityId.toUpperCase();
  }

  function hasAbilityBlock(combatant: Combatant): boolean {
    return combatant.ability_scores !== undefined;
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

  async function loadPreparedContext(characterId: string) {
    preparedLoading = true;
    try {
      const ctx = await fetchPreparedSpells(characterId);
      preparedContext = ctx;
      const pool = new Set(ctx.pool ?? []);
      selectedPrepared = (ctx.spells_prepared ?? []).filter((id) => pool.has(id));
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      preparedLoading = false;
    }
  }

  function togglePreparedSpell(spellId: string) {
    if (!preparedContext?.quota) {
      return;
    }
    if (selectedPrepared.includes(spellId)) {
      selectedPrepared = selectedPrepared.filter((id) => id !== spellId);
      return;
    }
    if (selectedPrepared.length >= preparedContext.quota) {
      return;
    }
    selectedPrepared = [...selectedPrepared, spellId];
  }

  async function confirmPreparedSpells() {
    if (!viewer.trim() || !canConfirmPrepared) {
      return;
    }
    error = null;
    preparedLoading = true;
    loading = true;
    const selection = [...selectedPrepared];
    const name =
      combat?.viewer?.combatant_id != null && combat
        ? combatantName(combat.viewer.combatant_id, combat)
        : viewer.trim();
    try {
      await applyPreparedSpells(viewer.trim(), { spell_ids: selection });
      preparedContext = null;
      selectedPrepared = [];
      applyCombatState(await fetchCombatState(combatId, viewer));
      pushJournal({
        kind: "spell",
        summary: `${name} — sorts préparés confirmés`,
        detail: selection.join(", "),
      });
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      preparedLoading = false;
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

  async function launchAttack() {
    if (!canAttack || !combat) {
      return;
    }
    error = null;
    loading = true;
    try {
      await postWeaponAttack(
        combatId,
        {
          attacker_id: attackerId,
          target_id: targetId,
          weapon_id: weaponId,
        },
        viewer,
      );
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
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function reviveCombatant() {
    if (!canRevive || !combat) {
      return;
    }
    error = null;
    loading = true;
    const tgt = targetId;
    try {
      const next = await healCombatant(combatId, tgt, viewer);
      applyCombatState(next);
      pushJournal({
        kind: "system",
        summary: `${combatantName(tgt, next)} réanimé (PV max)`,
        detail: "Outil MJ · heal",
      });
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function runLongRestForTarget() {
    if (!canRevive || !combat || !dmTargetCharacterId) {
      return;
    }
    error = null;
    loading = true;
    const tgt = targetId;
    const charId = dmTargetCharacterId;
    try {
      await postLongRest(charId);
      const next = await syncCombatantFromSheet(combatId, tgt, viewer);
      applyCombatState(next);
      if (viewer.trim() === charId) {
        await loadPreparedContext(charId);
      }
      pushJournal({
        kind: "system",
        summary: `Repos long — ${combatantName(tgt, next)}`,
        detail:
          viewer.trim() === charId
            ? "Préparation de sorts disponible si classe préparateur."
            : `Sélectionnez le viewer ${charId.slice(0, 8)}… pour préparer les sorts.`,
      });
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function launchReactionSpell(spellId: string) {
    if (!canCastReactionSpell || !combat?.viewer?.combatant_id) {
      return;
    }
    error = null;
    loading = true;
    const casterId = combat.viewer.combatant_id;
    try {
      const next = await postCombatCast(
        combatId,
        {
          caster_id: casterId,
          spell_id: spellId,
          target_ids: [],
        },
        viewer,
      );
      applyCombatState(next);
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
          {#if sheetCombatant}
            <div class="active-head">
              <CharacterPortrait name={sheetCombatant.display_name} size={44} active />
              <div class="active-id">
                <strong class="active-name">{sheetCombatant.display_name}</strong>
                <span class="active-sub">
                  {#if sheetCombatant.class_name != null && sheetCombatant.level != null}
                    {sheetCombatant.race_name
                      ? `${sheetCombatant.race_name} · `
                      : ""}{sheetCombatant.class_name} · niv. {sheetCombatant.level}
                  {/if}
                  {#if viewer.trim() && combat?.viewer?.combatant_id && combat.current_combatant_id !== combat.viewer.combatant_id && currentTurnCombatant}
                    {#if sheetCombatant.class_name != null && sheetCombatant.level != null}
                      ·
                    {/if}
                    Tour de {currentTurnCombatant.display_name}
                  {/if}
                </span>
              </div>
            </div>

            <div class="vital-chips">
              <div class="vital">
                <span class="vital-label">PV</span>
                <span class="vital-value mono">
                  {sheetCombatant.hp_current !== undefined
                    ? `${sheetCombatant.hp_current}${sheetCombatant.hp_max !== undefined ? ` / ${sheetCombatant.hp_max}` : ""}`
                    : "—"}
                </span>
              </div>
              <div class="vital">
                <span class="vital-label">CA</span>
                <span class="vital-value mono">
                  {sheetCombatant.ac !== undefined ? sheetCombatant.ac : "—"}
                </span>
              </div>
            </div>

            {#if sheetCombatant.action_budget}
              {@const b = sheetCombatant.action_budget}
              <div class="budget-chips">
                <span class="budget-chip" class:used={!b.has_action}>Action</span>
                <span class="budget-chip" class:used={!b.has_bonus_action}>Bonus</span>
                <span class="budget-chip" class:used={!b.has_reaction}>Réaction</span>
                <span class="budget-chip" class:used={!b.has_movement}>Mouvement</span>
              </div>
            {:else}
              <p class="hint">Budget d'action non exposé pour ce combattant.</p>
            {/if}

            {#if sheetCombatant.concentration_spell_name}
              <p class="conc-line">
                <Icon name="sparkle" size={12} />
                Concentration : <strong>{sheetCombatant.concentration_spell_name}</strong>
                {#if sheetCombatant.concentration_spell_id}
                  <span class="mono conc-id">({sheetCombatant.concentration_spell_id})</span>
                {/if}
              </p>
            {/if}

            {#if hasAbilityBlock(sheetCombatant)}
              <div class="abilities">
                {#each COMBAT_ABILITY_IDS as abilityId (abilityId)}
                  <div class="ability">
                    <span class="ability-name">
                      {abilityLabel(sheetCombatant, abilityId)}
                    </span>
                    <span class="ability-value">
                      {sheetCombatant.ability_scores?.[abilityId] ?? "—"}
                    </span>
                    <span class="ability-mod">
                      {formatModifier(
                        sheetCombatant.ability_modifiers?.[abilityId] ?? 0,
                      )}
                    </span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="hint abilities-hidden">
                Caractéristiques non exposées pour ce combattant (vue joueur).
              </p>
            {/if}
          {:else}
            <p class="hint">Aucun tour actif.</p>
          {/if}
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
              {#if viewer.trim() && combat.viewer?.combatant_id}
                <p class="spell-viewer-label">
                  Personnage : <strong>{combatantName(combat.viewer.combatant_id, combat)}</strong>
                  {#if !isViewerTurn}
                    · hors tour (réactions disponibles)
                  {/if}
                </p>
              {/if}
              {#if viewerSpellcasting && spellSlotLevels.length > 0}
                <div class="spell-slots" aria-label="Emplacements de sorts">
                  {#each spellSlotLevels as level (level)}
                    {@const max = viewerSpellcasting.slots_max[level] ?? 0}
                    {@const remaining = viewerSpellcasting.slots_remaining[level] ?? 0}
                    <span
                      class="slot-chip"
                      class:slot-chip-empty={remaining === 0}
                      title="Emplacements niveau {level}"
                    >
                      niv.{level} · {remaining}/{max}
                    </span>
                  {/each}
                </div>
              {/if}
              {#if overlayCastableSpells.length > 0}
                <p class="spell-section-label">Overlay (buff / marque)</p>
                <div class="spell-actions">
                  {#each overlayCastableSpells as spellId (spellId)}
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
              {/if}
              {#if castableBonusSpells.length > 0}
                <p class="spell-section-label">Action bonus</p>
                <div class="spell-actions">
                  {#each castableBonusSpells as spellId (spellId)}
                    <button
                      type="button"
                      class="btn-spell btn-spell-bonus"
                      onclick={() => launchSpell(spellId)}
                      disabled={!canCastSpell}
                    >
                      <Icon name="sparkle" size={12} />
                      {spellId}
                    </button>
                  {/each}
                </div>
              {/if}
              {#if resolvedCastableSpells.length > 0}
                <p class="spell-section-label">Attaque / sauvegarde</p>
                <div class="spell-actions">
                  {#each resolvedCastableSpells as spellId (spellId)}
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
              {/if}
              {#if castableReactionSpells.length > 0}
                <p class="spell-section-label">Réaction</p>
                <div class="spell-actions">
                  {#each castableReactionSpells as spellId (spellId)}
                    <button
                      type="button"
                      class="btn-spell btn-spell-reaction"
                      onclick={() => launchReactionSpell(spellId)}
                      disabled={!canCastReactionSpell}
                    >
                      <Icon name="sparkle" size={12} />
                      {spellId}
                    </button>
                  {/each}
                </div>
              {/if}
              {#if castableSpells.length === 0 && castableBonusSpells.length === 0 && castableReactionSpells.length === 0}
                {#if viewer.trim()}
                  {#if combat.viewer?.combatant_id == null}
                    <p class="hint">Ce viewer ne participe pas à ce combat.</p>
                  {:else if !isViewerTurn}
                    <p class="hint">
                      Ce n'est pas le tour de {combatantName(combat.viewer.combatant_id, combat)}
                      — sorts d'action indisponibles ; réactions si budget disponible.
                    </p>
                  {:else}
                    <p class="hint">
                      Aucun sort lançable maintenant — vérifiez tour propre, préparation
                      et emplacements.
                    </p>
                  {/if}
                {:else}
                  <p class="hint">
                    Choisissez un viewer (en haut) pour activer les sorts joueur.
                  </p>
                {/if}
              {/if}
              {#if viewerSpellcasting && viewerPreparedLeveled.length > 0}
                <p class="hint spell-help">
                  Préparés (niv. 1+) :
                  {#each viewerPreparedLeveled as spellId, i (spellId)}
                    {#if i > 0} · {/if}<code>{spellId}</code>
                  {/each}.
                  Seuls les sorts combat (attaque, sauvegarde, overlay) ont un bouton —
                  ex. <code>detect_magic</code> ou <code>cure_wounds</code> n’apparaissent pas ici.
                </p>
              {:else if viewer.trim() && viewerSpellcasting}
                <p class="hint spell-help">
                  Aucun sort niv. 1+ préparé sur cette fiche.
                </p>
              {/if}
            </div>

            {#if preparedRechoicePending && preparedContext?.pool}
              <div class="action-sep" aria-hidden="true"></div>
              <div class="action-block prepared-block">
                <h3 class="action-title">
                  <Icon name="sparkle" size={12} />
                  Préparer les sorts
                </h3>
                <p class="prepared-banner">
                  Repos long effectué — choisissez
                  <strong>{preparedContext.quota}</strong> sort(s) préparé(s).
                </p>
                {#if preparedContext.pool_capped_notice}
                  <p class="hint prepared-capped">{preparedContext.pool_capped_notice}</p>
                {/if}
                {#if preparedContext.domain_spells && preparedContext.domain_spells.length > 0}
                  <p class="hint prepared-domain">
                    Domaine (toujours préparés) :
                    {#each preparedContext.domain_spells as spellId (spellId)}
                      <code>{spellId}</code>
                    {/each}
                  </p>
                {/if}
                {#if preparedContext.paladin_no_slots_notice}
                  <p class="hint">{preparedContext.paladin_no_slots_notice}</p>
                {/if}
                <p class="prepared-count">
                  Sélection :
                  <strong>{selectedPrepared.length}/{preparedContext.quota}</strong>
                </p>
                <div class="prepared-pool">
                  {#each preparedContext.pool as spellId (spellId)}
                    <button
                      type="button"
                      class="btn-prepared"
                      class:btn-prepared-active={selectedPrepared.includes(spellId)}
                      onclick={() => togglePreparedSpell(spellId)}
                      disabled={preparedLoading ||
                        loading ||
                        (!selectedPrepared.includes(spellId) &&
                          selectedPrepared.length >= (preparedContext.quota ?? 0))}
                    >
                      {spellId}
                    </button>
                  {/each}
                </div>
                <button
                  type="button"
                  class="btn-confirm-prepared"
                  onclick={confirmPreparedSpells}
                  disabled={!canConfirmPrepared}
                >
                  {preparedLoading ? "Enregistrement…" : "Confirmer la préparation"}
                </button>
              </div>
            {/if}

            <div class="action-sep" aria-hidden="true"></div>

            <div class="action-block dm-tools">
              <h3 class="action-title">
                <Icon name="wand" size={12} />
                Outils MJ (banc de test)
              </h3>
              <p class="hint dm-hint">
                Utilise la cible sélectionnée ci-dessus. Pour la préparation de sorts :
                choisissez le viewer du personnage, puis « Repos long ».
              </p>
              <div class="dm-actions">
                <button
                  type="button"
                  class="btn-dm"
                  onclick={reviveCombatant}
                  disabled={!canRevive}
                >
                  Réanimer (PV max)
                </button>
                <button
                  type="button"
                  class="btn-dm"
                  onclick={runLongRestForTarget}
                  disabled={!canRevive || !dmTargetCharacterId}
                >
                  Repos long
                </button>
              </div>
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
    color: var(--color-text-primary);
  }

  .ability-mod {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  .abilities-hidden {
    margin: 0.35rem 0 0;
    font-size: 0.75rem;
    font-style: italic;
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

  .spell-section-label {
    margin: 0.35rem 0 0.25rem;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .spell-viewer-label {
    margin: 0 0 0.35rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .prepared-block {
    border: 1px solid rgb(245 158 11 / 0.45);
    border-radius: var(--radius-md);
    padding: 0.55rem 0.6rem;
    background: rgb(245 158 11 / 0.06);
  }

  .dm-tools {
    border: 1px dashed rgb(148 163 184 / 0.35);
    border-radius: var(--radius-md);
    padding: 0.55rem 0.6rem;
  }

  .dm-hint {
    margin: 0 0 0.5rem;
    font-size: 0.72rem;
    line-height: 1.4;
  }

  .dm-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .btn-dm {
    flex: 1 1 auto;
    min-width: 7rem;
    padding: 0.4rem 0.55rem;
    font-size: 0.75rem;
    border: 1px solid rgb(148 163 184 / 0.45);
    border-radius: var(--radius-sm);
    background: rgb(15 23 42 / 0.55);
    color: var(--color-text);
    cursor: pointer;
  }

  .btn-dm:hover:not(:disabled) {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .btn-dm:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .prepared-banner {
    margin: 0 0 0.45rem;
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--color-accent);
  }

  .prepared-domain code {
    margin-right: 0.35rem;
  }

  .prepared-count {
    margin: 0.35rem 0;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .prepared-pool {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.5rem;
  }

  .btn-prepared {
    padding: 0.3rem 0.55rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--color-text-muted);
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border-default);
    border-radius: var(--radius-sm);
  }

  .btn-prepared-active {
    color: var(--color-accent);
    background: rgb(245 158 11 / 0.12);
    border-color: rgb(245 158 11 / 0.55);
  }

  .btn-confirm-prepared {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 0.45rem 0.7rem;
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--color-bg-panel);
    background: linear-gradient(180deg, var(--color-accent-hover), var(--color-accent));
    border: none;
    border-radius: var(--radius-md);
  }

  .btn-confirm-prepared:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .spell-slots {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.45rem;
  }

  .slot-chip {
    font-size: 0.72rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    padding: 0.2rem 0.45rem;
    border-radius: var(--radius-sm);
    color: var(--color-accent);
    background: rgb(245 158 11 / 0.08);
    border: 1px solid rgb(245 158 11 / 0.35);
  }

  .slot-chip-empty {
    opacity: 0.55;
    color: var(--color-text-muted);
    border-color: var(--color-border-default);
    background: var(--color-bg-panel);
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

  .btn-spell-reaction {
    color: rgb(96 165 250);
    background: rgb(96 165 250 / 0.08);
    border-color: rgb(96 165 250 / 0.45);
  }

  .btn-spell-reaction:hover:not(:disabled) {
    background: rgb(96 165 250 / 0.14);
    border-color: rgb(96 165 250);
  }

  .btn-spell-bonus {
    color: rgb(52 211 153);
    background: rgb(52 211 153 / 0.08);
    border-color: rgb(52 211 153 / 0.45);
  }

  .btn-spell-bonus:hover:not(:disabled) {
    background: rgb(52 211 153 / 0.14);
    border-color: rgb(52 211 153);
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
