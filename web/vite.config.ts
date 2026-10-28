import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// One port per stack. `scripts/dev-stack.sh --workers N` runs N of everything so that a
// parallel e2e run has no shared database; each web server proxies to its own backend.
const API_PROXY = {
  "/api": {
    target: `http://127.0.0.1:${process.env.SBL_API_PORT ?? 8000}`,
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // `/api` goes to the backend, so the application never needs an absolute URL and there
  // is no CORS question in development. The same proxy is repeated for `preview`, which
  // does not inherit `server` — and `preview` is what the e2e suite runs against: a built
  // bundle answers a page load in a fraction of the time an unbundled dev server does,
  // and the suite is dominated by page loads.
  server: {
    port: 5173,
    proxy: API_PROXY,
  },
  preview: {
    port: 5173,
    proxy: API_PROXY,
  },
});
