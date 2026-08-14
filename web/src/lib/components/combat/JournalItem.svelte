<script lang="ts">
  import Icon from "./Icon.svelte";
  import {
    presentJournalEntry,
    type JournalNameTone,
  } from "../../combat/journalPresentation";

  let {
    kind,
    summary,
    detail,
    eventType = "",
    time = "",
    nameTones = new Map<string, JournalNameTone>(),
  }: {
    kind: "attack" | "spell" | "system";
    summary: string;
    detail: string;
    eventType?: string;
    time?: string;
    nameTones?: Map<string, JournalNameTone>;
  } = $props();

  const presentation = $derived(
    presentJournalEntry(
      { kind, summary, detail, event_type: eventType },
      nameTones,
    ),
  );
</script>

<li
  class="entry"
  class:attack={kind === "attack"}
  class:spell={kind === "spell"}
  class:system={kind === "system"}
>
  <div class="entry-icon" aria-hidden="true">
    <Icon name={presentation.icon} size={14} />
  </div>
  <div class="entry-body">
    <div class="entry-top">
      <p class="entry-summary">
        {#each presentation.segments as segment, index (index)}
          {#if segment.tone === "plain" || segment.tone === "muted"}
            <span class="plain">{segment.text}</span>
          {:else}
            <span class="actor actor-{segment.tone}">{segment.text}</span>
          {/if}
        {/each}
      </p>
      {#if time}
        <span class="entry-time mono">{time}</span>
      {/if}
    </div>
    {#if presentation.chips.length > 0}
      <ul class="entry-chips">
        {#each presentation.chips as chip (chip.label)}
          <li class="chip chip-{chip.variant}">{chip.label}</li>
        {/each}
      </ul>
    {/if}
  </div>
</li>

<style>
  .entry {
    display: flex;
    gap: 0.6rem;
    padding: 0.55rem 0.65rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border-subtle);
    background:
      linear-gradient(135deg, rgb(255 255 255 / 0.02), transparent 55%),
      var(--color-bg-panel);
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .entry.attack {
    border-left: 3px solid rgb(248 113 113 / 0.75);
  }

  .entry.spell {
    border-left: 3px solid rgb(245 158 11 / 0.85);
  }

  .entry.system {
    border-left: 3px solid rgb(148 163 184 / 0.45);
    opacity: 0.92;
  }

  .entry-icon {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
    background: rgb(0 0 0 / 0.25);
    border: 1px solid var(--color-border-subtle);
  }

  .entry.attack .entry-icon {
    color: #fca5a5;
    border-color: rgb(248 113 113 / 0.35);
    background: rgb(248 113 113 / 0.08);
  }

  .entry.spell .entry-icon {
    color: var(--color-accent);
    border-color: rgb(245 158 11 / 0.35);
    background: rgb(245 158 11 / 0.08);
  }

  .entry-body {
    min-width: 0;
    flex: 1;
  }

  .entry-top {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
  }

  .entry-summary {
    margin: 0;
    flex: 1;
    min-width: 0;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .plain {
    color: var(--color-text-primary);
  }

  .actor {
    font-weight: 700;
  }

  .actor-self {
    color: #93c5fd;
  }

  .actor-ally {
    color: #7dd3fc;
  }

  .actor-foe {
    color: #fca5a5;
  }

  .entry-time {
    flex-shrink: 0;
    font-size: 0.65rem;
    color: var(--color-text-muted);
    padding-top: 0.12rem;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .entry-chips {
    list-style: none;
    margin: 0.35rem 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.12rem 0.42rem;
    border-radius: 999px;
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .chip-damage {
    color: #fecaca;
    background: rgb(239 68 68 / 0.12);
    border-color: rgb(239 68 68 / 0.35);
  }

  .chip-roll {
    color: #fde68a;
    background: rgb(245 158 11 / 0.1);
    border-color: rgb(245 158 11 / 0.35);
  }

  .chip-success {
    color: #bbf7d0;
    background: rgb(34 197 94 / 0.12);
    border-color: rgb(34 197 94 / 0.35);
  }

  .chip-fail {
    color: #fecaca;
    background: rgb(239 68 68 / 0.1);
    border-color: rgb(239 68 68 / 0.3);
  }

  .chip-info {
    color: #cbd5e1;
    background: rgb(148 163 184 / 0.1);
    border-color: rgb(148 163 184 / 0.28);
  }

  .chip-system {
    color: var(--color-text-muted);
    background: rgb(255 255 255 / 0.03);
    border-color: var(--color-border-subtle);
    text-transform: none;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
</style>
