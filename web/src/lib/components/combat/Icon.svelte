<script lang="ts" module>
  /** Icônes au trait — set unique du HUD (stroke 1.8, currentColor). */
  export type IconName =
    | "users"
    | "flag"
    | "wand"
    | "map"
    | "shield"
    | "sword"
    | "sparkle"
    | "scroll"
    | "dice"
    | "eye"
    | "grid"
    | "refresh"
    | "exit"
    | "next"
    | "user";
</script>

<script lang="ts">
  let { name, size = 14 }: { name: IconName; size?: number } = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === "users"}
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c0-3.3 2.9-5.5 6.5-5.5s6.5 2.2 6.5 5.5" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M16.5 14.7c2.7.5 5 2.3 5 5.3" />
  {:else if name === "flag"}
    <path d="M5 21V4" />
    <path d="M5 4h13l-2.5 4L18 12H5" />
  {:else if name === "wand"}
    <path d="M6 21 18 9l-3-3L3 18z" />
    <path d="m15 6 3 3" />
    <path d="M19 3v3M17.5 4.5h3" />
  {:else if name === "map"}
    <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z" />
    <path d="M9 4v14" />
    <path d="M15 6v14" />
  {:else if name === "shield"}
    <path d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6z" />
  {:else if name === "sword"}
    <path d="M14.5 16.5 4 6V3.5h2.5L17 14" />
    <path d="m13.5 18.5 5-5" />
    <path d="m16.5 16.5 3.5 3.5" />
  {:else if name === "sparkle"}
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
  {:else if name === "scroll"}
    <path d="M6 4h12v13a3 3 0 0 1-3 3H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
    <path d="M9 9h6M9 13h6" />
  {:else if name === "dice"}
    <path d="M12 2l8.5 5v10L12 22l-8.5-5V7z" />
    <path d="M12 9.5 20.5 7M12 9.5 3.5 7M12 9.5V22" />
  {:else if name === "eye"}
    <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
    <circle cx="12" cy="12" r="2.5" />
  {:else if name === "grid"}
    <rect x="4" y="4" width="16" height="16" rx="1" />
    <path d="M4 12h16M12 4v16" />
  {:else if name === "refresh"}
    <path d="M21 12a9 9 0 1 1-2.6-6.4" />
    <path d="M21 3v6h-6" />
  {:else if name === "exit"}
    <path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  {:else if name === "next"}
    <path d="M5 5v14l10-7z" />
    <path d="M19 5v14" />
  {:else if name === "user"}
    <circle cx="12" cy="8" r="4" />
    <path d="M4.5 21c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5" />
  {/if}
</svg>
