import type { ApiErrorPayload, LoadError } from "../types/combat";
import type { CharacterSheet } from "../types/sheet";

async function parseJsonResponse<T>(res: Response): Promise<T | LoadError> {
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

export async function fetchCharacterSheet(
  characterId: string,
): Promise<CharacterSheet> {
  const id = characterId.trim();
  if (!id) {
    throw {
      kind: "network",
      message: "character_id requis.",
    } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await fetch(`/v1/characters/${encodeURIComponent(id)}/sheet`);
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  const result = await parseJsonResponse<CharacterSheet>(res);
  if ("kind" in result) {
    throw result;
  }
  return result;
}
