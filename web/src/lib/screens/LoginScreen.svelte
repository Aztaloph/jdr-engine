<script lang="ts">
  import { link, push } from "svelte-spa-router";
  import { devLogin, type AuthRole } from "../auth/session";
  import {
    authState,
    initAuth,
    setSessionAfterLogin,
  } from "../auth/store.svelte";

  let userId = $state("");
  let role = $state<AuthRole>("player");
  let formError = $state<string | null>(null);
  let loading = $state(false);

  $effect(() => {
    if (!authState.ready) {
      return;
    }
    if (authState.probeError) {
      return;
    }
    if (authState.mode === "disabled") {
      push("/lobby");
      return;
    }
    if (authState.session) {
      push("/lobby");
    }
  });

  async function submit(event: Event) {
    event.preventDefault();
    formError = null;
    const trimmed = userId.trim();
    if (!trimmed) {
      formError = "Identifiant utilisateur requis (owner_id Discord ou id de test).";
      return;
    }
    loading = true;
    try {
      const session = await devLogin(trimmed, role);
      setSessionAfterLogin(session);
      push("/lobby");
    } catch (e) {
      formError = e instanceof Error ? e.message : "Connexion impossible.";
    } finally {
      loading = false;
    }
  }

  async function retryProbe() {
    await initAuth();
  }
</script>

<main class="login-page">
  <div class="login-card">
    <h1>Connexion — banc de test</h1>
    <p class="hint">
      Auth activée (<code>JDR_API_AUTH=1</code> via <code>launcher_web_auth.bat</code>).
      Utilisez le même <code>owner_id</code> que vos personnages SQLite.
    </p>

    {#if !authState.ready}
      <p class="waiting" role="status">Connexion à l'API…</p>
    {:else if authState.probeError}
      <p class="error" role="alert">{authState.probeError}</p>
      <button type="button" class="retry-btn" onclick={retryProbe}>
        Réessayer
      </button>
    {:else}
      {#if formError}
        <p class="error" role="alert">{formError}</p>
      {/if}

      <form onsubmit={submit}>
        <label class="field">
          <span>Identifiant utilisateur</span>
          <input
            type="text"
            bind:value={userId}
            placeholder="ex. gm1 ou owner_id du perso"
            autocomplete="username"
            disabled={loading}
          />
        </label>

        <fieldset class="role-field">
          <legend>Rôle</legend>
          <label>
            <input type="radio" bind:group={role} value="player" disabled={loading} />
            Joueur
          </label>
          <label>
            <input type="radio" bind:group={role} value="gm" disabled={loading} />
            MJ (GM)
          </label>
        </fieldset>

        <button type="submit" disabled={loading}>
          {loading ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    {/if}

    <p class="foot">
      <a href="/" use:link>Accueil</a>
      ·
      <a href="/lobby" use:link>Lobby (sans auth si API off)</a>
    </p>
  </div>
</main>

<style>
  .login-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    background: var(--color-bg, #0a0a0a);
    color: var(--color-text, #f5f5f5);
  }

  .login-card {
    width: min(100%, 24rem);
    padding: 1.5rem;
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 0.5rem;
    background: rgba(255, 255, 255, 0.03);
  }

  h1 {
    margin: 0 0 0.75rem;
    font-size: 1.25rem;
  }

  .hint {
    margin: 0 0 1rem;
    font-size: 0.85rem;
    opacity: 0.85;
    line-height: 1.45;
  }

  .waiting {
    margin: 0;
    font-size: 0.9rem;
    opacity: 0.85;
  }

  .error {
    margin: 0 0 1rem;
    padding: 0.5rem 0.75rem;
    border-radius: 0.25rem;
    background: rgba(239, 68, 68, 0.15);
    color: #fca5a5;
    font-size: 0.9rem;
  }

  .retry-btn {
    width: 100%;
    padding: 0.6rem;
    margin-bottom: 1rem;
    border: 1px solid rgba(245, 158, 11, 0.5);
    border-radius: 0.25rem;
    background: transparent;
    color: #f59e0b;
    cursor: pointer;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 1rem;
  }

  .field span {
    font-size: 0.85rem;
    opacity: 0.9;
  }

  input[type="text"] {
    padding: 0.5rem 0.65rem;
    border-radius: 0.25rem;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(0, 0, 0, 0.35);
    color: inherit;
  }

  .role-field {
    border: none;
    padding: 0;
    margin: 0 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .role-field legend {
    font-size: 0.85rem;
    margin-bottom: 0.35rem;
  }

  button[type="submit"] {
    width: 100%;
    padding: 0.6rem;
    border: none;
    border-radius: 0.25rem;
    background: #f59e0b;
    color: #0a0a0a;
    font-weight: 600;
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .foot {
    margin: 1rem 0 0;
    font-size: 0.85rem;
    text-align: center;
  }

  a {
    color: #f59e0b;
  }
</style>
