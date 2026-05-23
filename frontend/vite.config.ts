import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, the API and probes are proxied to the backend so the frontend can use
// same-origin relative paths (no CORS dance). In production, nginx does the same
// proxying (see nginx.conf). Override the backend target with VITE_PROXY_TARGET.
const target = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/health": { target, changeOrigin: true },
    },
  },
});
