/** Routage hash — zéro dépendance. Routes : `#/lobby`, `#/combat/:id?viewer=` */

export type Route =
  | { name: "lobby" }
  | { name: "combat"; combatId: string; viewer?: string };

export function parseHash(hash: string): Route {
  const trimmed = hash.replace(/^#/, "").trim();
  if (!trimmed || trimmed === "/" || trimmed === "/lobby") {
    return { name: "lobby" };
  }

  const qIndex = trimmed.indexOf("?");
  const path = qIndex >= 0 ? trimmed.slice(0, qIndex) : trimmed;
  const query = qIndex >= 0 ? trimmed.slice(qIndex + 1) : "";
  const params = new URLSearchParams(query);
  const viewerRaw = params.get("viewer")?.trim();
  const viewer = viewerRaw ? viewerRaw : undefined;

  const combatMatch = path.match(/^\/combat\/([^/]+)$/);
  if (combatMatch) {
    return { name: "combat", combatId: decodeURIComponent(combatMatch[1]), viewer };
  }

  return { name: "lobby" };
}

export function navigateToLobby(): void {
  window.location.hash = "#/lobby";
}

export function navigateToCombat(combatId: string | number, viewer?: string): void {
  let hash = `#/combat/${encodeURIComponent(String(combatId))}`;
  const viewerTrimmed = viewer?.trim();
  if (viewerTrimmed) {
    hash += `?viewer=${encodeURIComponent(viewerTrimmed)}`;
  }
  if (window.location.hash === hash) {
    return;
  }
  window.location.hash = hash;
}

export function subscribeHash(onChange: (route: Route) => void): () => void {
  const handler = () => onChange(parseHash(window.location.hash));
  window.addEventListener("hashchange", handler);
  return () => window.removeEventListener("hashchange", handler);
}

export function ensureDefaultRoute(): void {
  const hash = window.location.hash.replace(/^#/, "").trim();
  if (!hash || hash === "/") {
    navigateToLobby();
  }
}
