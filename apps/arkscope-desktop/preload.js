"use strict";

// Bridges the per-run sidecar connection params (passed by main via
// webPreferences.additionalArguments) into the renderer as window.arkscope.

const { contextBridge } = require("electron");

function argValue(prefix) {
  const found = process.argv.find((a) => a.startsWith(prefix));
  return found ? found.slice(prefix.length) : undefined;
}

contextBridge.exposeInMainWorld("arkscope", {
  apiBase: argValue("--arkscope-api-base=") || "http://127.0.0.1:8420",
  apiToken: argValue("--arkscope-api-token=") || undefined,
});
