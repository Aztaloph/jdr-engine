<script lang="ts">
  import {
    activateCombat,
    closeCombat,
    createCombat,
    fetchOpenCombats,
    isLoadError,
    type OpenCombatSummary,
  } from "../api/combat";
  import { fetchCharacterList } from "../api/characters";
  import type { CharacterListEntry } from "../types/character";
  import type { CombatState, LoadError } from "../types/combat";
  import { navigateToCombat, navigateToCharacter } from "../navigation";
  import ErrorAlert from "../components/ErrorAlert.svelte";

  let characterRows = $state<string[]>(["", ""]);
  let manualRows = $state<boolean[]>([false, false]);
  let sheetCharacterId = $state("");
  let sheetManual = $state(false);
  let characterOptions = $state<CharacterListEntry[]>([]);
  let listError = $state<string | null>(null);
  let lobbyCombat = $state<CombatState | null>(null);
  let openCombats = $state<OpenCombatSummary[]>([]);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);

  const hasCharacterList = $derived(characterOptions.length > 0);

  const canCreate = $derived(
    !loading &&
      characterRows.some((row) => row.trim().length > 0),
  );

  const canActivate = $derived(
    lobbyCombat !== null &&
      lobbyCombat.status === "preparing" &&
      lobbyCombat.combat_id !== null &&
      !loading,
  );

  $effect(() => {
    void loadCharacterOptions();
    void loadOpenCombats();
  });

  async function loadOpenCombats() {
    try {
      openCombats = await fetchOpenCombats();
    } catch {
      openCombats = [];
    }
  }

  async function loadCharacterOptions() {
    listError = null;
    try {
      characterOptions = await fetchCharacterList();
    } catch (e) {
      characterOptions = [];
      listError = isLoadError(e)
        ? e.message
        : "Impossible de charger la liste des personnages.";
    }
  }

  function characterOptionLabel(entry: CharacterListEntry): string {
    return `${entry.name} (${entry.character_id}) — ${entry.class_id} niv.${entry.level}`;
  }

  function addRow() {
    characterRows = [...characterRows, ""];
    manualRows = [...manualRows, false];
  }

  function removeRow(index: number) {
    if (characterRows.length <= 1) {
      characterRows = [""];
      manualRows = [false];
      return;
    }
    characterRows = characterRows.filter((_, i) => i !== index);
    manualRows = manualRows.filter((_, i) => i !== index);
  }

  function toggleManualRow(index: number) {
    manualRows[index] = !manualRows[index];
  }

  function nonEmptyCharacterIds(): string[] {
    return characterRows.map((row) => row.trim()).filter(Boolean);
  }

  async function createLobbyCombat() {
    error = null;
    loading = true;
    try {
      lobbyCombat = await createCombat(nonEmptyCharacterIds());
      await loadOpenCombats();
    } catch (e) {
      lobbyCombat = null;
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  async function activateLobbyCombat() {
    if (!lobbyCombat?.combat_id) {
      return;
    }
    error = null;
    loading = true;
    try {
      const activated = await activateCombat(String(lobbyCombat.combat_id));
      lobbyCombat = activated;
      navigateToCombat(activated.combat_id!);
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  function openCombatReadOnly() {
    if (lobbyCombat?.combat_id != null) {
      navigateToCombat(lobbyCombat.combat_id);
    }
  }

  function openCharacterSheet() {
    navigateToCharacter(sheetCharacterId);
  }

  async function closeOpenCombat(combatId: number) {
    error = null;
    loading = true;
    try {
      await closeCombat(String(combatId));
      if (lobbyCombat?.combat_id === combatId) {
        lobbyCombat = null;
      }
      await loadOpenCombats();
    } catch (e) {
      error = isLoadError(e) ? e : { kind: "network", message: String(e) };
    } finally {
      loading = false;
    }
  }

  function participantNames(entry: OpenCombatSummary): string {
    return entry.participants.map((p) => p.display_name).join(", ");
  }
</script>

<h1>Lobby — créer une rencontre</h1>
<p class="hint">
  Choisissez les personnages dans la liste (API <code>GET /v1/characters</code>)
  ou basculez en saisie manuelle. Vue MJ — create/activate sans filtre viewer.
</p>

{#if listError}
  <p class="hint" role="status">
    Liste indisponible : {listError}. Terminal :
    <code>venv\Scripts\python.exe tools\list_characters.py</code>
  </p>
{:else if hasCharacterList}
  <p class="hint" role="status">{characterOptions.length} personnage(s) en base.</p>
{/if}

<fieldset>
  <legend>Combats ouverts — libérer les personnages</legend>
  {#if openCombats.length === 0}
    <p class="hint">Aucun combat ouvert. Vos personnages sont disponibles pour un nouveau lobby.</p>
  {:else}
    <ul class="open-combats-list">
      {#each openCombats as entry (entry.combat_id)}
        <li>
          <div>
            <strong>Combat {entry.combat_id}</strong>
            <span class="hint"> — {entry.status} · {participantNames(entry)}</span>
          </div>
          <div class="open-combat-actions">
            <button type="button" class="linkish" onclick={() => navigateToCombat(entry.combat_id)} disabled={loading}>
              Ouvrir
            </button>
            <button type="button" onclick={() => closeOpenCombat(entry.combat_id)} disabled={loading}>
              Clôturer
            </button>
          </div>
        </li>
      {/each}
    </ul>
    <p class="hint">
      Clôturer un combat synchronise les PV sur la fiche et libère les personnages pour retester.
    </p>
  {/if}
</fieldset>

<fieldset>
  <legend>Combattants</legend>
  <ul class="character-rows">
    {#each characterRows as _row, index (index)}
      <li>
        {#if hasCharacterList && !manualRows[index]}
          <label>
            Personnage {index + 1}
            <select bind:value={characterRows[index]}>
              <option value="">— Choisir —</option>
              {#each characterOptions as entry (entry.character_id)}
                <option value={entry.character_id}>
                  {characterOptionLabel(entry)}
                </option>
              {/each}
            </select>
          </label>
          <button
            type="button"
            class="linkish row-toggle"
            onclick={() => toggleManualRow(index)}
          >
            Saisie manuelle
          </button>
        {:else}
          <label>
            character_id {index + 1}
            <input
              type="text"
              bind:value={characterRows[index]}
              placeholder="ex. 1715ef0a"
              autocomplete="off"
            />
          </label>
          {#if hasCharacterList}
            <button
              type="button"
              class="linkish row-toggle"
              onclick={() => toggleManualRow(index)}
            >
              Liste déroulante
            </button>
          {/if}
        {/if}
        <button
          type="button"
          class="row-remove"
          onclick={() => removeRow(index)}
          aria-label="Retirer la ligne"
        >
          Retirer
        </button>
      </li>
    {/each}
  </ul>
  <button type="button" class="linkish" onclick={addRow}>+ Ajouter un personnage</button>
</fieldset>

<fieldset>
  <legend>Consulter une fiche</legend>
  {#if hasCharacterList && !sheetManual}
    <label>
      Personnage
      <select bind:value={sheetCharacterId}>
        <option value="">— Choisir —</option>
        {#each characterOptions as entry (entry.character_id)}
          <option value={entry.character_id}>
            {characterOptionLabel(entry)}
          </option>
        {/each}
      </select>
    </label>
    <button type="button" class="linkish" onclick={() => (sheetManual = true)}>
      Saisie manuelle
    </button>
  {:else}
    <label>
      character_id
      <input
        type="text"
        bind:value={sheetCharacterId}
        placeholder="ex. 1715ef0a"
        autocomplete="off"
      />
    </label>
    {#if hasCharacterList}
      <button type="button" class="linkish" onclick={() => (sheetManual = false)}>
        Liste déroulante
      </button>
    {/if}
  {/if}
  <div class="actions">
    <button
      type="button"
      onclick={openCharacterSheet}
      disabled={loading || !sheetCharacterId.trim()}
    >
      Ouvrir la fiche
    </button>
  </div>
</fieldset>

<div class="actions">
  <button type="button" onclick={createLobbyCombat} disabled={!canCreate}>
    {loading ? "Création…" : "Créer le combat"}
  </button>
  {#if lobbyCombat?.combat_id != null}
    <button type="button" onclick={activateLobbyCombat} disabled={!canActivate}>
      {loading ? "Activation…" : "Activer et jouer"}
    </button>
    <button type="button" onclick={openCombatReadOnly} disabled={loading}>
      Ouvrir sans activer
    </button>
  {/if}
</div>

{#if error}
  <ErrorAlert {error} />
{/if}

{#if lobbyCombat}
  <section class="lobby-result" aria-live="polite">
    <h2>Rencontre créée</h2>
    <dl class="meta">
      <div>
        <dt>combat_id</dt>
        <dd>{lobbyCombat.combat_id ?? "—"}</dd>
      </div>
      <div>
        <dt>status</dt>
        <dd>{lobbyCombat.status}</dd>
      </div>
      <div>
        <dt>combattants</dt>
        <dd>{Object.keys(lobbyCombat.combatants).length}</dd>
      </div>
    </dl>
    {#if lobbyCombat.status === "preparing"}
      <p class="hint">
        Statut <code>preparing</code> — activez pour lancer l'initiative et accéder
        au combat.
      </p>
    {/if}
  </section>
{/if}
