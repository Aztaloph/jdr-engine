import { isLoadError } from "./combat";
import type { LoadError } from "../types/combat";
import type { CharacterListEntry, CharacterListResponse } from "../types/character";

export async function fetchCharacterList(): Promise<CharacterListEntry[]> {
  let res: Response;
  try {
    res = await fetch("/v1/characters");
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

export { isLoadError };
