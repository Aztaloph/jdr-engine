<script lang="ts">
  import {
    activateCombat,
    createCombat,
    isLoadError,
  } from "../api/combat";
  import type { CombatState, LoadError } from "../types/combat";
  import { navigateToCombat, navigateToCharacter } from "../navigation";
  import ErrorAlert from "../components/ErrorAlert.svelte";

  let characterRows = $state<string[]>(["", ""]);
  let sheetCharacterId = $state("");
  let lobbyCombat = $state<CombatState | null>(null);
  let error = $state<LoadError | null>(null);
  let loading = $state(false);

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

  function addRow() {
    characterRows = [...characterRows, ""];
  }

  function removeRow(index: number) {
    if (characterRows.length <= 1) {
      characterRows = [""];
      return;
    }
    characterRows = characterRows.filter((_, i) => i !== index);
  }

  function nonEmptyCharacterIds(): string[] {
    return characterRows.map((row) => row.trim()).filter(Boolean);
  }

  async function createLobbyCombat() {
    error = null;
    loading = true;
    try {
      lobbyCombat = await createCombat(nonEmptyCharacterIds());
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
</script>

<h1>Lobby — créer une rencontre</h1>
<p class="hint">
  Saisie manuelle des <code>character_id</code> (pas de liste API). Vue MJ —
  les réponses create/activate ne filtrent pas par viewer.
</p>

<fieldset>
  <legend>Combattants</legend>
  <ul class="character-rows">
    {#each characterRows as _row, index (index)}
      <li>
        <label>
          character_id {index + 1}
          <input
            type="text"
            bind:value={characterRows[index]}
            placeholder="ex. e2e_alice"
            autocomplete="off"
          />
        </label>
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
  <label>
    character_id
    <input
      type="text"
      bind:value={sheetCharacterId}
      placeholder="ex. e2e_alice"
      autocomplete="off"
    />
  </label>
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
