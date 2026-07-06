#!/usr/bin/env node
// Self-sufficient dev launcher: `npm run dev:desktop` previously ONLY started
// Electron and assumed the Vite dev server (8430) was already running in another
// terminal — a bare run died with ERR_CONNECTION_REFUSED. This spawns vite,
// waits until the dev URL actually responds, then launches Electron, and tears
// both down together (closing the app window stops vite; vite dying closes the
// app). Zero new dependencies.
//
//   ARKSCOPE_WEB_DEV_PORT       dev-server port (default 8430, matches vite.config.ts)
//   ARKSCOPE_DEV_NO_ELECTRON=1  start+wait vite only (smoke/CI use)

const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");
const { clearSidecarApiConfig, nativeHostConfigPath } = require("./sidecarConfig");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const PORT = process.env.ARKSCOPE_WEB_DEV_PORT || "8430";
const URL = `http://127.0.0.1:${PORT}`;
const WAIT_MS = 60_000;

let vite = null;
let electron = null;
let shuttingDown = false;

function killTree(child) {
  // Children are spawned detached (own process group): killing just the npm
  // wrapper ORPHANS the real vite/electron underneath (verified — vite kept
  // serving after wrapper death). kill(-pid) signals the whole group.
  if (!child || child.exitCode != null) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (e) {
    if (e.code !== "ESRCH") {
      try { child.kill("SIGTERM"); } catch { /* already gone */ }
    }
  }
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  try {
    clearSidecarApiConfig(nativeHostConfigPath());
  } catch (e) {
    console.error(`[dev] native host config cleanup failed: ${e.message || e}`);
  }
  killTree(vite);
  killTree(electron);
  setTimeout(() => process.exit(code), 500); // let the groups die first
}

function ping(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode != null);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1_000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForUrl(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await ping(url)) return true;
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

async function main() {
  // vite.config.ts uses strictPort; if OUR previous vite is still up, reuse it.
  const alreadyUp = await ping(URL);

  if (!alreadyUp) {
    console.log(`[dev] starting vite dev server on ${URL} ...`);
    vite = spawn("npm", ["run", "dev", "--workspace", "apps/arkscope-web"], {
      cwd: REPO_ROOT,
      stdio: ["ignore", "inherit", "inherit"],
      env: { ...process.env, ARKSCOPE_WEB_DEV_PORT: PORT },
      detached: true, // own process group → killTree can take npm AND vite
    });
    vite.on("exit", (code) => {
      // vite dying first would leave a blank window — stop everything.
      if (!shuttingDown) {
        console.error(`[dev] vite exited (${code}); shutting down.`);
        shutdown(code ?? 1);
      }
    });
  } else {
    console.log(`[dev] vite already running on ${URL} — reusing it.`);
  }

  if (!(await waitForUrl(URL, WAIT_MS))) {
    console.error(`[dev] vite did not respond on ${URL} within ${WAIT_MS / 1000}s.`);
    shutdown(1);
    return;
  }

  if (process.env.ARKSCOPE_DEV_NO_ELECTRON === "1") {
    console.log("[dev] ARKSCOPE_DEV_NO_ELECTRON=1 — vite is up; skipping electron.");
    shutdown(0);
    return;
  }

  console.log(`[dev] starting electron (renderer: ${URL}) ...`);
  electron = spawn("npm", ["run", "start", "--workspace", "apps/arkscope-desktop"], {
    cwd: REPO_ROOT,
    stdio: "inherit",
    env: { ...process.env, ARKSCOPE_WEB_DEV_URL: URL },
    detached: true, // own process group → killTree can take npm AND electron
  });
  electron.on("exit", (code) => shutdown(code ?? 0));
}

process.on("SIGINT", () => shutdown(130));
process.on("SIGTERM", () => shutdown(143));

main().catch((e) => {
  console.error("[dev] launcher failed:", e);
  shutdown(1);
});
