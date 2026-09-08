import { fileURLToPath } from "node:url";
import path from "node:path";
import { createServer } from "vite";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../../../..");
const web = path.join(root, "apps/arkscope-web");
const api = process.env.INVESTIGATION_FIXTURE_API || "http://127.0.0.1:9000";
if (!/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(api)) throw new Error("An isolated localhost fixture API is required");
const server = await createServer({
  root: web, configFile: path.join(web, "vite.config.ts"), logLevel: "error",
  resolve: { alias: { "@app": path.join(web, "src") } },
  server: { host: "127.0.0.1", port: 5187, strictPort: false, fs: { allow: [root] },
    proxy: { "/fixture-api": { target: api, rewrite: value => value.slice("/fixture-api".length) } } },
  plugins: [{ name: "investigation-review-preview", configureServer(server) {
    server.middlewares.use(async (req, res, next) => {
      if (!req.url?.startsWith("/investigation-preview")) return next();
      res.setHeader("Content-Type", "text/html");
      res.end(await server.transformIndexHtml(req.url, `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" href="data:,"><title>ArkScope isolated investigation</title></head><body><div id="root"></div><script>window.arkscope={apiBase:location.origin+"/fixture-api"}</script><script type="module" src="/@fs${path.join(here, "preview.tsx")}"></script></body></html>`));
    });
  } }],
});
await server.listen();
console.log(JSON.stringify({ url: `http://127.0.0.1:${server.httpServer.address().port}/investigation-preview` }));
process.on("SIGTERM", async () => { await server.close(); process.exit(0); });
