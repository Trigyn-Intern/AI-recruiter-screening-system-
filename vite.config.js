import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "frontend",
  server: {
    host: "0.0.0.0",
    port: 3000,
    hmr: false,
    ws: false,
  },
  plugins: [react()],
});
