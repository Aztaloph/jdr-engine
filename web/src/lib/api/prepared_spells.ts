import { isLoadError } from "./combat";
import type { LoadError } from "../types/combat";
import type {
  PreparedSpellsRequest,
  PreparedSpellsView,
} from "../types/prepared_spells";

async function parseJson<T>(res: Response): Promise<T | LoadError> {
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
    return payload as T;
  }
  const err = payload as { error?: { code?: string; message?: string } };
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

export async function fetchPreparedSpells(
  characterId: string,
): Promise<PreparedSpellsView> {
  let res: Response;
  try {
    res = await fetch(
      `/v1/characters/${encodeURIComponent(characterId)}/prepared-spells`,
    );
  } catch (cause) {
    throw {
      kind: "network",
      message: cause instanceof Error ? cause.message : String(cause),
    } satisfies LoadError;
  }
  const data = await parseJson<PreparedSpellsView>(res);
  if ("kind" in data) {
    throw data;
  }
  return data;
}

export async function applyPreparedSpells(
  characterId: string,
  body: PreparedSpellsRequest,
): Promise<PreparedSpellsView> {
  let res: Response;
  try {
    res = await fetch(
      `/v1/characters/${encodeURIComponent(characterId)}/prepared-spells`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  } catch (cause) {
    throw {
      kind: "network",
      message: cause instanceof Error ? cause.message : String(cause),
    } satisfies LoadError;
  }
  const data = await parseJson<PreparedSpellsView>(res);
  if ("kind" in data) {
    throw data;
  }
  return data;
}
