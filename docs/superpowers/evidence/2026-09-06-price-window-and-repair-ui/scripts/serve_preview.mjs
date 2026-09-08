import { fileURLToPath } from "node:url";
import path from "node:path";
import { createServer } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../../../..");
const web = path.join(root, "apps/arkscope-web");
const entry = `/@fs${path.join(here, "preview.tsx")}`;
const server = await createServer({
  root: web, configFile: path.join(web, "vite.config.ts"), logLevel: "error",
  resolve: { alias: { "@app": path.join(web, "src") } },
  server: { host: "127.0.0.1", port: 0, strictPort: false, fs: { allow: [root] } },
  plugins: [{ name: "price-repair-fixture", configureServer(server) {
    server.middlewares.use(async (req, res, next) => {
      if (!req.url?.startsWith("/price-repair-preview")) return next();
      res.setHeader("Content-Type", "text/html");
      res.end(await server.transformIndexHtml(req.url, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,"><title>Price repair fixture</title></head><body><div id="root"></div><script type="module" src="${entry}"></script></body></html>`));
    });
  } }],
});
await server.listen();
console.log(JSON.stringify({ url: `http://127.0.0.1:${server.httpServer.address().port}/price-repair-preview` }));
process.on("SIGTERM", async () => { await server.close(); process.exit(0); });
