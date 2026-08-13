<script lang="ts">
  import Icon from "./Icon.svelte";
  import type { CombatState, Combatant } from "../../types/combat";

  let {
    combat,
    viewer = "",
    loading = false,
    onMove,
    onSelectTarget,
  }: {
    combat: CombatState;
    viewer?: string;
    loading?: boolean;
    onMove: (x: number, y: number) => void;
    onSelectTarget?: (combatantId: string) => void;
  } = $props();

  const viewerCombatantId = $derived(combat.viewer?.combatant_id ?? null);

  const currentBudget = $derived.by(() => {
    const cid = combat.current_combatant_id;
    if (!cid) {
      return undefined;
    }
    return combat.combatants[cid]?.action_budget;
  });

  const canMove = $derived(
    combat.status === "active" &&
      !loading &&
      viewerCombatantId != null &&
      combat.current_combatant_id === viewerCombatantId &&
      (currentBudget?.movement_remaining_ft ?? 0) > 0,
  );

  const cells = $derived.by(() => {
    const grid = combat.grid;
    if (!grid) {
      return [] as Array<{ x: number; y: number }>;
    }
    const result: Array<{ x: number; y: number }> = [];
    for (let y = 0; y < grid.height; y += 1) {
      for (let x = 0; x < grid.width; x += 1) {
        result.push({ x, y });
      }
    }
    return result;
  });

  const tokenByCell = $derived.by(() => {
    const map = new Map<string, Combatant>();
    for (const combatant of Object.values(combat.combatants)) {
      const pos = combatant.position;
      if (pos != null) {
        map.set(`${pos.x},${pos.y}`, combatant);
      }
    }
    return map;
  });

  function columnLabel(index: number): string {
    let n = index;
    let label = "";
    do {
      label = String.fromCharCode(65 + (n % 26)) + label;
      n = Math.floor(n / 26) - 1;
    } while (n >= 0);
    return label;
  }

  function tokenSide(combatant: Combatant): "self" | "other" {
    const viewerId = viewer.trim();
    if (viewerId && combatant.character_id === viewerId) {
      return "self";
    }
    return "other";
  }

  function combatantAt(x: number, y: number): Combatant | undefined {
    return tokenByCell.get(`${x},${y}`);
  }

  function handleCellClick(x: number, y: number) {
    const occupant = combatantAt(x, y);
    if (occupant) {
      if (onSelectTarget && occupant.combatant_id !== viewerCombatantId) {
        onSelectTarget(occupant.combatant_id);
      }
      return;
    }
    if (canMove) {
      onMove(x, y);
    }
  }

  function initials(name: string): string {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) {
      return "?";
    }
    if (parts.length === 1) {
      return parts[0].slice(0, 2).toUpperCase();
    }
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
</script>

