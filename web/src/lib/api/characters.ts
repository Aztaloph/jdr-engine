import { authFetch } from "../auth/session";
import { isLoadError } from "./combat";
import type { LoadError } from "../types/combat";
import type { CharacterListEntry, CharacterListResponse } from "../types/character";

export async function fetchCharacterList(): Promise<CharacterListEntry[]> {
  let res: Response;
  try {
    res = await authFetch("/v1/characters");
  } catch (cause) {
    throw {
      kind: "network",
      message:
        cause instanceof Error
          ? cause.message
          : "API injoignable — vérifiez qu'uvicorn tourne sur le port 8000.",
    } satisfies LoadError;
  }

  if (!res.ok) {
    throw {
      kind: "network",
      message: `Impossible de charger la liste des personnages (HTTP ${res.status}).`,
    } satisfies LoadError;
  }

  const data = (await res.json()) as CharacterListResponse;
  return data.characters ?? [];
}

export async function postLongRest(characterId: string): Promise<void> {
  const id = characterId.trim();
  if (!id) {
    throw {
      kind: "network",
      message: "character_id requis.",
    } satisfies LoadError;
  }

  let res: Response;
  try {
    res = await authFetch(`/v1/characters/${encodeURIComponent(id)}/long-rest`, {
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

  if (!res.ok) {
    let message = `Repos long refusé (HTTP ${res.status}).`;
    try {
      const payload = (await res.json()) as { error?: { message?: string } };
      if (payload.error?.message) {
        message = payload.error.message;
      }
    } catch {
      /* corps non JSON */
    }
    throw {
      kind: "network",
      message,
    } satisfies LoadError;
  }
}

export { isLoadError };
