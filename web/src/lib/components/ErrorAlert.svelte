<script lang="ts">
  import type { LoadError } from "../types/combat";

  let { error }: { error: LoadError } = $props();
</script>

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
    {:else if error.code === "CHARACTER_NOT_FOUND"}
      <span class="hint">Personnage introuvable — vérifiez le character_id.</span>
    {:else if error.code === "CHARACTER_ALREADY_IN_COMBAT"}
      <span class="hint">Un personnage participe déjà à un combat ouvert.</span>
    {:else if error.code === "INSUFFICIENT_COMBATANTS"}
      <span class="hint">Au moins deux combattants actifs requis pour activer.</span>
    {/if}
  {:else}
    <strong>API injoignable</strong>
    <span>{error.message}</span>
    <span class="hint">
      Terminal 1 (racine du dépôt) :
      <code>venv\Scripts\python.exe -m uvicorn --factory interfaces.api.app:create_app</code>
      — puis relancez l'action.
    </span>
  {/if}
</div>
