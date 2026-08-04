import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the React frontend.
//
// server.host = true           -> bind on 0.0.0.0 so Docker and other
//                                 containers (e.g. OWASP ZAP) can reach
//                                 the dev server.
// server.allowedHosts          -> let ZAP and other tools hit us via
//                                 host.docker.internal / localhost.
//                                 Without this, Vite returns 403 with
//                                 "Blocked request. This host ... is
//                                 not allowed."
//
// These are dev-server settings only. The production build (vite build)
// is unaffected.
export default defineConfig({
  server: {
    host: true,
    hmr: false,
    allowedHosts: [
      "host.docker.internal",
      "localhost",
      "127.0.0.1",
    ],
  },
  plugins: [react()],
});
