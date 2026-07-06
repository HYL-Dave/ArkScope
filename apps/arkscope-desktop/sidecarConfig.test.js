"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  clearSidecarApiConfig,
  stopSidecarCleanup,
  writeSidecarApiConfig,
} = require("./sidecarConfig");

function tmpConfig() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "arkscope-sidecar-config-"));
  return path.join(dir, ".config", "arkscope", "sa_native_host.json");
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

test("writes api fields into an absent native host config", () => {
  const cfg = tmpConfig();

  writeSidecarApiConfig(cfg, {
    apiBase: "http://127.0.0.1:45678",
    apiToken: "token-1",
  });

  assert.deepEqual(readJson(cfg), {
    api_base: "http://127.0.0.1:45678",
    api_token: "token-1",
  });
  assert.equal(fs.statSync(cfg).mode & 0o777, 0o600);
  assert.deepEqual(fs.readdirSync(path.dirname(cfg)).filter((name) => name.includes(".tmp")), []);
});

test("preserves existing launcher fields when writing api fields", () => {
  const cfg = tmpConfig();
  fs.mkdirSync(path.dirname(cfg), { recursive: true });
  fs.writeFileSync(
    cfg,
    JSON.stringify({
      project_root: "/repo",
      python_path: "/venv/bin/python",
      host_script: "/repo/src/sa_native_host.py",
    }),
  );

  writeSidecarApiConfig(cfg, {
    apiBase: "http://127.0.0.1:45678",
    apiToken: "token-1",
  });

  assert.deepEqual(readJson(cfg), {
    project_root: "/repo",
    python_path: "/venv/bin/python",
    host_script: "/repo/src/sa_native_host.py",
    api_base: "http://127.0.0.1:45678",
    api_token: "token-1",
  });
});

test("clear removes only api fields and tolerates absent config", () => {
  const absent = tmpConfig();
  clearSidecarApiConfig(absent);

  const cfg = tmpConfig();
  fs.mkdirSync(path.dirname(cfg), { recursive: true });
  fs.writeFileSync(
    cfg,
    JSON.stringify({
      project_root: "/repo",
      python_path: "/venv/bin/python",
      host_script: "/repo/src/sa_native_host.py",
      api_base: "http://127.0.0.1:45678",
      api_token: "token-1",
    }),
  );

  clearSidecarApiConfig(cfg);

  assert.deepEqual(readJson(cfg), {
    project_root: "/repo",
    python_path: "/venv/bin/python",
    host_script: "/repo/src/sa_native_host.py",
  });
});

test("stop cleanup clears api fields even when there is no live sidecar", () => {
  for (const child of [null, { exitCode: 0 }]) {
    const cfg = tmpConfig();
    fs.mkdirSync(path.dirname(cfg), { recursive: true });
    fs.writeFileSync(cfg, JSON.stringify({ api_base: "http://127.0.0.1:1", api_token: "t" }));
    const signals = [];

    stopSidecarCleanup(child, cfg, {
      kill: (_proc, signal) => signals.push(signal),
      scheduleKill: () => {},
    });

    assert.deepEqual(readJson(cfg), {});
    assert.deepEqual(signals, []);
  }
});

test("stop cleanup clears api fields before killing a running sidecar", () => {
  const cfg = tmpConfig();
  fs.mkdirSync(path.dirname(cfg), { recursive: true });
  fs.writeFileSync(cfg, JSON.stringify({ api_base: "http://127.0.0.1:1", api_token: "t" }));
  const signals = [];
  const child = { exitCode: null };

  stopSidecarCleanup(child, cfg, {
    kill: (_proc, signal) => {
      signals.push({ signal, cfg: readJson(cfg) });
    },
    scheduleKill: () => {},
  });

  assert.deepEqual(signals, [{ signal: "SIGTERM", cfg: {} }]);
});
