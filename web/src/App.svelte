<script lang="ts">
  import {
    ensureDefaultRoute,
    navigateToLobby,
    parseHash,
    subscribeHash,
    type Route,
  } from "./lib/router";
  import LobbyScreen from "./lib/screens/LobbyScreen.svelte";
  import CombatScreen from "./lib/screens/CombatScreen.svelte";

  ensureDefaultRoute();

  let route = $state<Route>(parseHash(window.location.hash));

  $effect(() => {
    return subscribeHash((next) => {
      route = next;
    });
  });
</script>

<nav class="app-nav" aria-label="Navigation principale">
  <a
    href="#/lobby"
    class:active={route.name === "lobby"}
    onclick={(e) => {
      e.preventDefault();
      navigateToLobby();
    }}
  >
    Lobby
  </a>
  {#if route.name === "combat"}
    <span class="nav-sep">·</span>
    <span class="nav-current">Combat {route.combatId}</span>
  {/if}
</nav>

{#if route.name === "lobby"}
  <LobbyScreen />
{:else if route.name === "combat"}
  <CombatScreen combatId={route.combatId} initialViewer={route.viewer ?? ""} />
{/if}
