/**
 * Action Svelte — apparition douce au scroll (IntersectionObserver).
 * Respecte `prefers-reduced-motion` : contenu affiché sans animation.
 */
export function reveal(
  node: HTMLElement,
  options: { delay?: number } = {},
): { destroy?: () => void } {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || typeof IntersectionObserver === "undefined") {
    node.classList.add("is-revealed");
    return {};
  }

  node.classList.add("reveal-init");
  if (options.delay) {
    node.style.transitionDelay = `${options.delay}ms`;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          node.classList.add("is-revealed");
          observer.disconnect();
        }
      }
    },
    { threshold: 0.12 },
  );
  observer.observe(node);

  return {
    destroy: () => observer.disconnect(),
  };
}