<section class="map" aria-label="Carte tactique">
  <header class="map-head">
    <span class="map-title">
      <Icon name="map" size={13} />
      Carte tactique
    </span>
    <div class="map-tools">
      <button type="button" class="tool" disabled title="Vision — à venir">
        <Icon name="eye" size={12} />
        Vision
      </button>
      <button type="button" class="tool" disabled title="Mesure — à venir">
        <Icon name="grid" size={12} />
        Mesure
      </button>
      {#if combat.grid}
        <span class="grid-chip mono">{combat.grid.width}×{combat.grid.height}</span>
      {/if}
    </div>
  </header>

  {#if combat.status !== "active"}
    <div class="map-message">
      {#if combat.status === "preparing"}
        <p>Carte disponible après activation du combat.</p>
      {:else}
        <p>Combat terminé — carte en lecture seule.</p>
      {/if}
    </div>
  {:else if !combat.grid}
    <div class="map-message">
      <p>Grille non initialisée — activez le combat pour afficher la carte.</p>
    </div>
  {:else}
    <div class="map-body">
      <div class="axis axis-top" style={`--cols: ${combat.grid.width}`}>
        {#each Array.from({ length: combat.grid.width }) as _, x (x)}
          <span>{columnLabel(x)}</span>
        {/each}
      </div>
      <div class="map-scroll">
        <div class="axis axis-left" style={`--rows: ${combat.grid.height}`}>
          {#each Array.from({ length: combat.grid.height }) as _, y (y)}
            <span>{y + 1}</span>
          {/each}
        </div>
        <div
          class="grid-board"
          style={`grid-template-columns: repeat(${combat.grid.width}, var(--cell-size));`}
          role="grid"
          aria-label="Grille de combat"
        >
          {#each cells as cell (`${cell.x},${cell.y}`)}
            {@const occupant = combatantAt(cell.x, cell.y)}
            {@const isCurrent = occupant?.combatant_id === combat.current_combatant_id}
            <button
              type="button"
              class="cell"
              class:occupied={occupant != null}
              class:current-turn={isCurrent}
              class:move-target={canMove && occupant == null}
              disabled={loading || (occupant != null && !onSelectTarget)}
              aria-label={occupant
                ? `${occupant.display_name} — case ${columnLabel(cell.x)}${cell.y + 1}`
                : `Case ${columnLabel(cell.x)}${cell.y + 1}`}
              onclick={() => handleCellClick(cell.x, cell.y)}
            >
              {#if occupant}
                <span
                  class="token {tokenSide(occupant)}"
                  class:current-turn={isCurrent}
                  title={occupant.display_name}
                >
                  {initials(occupant.display_name)}
                </span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <footer class="map-foot">
    {#if combat.status === "active" && combat.grid}
      {#if canMove}
        <span class="foot-note">
          Clic sur une case libre pour déplacer votre personnage
          {#if currentBudget?.movement_remaining_ft !== undefined}
            — <strong class="mono">{currentBudget.movement_remaining_ft} ft</strong> restants
          {/if}
        </span>
      {:else if viewerCombatantId == null}
        <span class="foot-note">Sélectionnez un viewer pour activer le déplacement.</span>
      {:else if combat.current_combatant_id !== viewerCombatantId}
        <span class="foot-note">Carte en lecture seule — ce n'est pas votre tour.</span>
      {:else if (currentBudget?.movement_remaining_ft ?? 0) <= 0}
        <span class="foot-note">Budget mouvement épuisé pour ce tour.</span>
      {:else}
        <span class="foot-note">Carte en lecture seule.</span>
      {/if}
      <span class="foot-scale mono">1 case = 5 ft (Chebyshev)</span>
    {:else}
      <span class="foot-note">Positions synchronisées via l'API combat (lot 8).</span>
    {/if}
  </footer>
</section>

<style>
  .map {
    --cell-size: 2rem;
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 540px;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 0.03),
      0 8px 24px rgb(0 0 0 / 0.4);
    overflow: hidden;
  }

  .map-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: linear-gradient(rgb(255 255 255 / 0.02), transparent), var(--color-bg-panel);
  }

  .map-title {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-family: var(--font-display);
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .map-title :global(svg) {
    color: var(--color-accent);
  }

  .map-tools {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .tool {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
    background: var(--color-bg-input);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    padding: 0.22rem 0.5rem;
  }

  .tool:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .grid-chip {
    font-size: 0.66rem;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-subtle);
    border-radius: 999px;
    padding: 0.12rem 0.45rem;
  }

  .map-message {
    flex: 1;
    display: grid;
    place-items: center;
    padding: 2rem;
    text-align: center;
    color: var(--color-text-muted);
    font-size: 0.85rem;
  }

  .map-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0.65rem 0.35rem;
    gap: 0.35rem;
  }

  .axis {
    display: grid;
    font-family: var(--font-mono);
    font-size: 0.58rem;
    letter-spacing: 0.05em;
    color: rgb(255 255 255 / 0.22);
    user-select: none;
  }

  .axis-top {
    grid-template-columns: repeat(var(--cols), var(--cell-size));
    gap: 1px;
    margin-left: 1.35rem;
  }

  .axis-top span,
  .axis-left span {
    display: grid;
    place-items: center;
  }

  .map-scroll {
    flex: 1;
    min-height: 0;
    overflow: auto;
    display: flex;
    gap: 0.35rem;
    background: #0b0a08;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    padding: 0.35rem;
  }

  .axis-left {
    grid-template-rows: repeat(var(--rows), var(--cell-size));
    gap: 1px;
    flex-shrink: 0;
  }

  .grid-board {
    display: grid;
    gap: 1px;
    align-content: start;
  }

  .cell {
    width: var(--cell-size);
    height: var(--cell-size);
    padding: 0;
    border: 1px solid rgb(255 255 255 / 0.06);
    background: rgb(255 255 255 / 0.02);
    cursor: default;
    display: grid;
    place-items: center;
    position: relative;
  }

  .cell.move-target:not(:disabled) {
    cursor: pointer;
  }

  .cell.move-target:not(:disabled):hover {
    background: rgb(245 158 11 / 0.12);
    border-color: rgb(245 158 11 / 0.35);
  }

  .cell.current-turn {
    box-shadow: inset 0 0 0 1px rgb(245 158 11 / 0.45);
  }

  .cell:disabled {
    cursor: not-allowed;
  }

  .token {
    width: calc(var(--cell-size) - 4px);
    height: calc(var(--cell-size) - 4px);
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.45);
  }

  .token.self {
    border: 2px solid rgb(74 222 128 / 0.85);
    background: rgb(74 222 128 / 0.12);
    color: rgb(187 247 208);
  }

  .token.other {
    border: 2px solid rgb(239 68 68 / 0.85);
    background: rgb(239 68 68 / 0.12);
    color: rgb(254 202 202);
  }

  .token.current-turn {
    box-shadow:
      0 0 0 2px rgb(245 158 11 / 0.55),
      0 2px 10px rgb(245 158 11 / 0.25);
  }

  .map-foot {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.4rem 0.8rem;
    border-top: 1px solid var(--color-border-subtle);
    background: var(--color-bg-panel);
  }

  .foot-note {
    font-size: 0.68rem;
    color: var(--color-text-muted);
  }

  .foot-scale {
    margin-left: auto;
    font-size: 0.66rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .mono {
    font-family: var(--font-mono);
  }
</style>
