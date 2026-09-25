import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Single-app: in dev the API is proxied to FastAPI (:8000) so the browser sees
// one origin; in production Vite builds static assets that FastAPI serves.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/healthz": "http://localhost:8000",
      "/readyz": "http://localhost:8000",
    },
  },
  // web/public holds the room photos (served as-is, /rooms/...).
  publicDir: "public",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
