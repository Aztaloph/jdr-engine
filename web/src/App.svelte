<script lang="ts">
  import Router, { link, router } from "svelte-spa-router";
  import LobbyScreen from "./lib/screens/LobbyScreen.svelte";
  import CombatScreen from "./lib/screens/CombatScreen.svelte";
  import { ensureDefaultRoute } from "./lib/navigation";
  import type { RouteDefinition } from "svelte-spa-router";

  ensureDefaultRoute();

  const routes: RouteDefinition = {
    "/": LobbyScreen,
    "/lobby": LobbyScreen,
    "/combat/:id": CombatScreen,
    "*": LobbyScreen,
  };

  const isLobbyRoute = $derived(
    router.location === "/" ||
      router.location === "/lobby" ||
      !router.location.startsWith("/combat/"),
  );

  const combatNavId = $derived.by(() => {
    const match = router.location.match(/^\/combat\/([^/]+)/);
    return match?.[1] ?? null;
  });
</script>

<nav class="app-nav" aria-label="Navigation principale">
  <a href="/lobby" use:link class:active={isLobbyRoute}>Lobby</a>
  {#if combatNavId}
    <span class="nav-sep">·</span>
    <span class="nav-current">Combat {combatNavId}</span>
  {/if}
</nav>

<Router {routes} />
