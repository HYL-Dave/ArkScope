import { describe, expect, it } from "vitest";
import i18n from "i18next";

import {
  activeFirst,
  addApiKeyButtonLabel,
  addApiKeySuccessMessage,
  credentialPill,
  credentialAvailabilityText,
  defaultMakeActiveOnAdd,
  discoverButtonLabel,
  discoveryHeaderTitle,
  discoveryResultCredentialLabel,
  discoverySourceLabel,
  supportsCredentialExpiry,
  isoToDateInput,
  dateInputToIso,
} from "./credentialDisplay";
import type { SettingsT } from "./settings/settingsCopy";

function settingsT(locale: "zh-Hant" | "en"): SettingsT {
  return i18n.getFixedT(locale, "settings") as SettingsT;
}

const zhT = settingsT("zh-Hant");

describe("activeFirst", () => {
  it("moves the active credential to the front, preserving the rest's order", () => {
    const rows = [{ id: "a", active: false }, { id: "b", active: true }, { id: "c", active: false }];
    expect(activeFirst(rows).map((r) => r.id)).toEqual(["b", "a", "c"]);
  });
  it("is a no-op when the first is already active or none is active", () => {
    expect(activeFirst([{ id: "x", active: true }, { id: "y", active: false }]).map((r) => r.id)).toEqual(["x", "y"]);
    expect(activeFirst([{ id: "x", active: false }, { id: "y", active: false }]).map((r) => r.id)).toEqual(["x", "y"]);
  });
  it("does not mutate the input + handles empty", () => {
    const rows = [{ id: "a", active: false }, { id: "b", active: true }];
    activeFirst(rows);
    expect(rows.map((r) => r.id)).toEqual(["a", "b"]);  // original order intact
    expect(activeFirst([])).toEqual([]);
  });
});

describe("discoverySourceLabel", () => {
  it("distinguishes OpenAI API vs ChatGPT backend (both provider_api at the data layer)", () => {
    expect(discoverySourceLabel("openai", "api_key", "provider_api", zhT)).toBe("OpenAI API · 已取得可見模型清單");
    expect(discoverySourceLabel("openai", "chatgpt_oauth", "provider_api", zhT)).toBe("ChatGPT 訂閱 · 已取得可見模型清單");
  });
  it("labels Anthropic API", () => {
    expect(discoverySourceLabel("anthropic", "api_key", "provider_api", zhT)).toBe("Anthropic API · 已取得可見模型清單");
  });
  it("labels seed candidates as non-live regardless of provider/mode", () => {
    expect(discoverySourceLabel("anthropic", "claude_code_oauth", "seed", zhT)).toBe("候選模型是 seed 清單，不是即時 discovery。");
    expect(discoverySourceLabel("openai", "api_key", "seed", zhT)).toBe("候選模型是 seed 清單，不是即時 discovery。");
  });
});

describe("credentialPill", () => {
  it("reflects the active credential's auth mode (not just key set/no key)", () => {
    expect(credentialPill({ auth_type: "api_key" }, zhT)).toEqual({ label: "API key", ok: true });
    expect(credentialPill({ auth_type: "chatgpt_oauth" }, zhT)).toEqual({ label: "ChatGPT 訂閱", ok: true });
    expect(credentialPill({ auth_type: "claude_code_oauth" }, zhT)).toEqual({ label: "Claude 訂閱", ok: true });
  });
  it("says no credential when none active", () => {
    expect(credentialPill(null, zhT)).toEqual({ label: "尚未設定此 provider 的登入", ok: false });
  });
});

describe("credential row metadata display", () => {
  it("uses short availability copy so rows don't stretch on non-secret OAuth credentials", () => {
    expect(credentialAvailabilityText({ available: true, masked: null }, zhT)).toBe("可用");
    expect(credentialAvailabilityText({ available: true, masked: "sk-p...Q2wA" }, zhT)).toBe("sk-p...Q2wA");
    expect(credentialAvailabilityText({ available: false, masked: null }, zhT)).toBe("目前無法使用");
  });

  it("shows an expiry editor ONLY for claude_code_oauth (chatgpt_oauth auto-refreshes; api_key has no expiry)", () => {
    expect(supportsCredentialExpiry("api_key")).toBe(false);
    expect(supportsCredentialExpiry("api_key_pool")).toBe(false);
    expect(supportsCredentialExpiry("chatgpt_oauth")).toBe(false); // token auto-refreshes → no manual expiry
    expect(supportsCredentialExpiry("claude_code_oauth")).toBe(true); // setup-token: informational, user-set
  });
});

