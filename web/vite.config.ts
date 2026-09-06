import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Anfragen an /api gehen an das Backend. So braucht die Anwendung im Browser keine
    // absolute URL zu kennen und es gibt in der Entwicklung kein CORS-Thema.
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
