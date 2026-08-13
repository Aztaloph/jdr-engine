import type { ApiErrorPayload, CombatJournalEntry, CombatState, LoadError } from "../types/combat";
import type { WeaponAttackResult, WeaponId } from "../types/attack";

const API_UNREACHABLE_MESSAGE =
  "API injoignable — lancez uvicorn sur le port 8000 (voir web/README.md).";

/** Erreurs proxy Vite quand uvicorn est arrêté (corps vide ou HTML). */
function isGatewayUnreachable(status: number): boolean {
  return status === 502 || status === 503 || status === 504;
}

function gatewayLoadError(status: number): LoadError {
  return {
    kind: "network",
    message:
      status === 502
        ? `${API_UNREACHABLE_MESSAGE} (proxy Vite : connexion refusée sur 127.0.0.1:8000).`
        : API_UNREACHABLE_MESSAGE,
  };
}

async function parseJsonResponse<T>(res: Response): Promise<T | LoadError> {
  const text = await res.text();
  let payload: unknown;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    if (isGatewayUnreachable(res.status)) {
      return gatewayLoadError(res.status);
    }
    return {
      kind: "api",
      status: res.status,
      code: "INVALID_JSON",
      message: `Réponse non JSON (HTTP ${res.status}).`,
    };
  }

  if (res.ok) {
    return payload as T;
  }

  const err = payload as ApiErrorPayload;
  if (err?.error?.code && err?.error?.message) {
    return {
      kind: "api",
      status: res.status,
      code: err.error.code,
      message: err.error.message,
    };
  }

  if (isGatewayUnreachable(res.status)) {
    return gatewayLoadError(res.status);
  }

  return {
    kind: "api",
    status: res.status,
    code: "UNKNOWN_ERROR",
    message: `Erreur HTTP ${res.status}.`,
  };
}

export async function fetchCombatState(
  combatId: string,
  viewer?: string,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url);
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function healCombatant(
  combatId: string,
  combatantId: string,
  viewer?: string,
  hpCurrent?: number,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/heal${query ? `?${query}` : ""}`;

  const body: { combatant_id: string; hp_current?: number } = {
    combatant_id: combatantId,
  };
  if (hpCurrent !== undefined) {
    body.hp_current = hpCurrent;
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function syncCombatantFromSheet(
  combatId: string,
  combatantId: string,
  viewer?: string,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/sync-combatant${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ combatant_id: combatantId }),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function advanceCombatTurn(
  combatId: string,
  viewer?: string,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/advance-turn${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, { method: "POST" });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export interface AttackRequest {
  attacker_id: string;
  target_id: string;
  weapon_id: WeaponId;
}

export interface CombatCastRequest {
  caster_id: string;
  spell_id: string;
  target_ids: string[];
  slot_level?: number | null;
}

export async function postCombatCast(
  combatId: string,
  body: CombatCastRequest,
  viewer?: string,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/cast${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function postWeaponAttack(
  combatId: string,
  body: AttackRequest,
  viewer?: string,
): Promise<WeaponAttackResult> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/attack${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<WeaponAttackResult>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export function isLoadError(value: unknown): value is LoadError {
  return (
    typeof value === "object" &&
    value !== null &&
    "kind" in value &&
    ((value as LoadError).kind === "api" ||
      (value as LoadError).kind === "network")
  );
}

export async function createCombat(characterIds: string[]): Promise<CombatState> {
  const ids = characterIds.map((id) => id.trim()).filter(Boolean);
  if (ids.length === 0) {
    throw {
      kind: "network",
      message: "Au moins un character_id requis.",
    } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await fetch("/v1/combats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character_ids: ids }),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function fetchCombatJournal(combatId: string): Promise<CombatJournalEntry[]> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await fetch(`/v1/combats/${encodeURIComponent(id)}/events`);
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<{ events: CombatJournalEntry[] }>(res);
  if ("kind" in result) {
    throw result;
  }
  return result.events ?? [];
}

export interface MoveCombatantRequest {
  combatant_id: string;
  x: number;
  y: number;
}

export async function postCombatMove(
  combatId: string,
  body: MoveCombatantRequest,
  viewer?: string,
): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  const params = new URLSearchParams();
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    params.set("viewer", viewerTrimmed);
  }
  const query = params.toString();
  const url = `/v1/combats/${encodeURIComponent(id)}/move${query ? `?${query}` : ""}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export async function activateCombat(combatId: string): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await fetch(`/v1/combats/${encodeURIComponent(id)}/activate`, {
      method: "POST",
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}

export interface OpenCombatParticipant {
  character_id: string;
  display_name: string;
}

export interface OpenCombatSummary {
  combat_id: number;
  status: CombatState["status"];
  participants: OpenCombatParticipant[];
}

export async function fetchOpenCombats(): Promise<OpenCombatSummary[]> {
  let res: Response;
  try {
    res = await fetch("/v1/combats/open");
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<{ combats: OpenCombatSummary[] }>(res);
  if ("kind" in result) {
    throw result;
  }
  return result.combats ?? [];
}

export async function closeCombat(combatId: string): Promise<CombatState> {
  const id = combatId.trim();
  if (!id) {
    throw { kind: "network", message: "combat_id requis." } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await fetch(`/v1/combats/${encodeURIComponent(id)}/close`, {
      method: "POST",
    });
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CombatState>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}
