import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser calls /api/... on this dev server, and Vite forwards it to the backend.
// So the browser only talks to its own origin and no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});