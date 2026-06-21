"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { shouldOpenExternal } = require("./navigation");

test("opens OAuth/browser URLs externally instead of inside the Electron shell", () => {
  assert.equal(
    shouldOpenExternal(
      "https://auth.openai.com/oauth/authorize?client_id=app_x",
      "http://127.0.0.1:8430/settings",
    ),
    true,
  );
});

test("keeps same-origin renderer navigation inside Electron", () => {
  assert.equal(
    shouldOpenExternal("http://127.0.0.1:8430/settings", "http://127.0.0.1:8430/"),
    false,
  );
});

test("ignores non-http URLs", () => {
  assert.equal(shouldOpenExternal("file:///tmp/index.html", "file:///tmp/app.html"), false);
});
