<script lang="ts">
  import Icon from "./Icon.svelte";
  import { SCENE_TEST_MAP_URL } from "../../constants/scene_map";
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

  let mapBodyEl: HTMLDivElement | undefined = $state(undefined);
  let cellSizePx = $state(20);

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

  const grid = $derived(combat.grid);

  const cells = $derived.by(() => {
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

  const placedTokens = $derived.by(() => {
    if (!grid) {
      return [] as Array<{ combatant: Combatant; x: number; y: number }>;
    }
    const list: Array<{ combatant: Combatant; x: number; y: number }> = [];
    for (const combatant of Object.values(combat.combatants)) {
      const pos = combatant.position;
      if (pos != null) {
        list.push({ combatant, x: pos.x, y: pos.y });
      }
    }
    return list;
  });

  /* Le cadre doré remplit tout le rectangle disponible ; la grille jouable
     (cases carrées) est centrée, et les bandes restantes sont comblées par
     le même quadrillage décoratif (non jouable). */
  const FRAME_BORDER_PX = 2;

  let frameInnerW = $state(0);
  let frameInnerH = $state(0);

  const stageOffset = $derived.by(() => {
    if (!grid) {
      return { x: 0, y: 0 };
    }
    const w = cellSizePx * grid.width;
    const h = cellSizePx * grid.height;
    return {
      x: Math.max(0, Math.round((frameInnerW - w) / 2)),
      y: Math.max(0, Math.round((frameInnerH - h) / 2)),
    };
  });

  const stageStyle = $derived.by(() => {
    if (!grid) {
      return "";
    }
    const w = cellSizePx * grid.width;
    const h = cellSizePx * grid.height;
    return `--cell-size:${cellSizePx}px;width:${w}px;height:${h}px;left:${stageOffset.x}px;top:${stageOffset.y}px;`;
  });

  /* Quadrillage décoratif aligné sur la grille jouable. */
  const decoGridStyle = $derived.by(() => {
    if (!grid || cellSizePx <= 0) {
      return "";
    }
    const offX = stageOffset.x % cellSizePx;
    const offY = stageOffset.y % cellSizePx;
    return `background-size:${cellSizePx}px ${cellSizePx}px;background-position:${offX}px ${offY}px;`;
  });

  const gridLayerStyle = $derived.by(() => {
    if (!grid) {
      return "";
    }
    return `grid-template-columns: repeat(${grid.width}, 1fr); grid-template-rows: repeat(${grid.height}, 1fr);`;
  });

  $effect(() => {
    const host = mapBodyEl;
    const g = grid;
    if (!host || !g) {
      return;
    }

    const update = () => {
      const rect = host.getBoundingClientRect();
      const availW = rect.width - FRAME_BORDER_PX;
      const availH = rect.height - FRAME_BORDER_PX;
      if (availW <= 0 || availH <= 0) {
        return;
      }
      frameInnerW = availW;
      frameInnerH = availH;
      cellSizePx = Math.max(
        8,
        Math.floor(Math.min(availW / g.width, availH / g.height)),
      );
    };

    update();
    const ro = new ResizeObserver(() => update());
    ro.observe(host);
    return () => ro.disconnect();
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

  function tokenPercent(x: number, y: number): { left: number; top: number } {
    if (!grid) {
      return { left: 0, top: 0 };
    }
    return {
      left: ((x + 0.5) / grid.width) * 100,
      top: ((y + 0.5) / grid.height) * 100,
    };
  }

  function handleCellClick(x: number, y: number) {
    if (combatantAt(x, y)) {
      return;
    }
    if (canMove) {
      onMove(x, y);
    }
  }

  function handleTokenClick(combatant: Combatant, event: MouseEvent) {
    event.stopPropagation();
    if (onSelectTarget && combatant.combatant_id !== viewerCombatantId) {
      onSelectTarget(combatant.combatant_id);
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
      {#if grid}
        <span class="grid-chip mono">{grid.width}×{grid.height}</span>
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
  {:else if !grid}
    <div class="map-message">
      <p>Grille non initialisée — activez le combat pour afficher la carte.</p>
    </div>
  {:else}
    <div class="map-body" bind:this={mapBodyEl}>
      <div class="scene-frame">
        <div
          class="scene-backdrop"
          style={`--scene-url: url("${SCENE_TEST_MAP_URL}")`}
          aria-hidden="true"
        ></div>
        <div class="deco-grid" style={decoGridStyle} aria-hidden="true"></div>
        <div class="play-stage" style={stageStyle}>
        <div
          class="grid-layer"
          style={gridLayerStyle}
          role="grid"
          aria-label="Grille de combat"
        >
          {#each cells as cell (`${cell.x},${cell.y}`)}
            {@const occupant = combatantAt(cell.x, cell.y)}
            {@const isCurrent = occupant?.combatant_id === combat.current_combatant_id}
            <button
              type="button"
              class="cell"
              class:current-turn={isCurrent}
              class:move-target={canMove && occupant == null}
              disabled={loading}
              aria-label={`Case ${columnLabel(cell.x)}${cell.y + 1}`}
              onclick={() => handleCellClick(cell.x, cell.y)}
            ></button>
          {/each}
        </div>

        <div class="tokens-layer">
          {#each placedTokens as entry (`${entry.combatant.combatant_id}-${entry.x}-${entry.y}`)}
            {@const pct = tokenPercent(entry.x, entry.y)}
            {@const isCurrent = entry.combatant.combatant_id === combat.current_combatant_id}
            <button
              type="button"
              class="token {tokenSide(entry.combatant)}"
              class:current-turn={isCurrent}
              class:selectable={onSelectTarget != null &&
                entry.combatant.combatant_id !== viewerCombatantId}
              style={`left:${pct.left}%;top:${pct.top}%;width:calc(var(--cell-size) * 0.82);height:calc(var(--cell-size) * 0.82);`}
              title={entry.combatant.display_name}
              disabled={loading}
              aria-label={entry.combatant.display_name}
              onclick={(e) => handleTokenClick(entry.combatant, e)}
            >
              {initials(entry.combatant.display_name)}
            </button>
          {/each}
        </div>
        </div>
      </div>
    </div>
  {/if}

  <footer class="map-foot">
    {#if combat.status === "active" && grid}
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
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    height: 100%;
    min-height: 540px;
  }

  /* Bandeau titre : panneau propre, détaché de la carte (maquette). */
  .map-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.8rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
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
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  /* Zone neutre : centre le cadre doré, sert de référence de mesure. */
  .map-body {
    position: relative;
    flex: 1;
    min-height: 0;
    display: grid;
    place-items: center;
    padding: 0;
    overflow: hidden;
  }

  /* Cadre doré : liseré 1px uniforme, angles arrondis, remplit tout l'espace. */
  .scene-frame {
    position: relative;
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    border: 1px solid rgb(218 165 32 / 0.85);
    border-radius: 10px;
    overflow: hidden;
    background: #12100e;
  }

  /* Quadrillage décoratif : mêmes carrés que la grille jouable, non cliquable. */
  .deco-grid {
    position: absolute;
    inset: 0;
    z-index: 1;
    pointer-events: none;
    background-image:
      linear-gradient(rgb(255 255 255 / 0.055) 1px, transparent 1px),
      linear-gradient(90deg, rgb(255 255 255 / 0.055) 1px, transparent 1px);
  }

  /* Zone jouable : grille du moteur, centrée, cases carrées. */
  .play-stage {
    position: absolute;
    z-index: 2;
  }

  .scene-backdrop {
    position: absolute;
    inset: 0;
    z-index: 0;
    background-color: #12100e;
    background-image:
      var(--scene-url),
      radial-gradient(ellipse 90% 70% at 50% 52%, rgb(245 158 11 / 0.07), transparent 62%),
      radial-gradient(ellipse 40% 30% at 22% 20%, rgb(255 255 255 / 0.02), transparent),
      radial-gradient(ellipse 35% 28% at 80% 78%, rgb(255 255 255 / 0.015), transparent),
      repeating-linear-gradient(37deg, rgb(255 255 255 / 0.008) 0 2px, transparent 2px 9px),
      repeating-linear-gradient(-52deg, rgb(0 0 0 / 0.22) 0 3px, transparent 3px 13px),
      linear-gradient(#141210, #0c0b09);
    background-size: cover, auto, auto, auto, auto, auto, auto;
    background-position: center;
    background-repeat: no-repeat;
    pointer-events: none;
  }

  .grid-layer {
    position: absolute;
    inset: 0;
    display: grid;
    gap: 0;
    z-index: 1;
  }

  .cell {
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    padding: 0;
    margin: 0;
    border: 1px solid rgb(255 255 255 / 0.1);
    background: transparent;
    cursor: default;
  }

  .cell.move-target:not(:disabled) {
    cursor: pointer;
  }

  .cell.move-target:not(:disabled):hover {
    background: rgb(245 158 11 / 0.14);
    border-color: rgb(245 158 11 / 0.35);
  }

  .cell.current-turn {
    box-shadow: inset 0 0 0 1px rgb(245 158 11 / 0.5);
  }

  .tokens-layer {
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
  }

  .token {
    position: absolute;
    translate: -50% -50%;
    padding: 0;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: clamp(0.48rem, calc(var(--cell-size) * 0.28), 0.72rem);
    font-weight: 700;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.45);
    pointer-events: auto;
    cursor: default;
  }

  .token.selectable {
    cursor: pointer;
  }

  .token.self {
    border: 2px solid rgb(74 222 128 / 0.85);
    background: rgb(74 222 128 / 0.18);
    color: rgb(187 247 208);
  }

  .token.other {
    border: 2px solid rgb(239 68 68 / 0.85);
    background: rgb(239 68 68 / 0.18);
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
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-lg);
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
