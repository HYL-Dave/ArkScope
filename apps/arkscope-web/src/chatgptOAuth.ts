// Pure state machine for the in-app ChatGPT OAuth login — extracted from the React
// glue so it is unit-testable without a DOM, a browser, or a real backend (mirrors
// researchProvider.ts). The Settings component injects the real status client + a
// real clock/sleep; tests inject fakes.
import type { OAuthStatusResult, ProbeResult, ProviderCredential } from "./api";

export type PollResult =
  | { kind: "success"; credential: ProviderCredential | null }
  // manualCompletable (F4): false when the backend consumed the single-use state
  // (completion failed after the callback arrived) — a manual paste can never
  // succeed then, so the UI must not offer it. Absent/true = fallback still valid.
  | { kind: "error"; detail: string; manualCompletable: boolean }
  | { kind: "unknown" }
  | { kind: "timeout" }
  | { kind: "aborted" };

export interface PollOptions {
  statusFn: (state: string) => Promise<OAuthStatusResult>;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  timeoutMs?: number;
  intervalMs?: number;
  // Cooperative cancel: when this returns true the poll stops with {kind:"aborted"}
  // (e.g. the manual copy-code completion won, or the user cancelled) so a superseded
  // login neither keeps hitting the backend nor pins the "登入" button busy.
  shouldAbort?: () => boolean;
}

const DEFAULT_TIMEOUT_MS = 180_000; // generous: the user is logging in via a browser
const DEFAULT_INTERVAL_MS = 1_500;

// Poll /status until the login reaches a terminal state, or the wall-clock budget
// is exhausted. Terminal: success / error (carry the backend detail — NO silent
// fallback) / unknown (the login was never tracked or was evicted → stop, don't
// spin). Timeout returns its own kind so the UI can offer the manual fallback.
export async function pollOAuthStatus(state: string, opts: PollOptions): Promise<PollResult> {
  const { statusFn, now, sleep, shouldAbort } = opts;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const intervalMs = opts.intervalMs ?? DEFAULT_INTERVAL_MS;
  const start = now();
  for (;;) {
    if (shouldAbort?.()) return { kind: "aborted" };
    const s = await statusFn(state);
    // Round-5 SF: a cancel can land while the request is in flight — re-check
    // before treating the (now superseded) response as a terminal outcome.
    if (shouldAbort?.()) return { kind: "aborted" };
    if (s.status === "success") return { kind: "success", credential: s.credential };
    if (s.status === "error") {
      return { kind: "error", detail: s.detail ?? "unknown error", manualCompletable: s.manual_completable !== false };
    }
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

export function probeDisplayLabel(name: string): string {
  if (name.startsWith("P1")) return "Token / backend";
  if (name.startsWith("P2a")) return "參數相容性";
  if (name.startsWith("P2b")) return "工具呼叫";
  if (name.startsWith("P2c")) return "可用模型";
  return name;
}

export function extractProbeModels(observed: string): string[] {
  const match = observed.match(/model ids:\s*(.+)$/i);
  if (!match) return [];
  return match[1]
    .replace(/\s*\(\+\d+\s+more\)\s*$/i, "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function probeDisplaySummary(probe: ProbeResult): { text: string; models: string[] } {
  if (probe.error) return { text: probe.error, models: [] };
  if (probe.name.startsWith("P1")) {
    return { text: probe.passed ? "OAuth 不是 public API key；ChatGPT backend 可 streaming" : probe.observed, models: [] };
  }
  if (probe.name.startsWith("P2a")) {
    return { text: probe.passed ? "backend 會拒絕 max_output_tokens；driver 需移除此參數" : probe.observed, models: [] };
  }
  if (probe.name.startsWith("P2b")) {
    return { text: probe.passed ? "function-call streaming 可用" : probe.observed, models: [] };
  }
  if (probe.name.startsWith("P2c")) {
    const models = extractProbeModels(probe.observed);
    return { text: models.length ? "可用模型" : probe.observed, models };
  }
  return { text: probe.observed, models: [] };
}

export function probeRuntimeNote(authType: ProviderCredential["auth_type"]): string | null {
  if (authType === "chatgpt_oauth") {
    return "會向 api.openai.com 與 ChatGPT backend 發出最小診斷請求，確認 token 類型、streaming、工具呼叫與可用模型；不回傳 token，可能消耗少量訂閱額度。";
  }
  if (authType === "claude_code_oauth") {
    return "會執行 claude -p 並向 api.anthropic.com 做最小診斷請求，確認 setup-token 可用且 raw SDK 會拒絕該 token；不回傳 token，可能消耗少量訂閱額度。";
  }
  return null;
}
