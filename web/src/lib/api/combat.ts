import type { ApiErrorPayload, CombatState, LoadError } from "../types/combat";

async function parseJsonResponse(res: Response): Promise<CombatState | LoadError> {
  const text = await res.text();
  let payload: unknown;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    return {
      kind: "api",
      status: res.status,
      code: "INVALID_JSON",
      message: `Réponse non JSON (HTTP ${res.status}).`,
    };
  }

  if (res.ok) {
    return payload as CombatState;
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

  const result = await parseJsonResponse(res);
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

  const result = await parseJsonResponse(res);
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
