import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" => relative asset paths in the built index.html, so the Electron
// shell can load it via loadFile(dist/index.html) (file:// protocol).
//
// Dev-server port: ArkScope owns the 84xx block (sidecar default 8420, web dev
// 8430) to avoid clashing with the Vite 5173 default that other projects grab.
// Override both this and dev:desktop's URL by exporting ARKSCOPE_WEB_DEV_PORT.
const DEV_PORT = Number(process.env.ARKSCOPE_WEB_DEV_PORT) || 8430;

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: DEV_PORT, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true },
});
