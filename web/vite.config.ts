import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Proxy /v1 → API FastAPI locale (pas de CORS côté Python dans ce lot).
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