describe("expiry date-input conversion", () => {
  it("isoToDateInput: ISO timestamp → YYYY-MM-DD (date-picker value)", () => {
    expect(isoToDateInput("2027-06-22T00:00:00+00:00")).toBe("2027-06-22");
    expect(isoToDateInput("2027-06-22T15:30:00Z")).toBe("2027-06-22");
  });
  it("isoToDateInput: empty / null / unparseable → empty string", () => {
    expect(isoToDateInput("")).toBe("");
    expect(isoToDateInput(null)).toBe("");
    expect(isoToDateInput(undefined)).toBe("");
    expect(isoToDateInput("not-a-date")).toBe("");
  });
  it("dateInputToIso: YYYY-MM-DD → canonical UTC-midnight ISO", () => {
    expect(dateInputToIso("2027-06-22")).toBe("2027-06-22T00:00:00+00:00");
  });
  it("dateInputToIso: empty → empty (clears the expiry; allow留空)", () => {
    expect(dateInputToIso("")).toBe("");
    expect(dateInputToIso("   ")).toBe("");
  });
});

describe("discoverButtonLabel", () => {
  it("is 查看候選模型 for the seed-only Claude OAuth, else 列模型", () => {
    expect(discoverButtonLabel("claude_code_oauth", zhT)).toBe("查看候選模型");
    expect(discoverButtonLabel("chatgpt_oauth", zhT)).toBe("列模型");
    expect(discoverButtonLabel("api_key", zhT)).toBe("列模型");
    expect(discoverButtonLabel(null, zhT)).toBe("列模型");
  });
});

describe("add API key activation copy", () => {
  it("defaults to active only when there is no LOCAL DB credential (env fallback rows don't count)", () => {
    expect(defaultMakeActiveOnAdd([])).toBe(true);
    expect(defaultMakeActiveOnAdd([{ id: "openai:OPENAI_API_KEY" }])).toBe(true); // env-only → still empty
    expect(defaultMakeActiveOnAdd([{ id: "local:1" }])).toBe(false); // a DB credential exists
    expect(defaultMakeActiveOnAdd([{ id: "openai:OPENAI_API_KEY" }, { id: "local:2" }])).toBe(false);
  });

  it("labels the submit action by whether the new key will become active", () => {
    expect(addApiKeyButtonLabel(true, zhT)).toBe("新增後設為 active");
    expect(addApiKeyButtonLabel(false, zhT)).toBe("新增 API key");
  });

  it("reports whether the add switched the active credential", () => {
    expect(addApiKeySuccessMessage("openai", true, zhT)).toBe("openai: 使用中");
    expect(addApiKeySuccessMessage("openai", false, zhT)).toBe("openai: 未使用");
  });
});

describe("discovery result header copy", () => {
  it("labels live vs seed discovery by auth mode", () => {
    expect(discoveryHeaderTitle("api_key", zhT)).toBe("列模型");
    expect(discoveryHeaderTitle("chatgpt_oauth", zhT)).toBe("列模型");
    expect(discoveryHeaderTitle("claude_code_oauth", zhT)).toBe("查看候選模型");
  });

  it("shows which credential produced the result", () => {
    expect(discoveryResultCredentialLabel({ label: "TS_Codex", auth_type: "chatgpt_oauth" }, zhT)).toBe("來源: TS_Codex / chatgpt_oauth");
    expect(discoveryResultCredentialLabel({ label: "OpenAI primary", auth_type: "api_key" }, zhT)).toBe("來源: OpenAI primary / api_key");
    expect(discoveryResultCredentialLabel(null, zhT)).toBe("來源: 未命名 credential");
  });
});

describe("localized credential presentation", () => {
  it("renders credential presentation helpers in both locales", () => {
    const enT = settingsT("en");
    expect(credentialPill({ auth_type: "chatgpt_oauth" }, zhT).label).toBe("ChatGPT 訂閱");
    expect(credentialPill({ auth_type: "chatgpt_oauth" }, enT).label).toBe("ChatGPT subscription");
    expect(credentialAvailabilityText({ available: false, masked: null }, zhT)).toBe("目前無法使用");
    expect(credentialAvailabilityText({ available: false, masked: null }, enT)).toBe("Currently unavailable");
    expect(discoverButtonLabel("claude_code_oauth", zhT)).toBe("查看候選模型");
    expect(discoverButtonLabel("claude_code_oauth", enT)).toBe("View candidate models");
    expect(discoveryHeaderTitle("api_key", zhT)).toBe("列模型");
    expect(discoveryHeaderTitle("api_key", enT)).toBe("List models");
  });

  it("preserves provider auth and credential identifiers as values", () => {
    const enT = settingsT("en");
    expect(addApiKeySuccessMessage("provider-source-id", false, enT)).toContain("provider-source-id");
    expect(discoveryResultCredentialLabel({
      label: "credential-alias-value",
      auth_type: "unknown-auth-value" as never,
    }, enT)).toContain("credential-alias-value / unknown-auth-value");
    expect(discoverySourceLabel("anthropic", "unknown-auth-value" as never, "provider_api", enT))
      .toContain("Anthropic API");
  });
});
