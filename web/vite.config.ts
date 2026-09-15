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

// The development tools in a *built* bundle (`web/src/dev/devTools.ts`) are asked for with
// `VITE_DEV_TOOLS=true`. The public test instance on Render needs them, and Render's
// dashboard environment variables proved unreliable for this project (see docs/deploy.md,
// "Configuration — baked into the image"): the deployed bundle came out without the role
// switcher although render.yaml declared the variable. So the decision lives here, in git:
// Render names the service it is building in RENDER_SERVICE_NAME, and the one service
// called `sbl-web` is the throwaway test URL. A real deployment gets a different name
// and, with it, an ordinary production build. An explicit VITE_DEV_TOOLS still wins.
if (process.env.RENDER_SERVICE_NAME === "sbl-web") {
  process.env.VITE_DEV_TOOLS ??= "true";
}

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
