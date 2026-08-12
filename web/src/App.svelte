<script lang="ts">
  import Router, { link, router } from "svelte-spa-router";
  import LandingScreen from "./lib/screens/LandingScreen.svelte";
  import LobbyScreen from "./lib/screens/LobbyScreen.svelte";
  import CombatScreen from "./lib/screens/CombatScreen.svelte";
  import CharacterScreen from "./lib/screens/CharacterScreen.svelte";
  import { ensureDefaultRoute } from "./lib/navigation";
  import type { RouteDefinition } from "svelte-spa-router";

  ensureDefaultRoute();

  const routes: RouteDefinition = {
    "/": LandingScreen,
    "/lobby": LobbyScreen,
    "/combat/:id": CombatScreen,
    "/character/:id": CharacterScreen,
    "*": LandingScreen,
  };

  /**
   * Routes cadrées — conteneur centré + nav interne.
   * Le combat est pleine page : son HUD intègre son propre header.
   */
  const isFramedRoute = $derived(
    /^\/(lobby|character\/)/.test(router.location),
  );

  const isLobbyRoute = $derived(router.location === "/lobby");

  const characterNavId = $derived.by(() => {
    const match = router.location.match(/^\/character\/([^/]+)/);
    return match?.[1] ?? null;
  });
</script>

<div class:app-frame={isFramedRoute}>
  {#if isFramedRoute}
    <nav class="app-nav" aria-label="Navigation principale">
      <a href="/" use:link class="nav-home">JDR Engine</a>
      <span class="nav-sep">·</span>
      <a href="/lobby" use:link class:active={isLobbyRoute}>Lobby</a>
      {#if characterNavId}
        <span class="nav-sep">·</span>
        <span class="nav-current">Fiche {characterNavId}</span>
      {/if}
    </nav>
  {/if}
  <Router {routes} />
</div>
