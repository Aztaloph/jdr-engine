/** Navigation programmatique — complète svelte-spa-router (query viewer dans le hash). */
import { push, replace, router } from "svelte-spa-router";

export function viewerFromQuerystring(querystring: string | undefined): string {
  const raw = new URLSearchParams(querystring ?? "").get("viewer")?.trim();
  return raw ?? "";
}

export function navigateToLobby(): void {
  void push("/lobby");
}

export function navigateToCombat(combatId: string | number, viewer?: string): void {
  const targetLocation = `/combat/${encodeURIComponent(String(combatId))}`;
  const viewerTrimmed = viewer?.trim();
  const targetQuerystring = viewerTrimmed
    ? `viewer=${encodeURIComponent(viewerTrimmed)}`
    : "";

  if (
    router.location === targetLocation &&
    (router.querystring ?? "") === targetQuerystring
  ) {
    return;
  }

  const path = targetQuerystring
    ? `${targetLocation}?${targetQuerystring}`
    : targetLocation;
  void push(path);
}

export function navigateToCharacter(characterId: string): void {
  const id = characterId.trim();
  if (!id) {
    return;
  }
  const targetLocation = `/character/${encodeURIComponent(id)}`;
  if (router.location === targetLocation) {
    return;
  }
  void push(targetLocation);
}

export function ensureDefaultRoute(): void {
  const hash = window.location.hash;
  if (!hash || hash === "#" || hash === "#/") {
    void replace("/lobby");
  }
}
