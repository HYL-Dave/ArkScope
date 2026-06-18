// Helpers for the direct "pick a model" Settings selector (provider is an
// attribute of the model, not a prerequisite step). Pure + unit-tested.
import type { ModelProvider } from "./api";

// Sentinel select value for "enter a custom model id".
export const MODEL_OPTION_CUSTOM = "__custom__";

// A catalog option is encoded as "<provider>:<modelId>" so one <select> can list
// models across providers and picking one yields both provider and model.
export function encodeModelOption(provider: ModelProvider, model: string): string {
  return `${provider}:${model}`;
}

export function decodeModelOption(value: string): { provider: ModelProvider; model: string } | null {
  const i = value.indexOf(":");
  if (i <= 0) return null;
  const provider = value.slice(0, i);
  const model = value.slice(i + 1);
  if (provider !== "openai" && provider !== "anthropic") return null;
  if (!model) return null;
  return { provider, model };
}

// Infer provider from a custom model id by prefix (mirrors the backend
// model_provider): claude-* → anthropic; gpt-*/o1/o3/o4 → openai; else null
// (caller keeps the current provider when inference is ambiguous).
export function inferProvider(modelId: string): ModelProvider | null {
  const m = modelId.trim().toLowerCase();
  if (!m) return null;
  if (m.startsWith("claude")) return "anthropic";
  if (m.startsWith("gpt") || /^o[134](-|$)/.test(m)) return "openai";
  return null;
}
