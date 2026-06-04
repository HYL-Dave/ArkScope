import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" => relative asset paths in the built index.html, so the Electron
// shell can load it via loadFile(dist/index.html) (file:// protocol).
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true },
});
