<script lang="ts">
  /**
   * Portrait de personnage — image réelle si fournie un jour, sinon fallback
   * initiales sur médaillon décoratif. Aucune source d'image inventée.
   */
  let {
    name,
    size = 44,
    active = false,
    imageUrl = null,
  }: {
    name: string;
    size?: number;
    active?: boolean;
    imageUrl?: string | null;
  } = $props();

  const initials = $derived(
    name
      .split(/\s+/)
      .map((word) => word[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase(),
  );
</script>

<span
  class="portrait"
  class:active
  style="width: {size}px; height: {size}px; font-size: {Math.round(size * 0.34)}px"
  title={name}
>
  {#if imageUrl}
    <img src={imageUrl} alt="Portrait de {name}" />
  {:else}
    <span class="initials" aria-hidden="true">{initials}</span>
  {/if}
</span>

<style>
  .portrait {
    position: relative;
    flex-shrink: 0;
    display: grid;
    place-items: center;
    border-radius: 50%;
    background:
      radial-gradient(circle at 35% 30%, #232323, #101010 75%);
    border: 1px solid var(--color-border-default);
    box-shadow:
      inset 0 0 0 2px rgb(0 0 0 / 0.55),
      0 2px 6px rgb(0 0 0 / 0.5);
    overflow: hidden;
  }

  .portrait.active {
    border-color: var(--color-accent);
    box-shadow:
      inset 0 0 0 2px rgb(0 0 0 / 0.55),
      0 0 0 2px rgb(245 158 11 / 0.25),
      0 0 14px rgb(245 158 11 / 0.3);
  }

  .portrait img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .initials {
    font-family: var(--font-display);
    font-weight: 700;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .portrait.active .initials {
    color: var(--color-accent);
  }
</style>
