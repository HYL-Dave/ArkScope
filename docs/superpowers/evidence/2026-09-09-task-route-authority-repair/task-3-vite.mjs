import { createServer } from "vite";
import { resolve } from "node:path";

const server = await createServer({
  envFile: false,
  cacheDir: resolve("../../tmp/task-3-ui/vite-cache"),
  server: { host: "127.0.0.1", port: 8467, strictPort: true, hmr: false },
});
await server.listen();
console.log("Task 3 isolated Vite ready");
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => { await server.close(); process.exit(0); });
}
