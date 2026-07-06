import { defineConfig } from "vitest/config";

// Frontend unit tests (C-2 onward). Kept separate from vite.config.ts so the
// production build config stays untouched. The load-bearing C-2 logic — the SSE
// frame parser and the event→state reducer — is pure TS, so the default node
// environment is enough (no jsdom). Add jsdom only if a component test needs it.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
