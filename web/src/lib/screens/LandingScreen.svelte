<script lang="ts">
  import LandingNav from "../components/landing/LandingNav.svelte";
  import Hero from "../components/landing/Hero.svelte";
  import HowItWorks from "../components/landing/HowItWorks.svelte";
  import FeatureGrid from "../components/landing/FeatureGrid.svelte";
  import ApiShowcase from "../components/landing/ApiShowcase.svelte";
  import StatsSection from "../components/landing/StatsSection.svelte";
  import FinalCta from "../components/landing/FinalCta.svelte";
  import LandingFooter from "../components/landing/LandingFooter.svelte";
</script>

<div class="landing">
  <LandingNav />
  <main>
    <Hero />
    <HowItWorks />
    <FeatureGrid />
    <ApiShowcase />
    <StatsSection />
    <FinalCta />
  </main>
  <LandingFooter />
</div>

<style>
  .landing {
    min-height: 100vh;
    background: var(--color-bg-base);
  }
</style>
