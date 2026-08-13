/**
 * WebSocket combat v1 — CONTRAT_WS.md.
 * Canal push complémentaire au REST ; aucune action de jeu via WS.
 */

import type { CombatState, GridPosition } from "../types/combat";

/** Code applicatif — combat introuvable (ne pas reconnecter). */
export const WS_COMBAT_NOT_FOUND = 4404;

export type WsConnectionStatus = "connecting" | "open" | "closed" | "error";

export interface CombatWsMessage {
  type: string;
  combat_id: number;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface CombatWsHandlers {
  onConnected?: (message: CombatWsMessage, isReconnect: boolean) => void;
  onPositionChanged?: (
    payload: PositionChangedPayload,
    message: CombatWsMessage,
  ) => void;
  onTurnStarted?: (
    payload: TurnStartedPayload,
    message: CombatWsMessage,
  ) => void;
  onCombatEnded?: (payload: CombatEndedPayload, message: CombatWsMessage) => void;
  onStateInvalidated?: (message: CombatWsMessage) => void;
  onCombatNotFound?: () => void;
  onDisconnected?: (code: number) => void;
  /** Diagnostic dev — cycle de vie socket. */
  onStatusChange?: (status: WsConnectionStatus, detail?: string) => void;
  /** Diagnostic dev — tout message entrant. */
  onEvent?: (message: CombatWsMessage) => void;
}

/** Pont mutable : handlers WS toujours à jour (évite closures Svelte périmées). */
export interface CombatWsHandlerBridge {
  scheduleSync: () => void;
  onCombatNotFound: () => void;
  onStatusChange: (status: WsConnectionStatus, detail?: string) => void;
  onEvent: (message: CombatWsMessage) => void;
}

export interface PositionChangedPayload {
  combatant_id: string;
  from: GridPosition;
  to: GridPosition;
  cost_ft: number;
  movement_remaining_ft: number;
  round_number: number;
  turn_index: number;
}

export interface TurnStartedPayload {
  combatant_id: string;
  round_number: number;
  turn_index: number;
}

export interface CombatEndedPayload {
  reason: string;
}

export interface CombatWsConnection {
  disconnect: () => void;
}

function wsBaseUrl(): string {
  if (typeof window === "undefined") {
    return "ws://127.0.0.1:8000";
  }
  // Dev : API directe (le proxy WS Vite est peu fiable sur Windows).
  if (import.meta.env.DEV) {
    return "ws://127.0.0.1:8000";
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}

function buildWsUrl(combatId: string, viewer?: string): string {
  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const path = `/v1/combats/${encodeURIComponent(combatId)}/ws`;
  return `${wsBaseUrl()}${path}${query ? `?${query}` : ""}`;
}

function parseMessage(raw: string): CombatWsMessage | null {
  try {
    const parsed = JSON.parse(raw) as CombatWsMessage;
    if (typeof parsed?.type !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function applyPositionChangedToState(
  state: CombatState,
  payload: PositionChangedPayload,
): CombatState {
  const combatant = state.combatants[payload.combatant_id];
  if (!combatant) {
    return state;
  }
  const nextBudget = combatant.action_budget
    ? {
        ...combatant.action_budget,
        movement_remaining_ft: payload.movement_remaining_ft,
      }
    : combatant.action_budget;
  return {
    ...state,
    round_number: payload.round_number,
    turn_index: payload.turn_index,
    combatants: {
      ...state.combatants,
      [payload.combatant_id]: {
        ...combatant,
        position: payload.to,
        action_budget: nextBudget,
      },
    },
  };
}

export function applyTurnStartedToState(
  state: CombatState,
  payload: TurnStartedPayload,
): CombatState {
  return {
    ...state,
    current_combatant_id: payload.combatant_id,
    round_number: payload.round_number,
    turn_index: payload.turn_index,
  };
}

/**
 * Ouvre le canal WS combat avec reconnexion backoff (sauf code 4404).
 * Préférer ``bridge`` pour les callbacks de sync — toujours à jour.
 */
export function connectCombatWs(
  combatId: string,
  viewer: string | undefined,
  bridge: CombatWsHandlerBridge,
): CombatWsConnection {
  const id = combatId.trim();
  let socket: WebSocket | null = null;
  let stopped = false;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const clearReconnect = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const scheduleReconnect = () => {
    if (stopped) {
      return;
    }
    const delayMs = Math.min(1000 * 2 ** attempt, 30_000);
    attempt += 1;
    reconnectTimer = setTimeout(connect, delayMs);
  };

  const dispatch = (message: CombatWsMessage, isReconnect: boolean) => {
    bridge.onEvent(message);

    switch (message.type) {
      case "connected":
        if (isReconnect) {
          bridge.scheduleSync();
        }
        break;
      case "position_changed":
      case "turn_started":
      case "combat_ended":
      case "combat_state_invalidated":
        bridge.scheduleSync();
        break;
      default:
        break;
    }
  };

  const connect = () => {
    if (stopped || !id) {
      return;
    }
    const isReconnect = attempt > 0;
    clearReconnect();
    bridge.onStatusChange("connecting");
    socket = new WebSocket(buildWsUrl(id, viewer));

    socket.addEventListener("open", () => {
      attempt = 0;
      bridge.onStatusChange("open");
    });

    socket.addEventListener("message", (event) => {
      const text = typeof event.data === "string" ? event.data : "";
      const message = parseMessage(text);
      if (message) {
        dispatch(message, isReconnect);
      }
    });

    socket.addEventListener("close", (event) => {
      if (stopped) {
        return;
      }
      bridge.onStatusChange("closed", String(event.code));
      if (event.code === WS_COMBAT_NOT_FOUND) {
        bridge.onCombatNotFound();
        stopped = true;
        return;
      }
      scheduleReconnect();
    });

    socket.addEventListener("error", () => {
      if (stopped) {
        return;
      }
      bridge.onStatusChange("error");
    });
  };

  connect();

  return {
    disconnect: () => {
      stopped = true;
      clearReconnect();
      const active = socket;
      socket = null;
      if (!active) {
        return;
      }
      active.onclose = null;
      active.onerror = null;
      active.onmessage = null;
      active.onopen = null;
      if (
        active.readyState === WebSocket.CONNECTING ||
        active.readyState === WebSocket.OPEN
      ) {
        active.close(1000, "disconnect");
      }
    },
  };
}
