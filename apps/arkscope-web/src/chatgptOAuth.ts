// Pure state machine for the in-app ChatGPT OAuth login — extracted from the React
// glue so it is unit-testable without a DOM, a browser, or a real backend (mirrors
// researchProvider.ts). The Settings component injects the real status client + a
// real clock/sleep; tests inject fakes.
import type { OAuthStatusResult, ProviderCredential } from "./api";

export type PollResult =
  | { kind: "success"; credential: ProviderCredential | null }
  | { kind: "error"; detail: string }
  | { kind: "unknown" }
  | { kind: "timeout" };

export interface PollOptions {
  statusFn: (state: string) => Promise<OAuthStatusResult>;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  timeoutMs?: number;
  intervalMs?: number;
}

const DEFAULT_TIMEOUT_MS = 180_000; // generous: the user is logging in via a browser
const DEFAULT_INTERVAL_MS = 1_500;

// Poll /status until the login reaches a terminal state, or the wall-clock budget
// is exhausted. Terminal: success / error (carry the backend detail — NO silent
// fallback) / unknown (the login was never tracked or was evicted → stop, don't
// spin). Timeout returns its own kind so the UI can offer the manual fallback.
export async function pollOAuthStatus(state: string, opts: PollOptions): Promise<PollResult> {
  const { statusFn, now, sleep } = opts;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const intervalMs = opts.intervalMs ?? DEFAULT_INTERVAL_MS;
  const start = now();
  for (;;) {
    const s = await statusFn(state);
    if (s.status === "success") return { kind: "success", credential: s.credential };
    if (s.status === "error") return { kind: "error", detail: s.detail ?? "unknown error" };
    if (s.status === "unknown") return { kind: "unknown" };
    // still pending
    if (now() - start >= timeoutMs) return { kind: "timeout" };
    await sleep(intervalMs);
  }
}

// The copy-code fallback accepts either a bare authorization code or the whole
// pasted redirect URL; pick the right field for the backend (which validates state
// + extracts the code from a URL). A value that looks like a callback URL goes as
// `redirect_url` (so the backend can state-match it); otherwise it's a bare `code`.
export function buildManualCompletion(
  state: string,
  pasted: string,
): { state: string; code?: string; redirect_url?: string } {
  const v = pasted.trim();
  const looksLikeUrl = /^https?:\/\//i.test(v) || v.includes("?code=") || v.includes("&code=");
  return looksLikeUrl ? { state, redirect_url: v } : { state, code: v };
}
