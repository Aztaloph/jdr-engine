<script lang="ts">
  let {
    label,
    variant = "muted",
  }: {
    label: string;
    variant?: "accent" | "muted" | "success" | "danger";
  } = $props();
</script>

<span
  class="badge"
  class:accent={variant === "accent"}
  class:muted={variant === "muted"}
  class:success={variant === "success"}
  class:danger={variant === "danger"}
>{label}</span>

<style>
  .badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    white-space: nowrap;
  }

  .accent {
    color: var(--color-accent);
    background: var(--color-accent-muted);
    border: 1px solid var(--color-accent);
  }

  .muted {
    color: var(--color-text-muted);
    background: transparent;
    border: 1px solid var(--color-border-subtle);
  }

  .success {
    color: var(--color-success);
    background: rgb(34 197 94 / 0.12);
    border: 1px solid var(--color-success);
  }

  .danger {
    color: var(--color-danger);
    background: var(--color-error-bg);
    border: 1px solid var(--color-danger);
  }
</style>
