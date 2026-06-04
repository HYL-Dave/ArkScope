"use strict";

// ArkScope desktop shell (Electron main).
//
// Lifecycle (spike): find a free 127.0.0.1 port -> spawn the Python sidecar
// (`python -m src.api`) bound to it with a per-run token and reload off ->
// poll /healthz until ready -> load the built web cockpit (or an error screen)
// -> kill the sidecar cleanly on quit.

const { app, BrowserWindow } = require("electron");
const { spawn } = require("node:child_process");
const net = require("node:net");
const crypto = require("node:crypto");
const http = require("node:http");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_DIST = path.join(__dirname, "..", "arkscope-web", "dist", "index.html");
const PYTHON = process.env.ARKSCOPE_PYTHON || "python";

let sidecar = null;
let win = null;
const stderrTail = [];

function pushTail(buf) {
  for (const line of buf.toString().split("\n")) {
    if (line.trim()) stderrTail.push(line);
  }
  while (stderrTail.length > 40) stderrTail.shift();
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function ping(port, token) {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host: "127.0.0.1",
        port,
        path: "/healthz",
        headers: { "x-arkscope-token": token },
        timeout: 1500,
      },
      (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      },
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitForHealth(port, token, timeoutMs = 40000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (sidecar && sidecar.exitCode !== null) return false; // process died
    if (await ping(port, token)) return true;
    await delay(500);
  }
  return false;
}

function startSidecar(port, token) {
  sidecar = spawn(PYTHON, ["-m", "src.api"], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      ARKSCOPE_API_HOST: "127.0.0.1",
      ARKSCOPE_API_PORT: String(port),
      ARKSCOPE_API_TOKEN: token,
      ARKSCOPE_API_RELOAD: "0",
      PYTHONUNBUFFERED: "1",
    },
  });
  sidecar.stdout.on("data", pushTail);
  sidecar.stderr.on("data", pushTail);
  sidecar.on("error", (e) => pushTail(Buffer.from(`[spawn error] ${e.message}`)));
  sidecar.on("exit", (code) => pushTail(Buffer.from(`[sidecar exited code=${code}]`)));
}

function stopSidecar() {
  if (!sidecar || sidecar.exitCode !== null) return;
  const child = sidecar;
  sidecar = null;
  try {
    child.kill("SIGTERM");
  } catch {
    /* already gone */
  }
  setTimeout(() => {
    try {
      child.kill("SIGKILL");
    } catch {
      /* already gone */
    }
  }, 4000);
}

async function createWindow() {
  const port = await findFreePort();
  const token = crypto.randomBytes(24).toString("hex");
  const apiBase = `http://127.0.0.1:${port}`;

  startSidecar(port, token);

  win = new BrowserWindow({
    width: 1440,
    height: 900,
    backgroundColor: "#0e1116",
    title: "ArkScope",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [
        `--arkscope-api-base=${apiBase}`,
        `--arkscope-api-token=${token}`,
      ],
    },
  });

  const ready = await waitForHealth(port, token);
  if (!ready) {
    const msg = stderrTail.join("\n") || "sidecar did not become healthy in time";
    await win.loadFile(path.join(__dirname, "error.html"), {
      search: "msg=" + encodeURIComponent(msg),
    });
    return;
  }

  const devUrl = process.env.ARKSCOPE_WEB_DEV_URL;
  if (devUrl) {
    await win.loadURL(devUrl);
  } else {
    await win.loadFile(WEB_DIST);
  }
}

app.whenReady().then(createWindow);

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("window-all-closed", () => {
  stopSidecar();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopSidecar);
process.on("exit", stopSidecar);
