<script lang="ts">
  import { fetchCharacterSheet } from "../api/sheet";
  import { isLoadError } from "../api/combat";
  import type { LoadError } from "../types/combat";
  import {
    ABILITY_IDS,
    type AbilityId,
    type CharacterSheet,
  } from "../types/sheet";
  import ErrorAlert from "../components/ErrorAlert.svelte";

  let {
    params = {},
    onRouteEvent: _onRouteEvent,
  }: {
    params?: { id?: string | null };
    onRouteEvent?: (detail: unknown) => void;
  } = $props();

  const characterId = $derived(params.id ?? "");

  let sheet = $state<CharacterSheet | null>(null);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);

  const savingThrowsOrdered = $derived.by(() => {
    if (!sheet) {
      return [];
    }
    const byId = new Map(
      sheet.saving_throws.map((entry) => [entry.ability_id, entry]),
    );
    return ABILITY_IDS.map((id) => byId.get(id)).filter(
      (entry): entry is NonNullable<typeof entry> => entry !== undefined,
    );
  });

  $effect(() => {
    const id = characterId;
    void loadSheet(id);
  });

  function abilityLabel(sheetData: CharacterSheet, abilityId: AbilityId): string {
    return sheetData.ability_labels[abilityId] ?? abilityId.toUpperCase();
  }

  function formatModifier(mod: number): string {
    return mod >= 0 ? `+${mod}` : String(mod);
  }

  async function loadSheet(id: string) {
    if (!id.trim()) {
      sheet = null;
      error = { kind: "network", message: "character_id requis." };
      return;
    }

    error = null;
    loading = true;
    try {
      sheet = await fetchCharacterSheet(id);
    } catch (e) {
      sheet = null;
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function reload() {
    await loadSheet(characterId);
  }
</script>

<h1>Fiche personnage</h1>
<p class="hint">
  character_id <span class="mono">{characterId || "—"}</span> —
  <code>GET /v1/characters/…/sheet</code>
</p>

<div class="actions">
  <button type="button" onclick={reload} disabled={loading || !characterId.trim()}>
    {loading ? "Chargement…" : "Recharger"}
  </button>
</div>

{#if error}
  <ErrorAlert {error} />
{/if}

{#if sheet}
  <section class="sheet-identity" aria-live="polite">
    <h2>{sheet.name}</h2>
    <p class="sheet-meta">
      {sheet.race_name} · {sheet.class_name} · niv. {sheet.level}
      · bonus de maîtrise {formatModifier(sheet.proficiency_bonus)}
    </p>
    <p class="hint mono">id {sheet.character_id}</p>
  </section>

  <section class="sheet-vitals">
    <h2>Vitalité et défense</h2>
    <dl class="meta">
      <div>
        <dt>PV</dt>
        <dd>{sheet.hp_current} / {sheet.hp_max}</dd>
      </div>
      <div>
        <dt>CA</dt>
        <dd>{sheet.ac}</dd>
      </div>
    </dl>
  </section>

  <section class="sheet-abilities">
    <h2>Caractéristiques</h2>
    <ul class="ability-grid">
      {#each ABILITY_IDS as abilityId (abilityId)}
        <li>
          <span class="ability-label">{abilityLabel(sheet, abilityId)}</span>
          <span class="ability-score">{sheet.ability_scores[abilityId] ?? "—"}</span>
          <span class="ability-mod">
            {formatModifier(sheet.ability_modifiers[abilityId] ?? 0)}
          </span>
        </li>
      {/each}
    </ul>
  </section>

  <section class="sheet-saves">
    <h2>Jets de sauvegarde</h2>
    <ul class="save-list">
      {#each savingThrowsOrdered as entry (entry.ability_id)}
        <li class:proficient={entry.proficient}>
          <span class="save-label">{abilityLabel(sheet, entry.ability_id)}</span>
          <span class="save-mod mono">{formatModifier(entry.modifier)}</span>
          {#if entry.proficient}
            <span class="save-mark" aria-label="maîtrise">●</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>

  <section class="sheet-skills">
    <h2>Compétences maîtrisées</h2>
    {#if sheet.proficient_skills.length === 0}
      <p class="hint">Aucune compétence maîtrisée.</p>
    {:else}
      <ul class="skill-list">
        {#each sheet.proficient_skills as skill (skill.id)}
          <li>
            <span>{skill.label}</span>
            <span class="mono hint">({skill.id})</span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  {#if sheet.active_effects !== undefined && sheet.active_effects.length > 0}
    <section class="effects">
      <h2>Effets actifs (combat)</h2>
      <ul>
        {#each sheet.active_effects as effect (effect.effect_id + effect.target_id + effect.applied_at_round)}
          <li>
            <span class="mono">{effect.effect_id}</span> — source {effect.source_id},
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
{/if}
