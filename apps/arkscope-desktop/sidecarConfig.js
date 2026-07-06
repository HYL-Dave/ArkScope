"use strict";

const fs = require("node:fs");
const path = require("node:path");

function nativeHostConfigPath() {
  if (process.env.ARKSCOPE_SA_NATIVE_HOST_CONFIG) {
    return process.env.ARKSCOPE_SA_NATIVE_HOST_CONFIG;
  }
  const home = process.env.HOME || process.env.USERPROFILE || "";
  return path.join(home, ".config", "arkscope", "sa_native_host.json");
}

function readConfig(configPath) {
  if (!fs.existsSync(configPath)) return {};
  return JSON.parse(fs.readFileSync(configPath, "utf8"));
}

function writeJsonAtomic(configPath, data) {
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  const tmp = `${configPath}.tmp-${process.pid}-${Date.now()}`;
  try {
    fs.writeFileSync(tmp, `${JSON.stringify(data, null, 2)}\n`, { mode: 0o600 });
    fs.renameSync(tmp, configPath);
    fs.chmodSync(configPath, 0o600);
  } finally {
    if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
  }
}

function writeSidecarApiConfig(configPath, { apiBase, apiToken }) {
  const cfg = readConfig(configPath);
  cfg.api_base = apiBase;
  cfg.api_token = apiToken;
  writeJsonAtomic(configPath, cfg);
}

function clearSidecarApiConfig(configPath) {
  if (!fs.existsSync(configPath)) return;
  const cfg = readConfig(configPath);
  delete cfg.api_base;
  delete cfg.api_token;
  writeJsonAtomic(configPath, cfg);
}

function stopSidecarCleanup(child, configPath, options = {}) {
  const kill = options.kill || ((proc, signal) => proc.kill(signal));
  const scheduleKill = options.scheduleKill || ((fn, ms) => setTimeout(fn, ms));
  const onError = options.onError || (() => {});

  try {
    clearSidecarApiConfig(configPath);
  } catch (error) {
    onError(error);
  }

  if (!child || child.exitCode !== null) {
    return { stopped: false };
  }

  try {
    kill(child, "SIGTERM");
  } catch (error) {
    onError(error);
  }
  scheduleKill(() => {
    try {
      kill(child, "SIGKILL");
    } catch (error) {
      onError(error);
    }
  }, 4000);
  return { stopped: true };
}

module.exports = {
  clearSidecarApiConfig,
  nativeHostConfigPath,
  stopSidecarCleanup,
  writeSidecarApiConfig,
};
