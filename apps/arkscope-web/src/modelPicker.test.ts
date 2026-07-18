import { describe, expect, it } from "vitest";

import type {
  EffectiveProviderModelEntry,
  EffectiveProviderModels,
  EffectiveProviderSummary,
  ModelOption,
} from "./api";
import {
  compatEntries,
  groupedModelEntries,
  modelProviderReason,
  optionReason,
} from "./modelPicker";

const entry = (
  id: string,
  over: Partial<EffectiveProviderModelEntry> = {},
): EffectiveProviderModelEntry => ({
  id,
  label: id,
  status: "visible",
  visible_to_credential: true,
  eligible: true,
  reason_code: null,
  thinking_mode: "none",
  effort_options: ["low", "high"],
  ...over,
});

const context: EffectiveProviderSummary = {
  credential_id: "local:7",
  auth_mode: "chatgpt_oauth",
  label: "ChatGPT Plus",
};

const providerBlock = (
  over: Partial<EffectiveProviderModels> = {},
): EffectiveProviderModels => ({
  executable: true,
  reason_code: null,
  models: [],
  cache_state: "ok",
  discovered_at: "2026-07-18T00:00:00Z",
  ...over,
});

describe("shared model picker authority", () => {
  it("applies the provider veto before model capability", () => {
    const blocked = entry("gpt-5.6-luna", {
      eligible: false,
      reason_code: "task_capability_missing",
    });
    expect(optionReason(blocked, "task_auth_mode_unsupported"))
      .toBe("task_auth_mode_unsupported");
  });

  it("classifies an ineligible model as task_capability_missing", () => {
    expect(optionReason(entry("gpt-5.6-luna", { eligible: false }), null))
      .toBe("task_capability_missing");
  });

  it("classifies a cache-ok invisible model as model_not_visible", () => {
    expect(optionReason(entry("gpt-5.6-luna", { visible_to_credential: false }), null))
      .toBe("model_not_visible");
  });

  it("keeps a route-pinned unknown model eligible while retaining its warning", () => {
    const custom = entry("gpt-future", {
      status: "route",
      visible_to_credential: false,
      reason_code: "model_not_in_registry",
    });
    expect(optionReason(custom, null)).toBeNull();
    expect(groupedModelEntries([custom], null)[3].entries[0]).toMatchObject({
      id: "gpt-future",
      reason_code: "model_not_in_registry",
      disabledReason: null,
    });
  });

  it("preserves visible, disabled, advanced, and route group ordering", () => {
    const groups = groupedModelEntries([
      entry("ready"),
      entry("disabled", { eligible: false }),
      entry("advanced", { status: "advanced" }),
      entry("route", { status: "route" }),
    ], null);
    expect(groups.map((group) => [group.label, group.entries.map((item) => item.id)]))
      .toEqual([
        ["可供此任務使用", ["ready"]],
        ["此登入可見", ["disabled"]],
        ["進階／未驗證", ["advanced"]],
        ["目前路由", ["route"]],
      ]);
  });

  it("keeps old-sidecar compatibility entries visibly unverified", () => {
    const seed: ModelOption = {
      id: "gpt-5.4-mini",
      provider: "openai",
      label: "GPT-5.4 mini",
      quality: "balanced",
      speed: "fast",
      cost_tier: "low",
      supports_structured_output: true,
      supports_tool_calling: true,
      recommended_for: [],
      source_url: "",
      verified_at: "",
      notes: "",
    };
    expect(compatEntries("openai", { model: "gpt-custom" }, { openai: [seed], anthropic: [] }))
      .toEqual([
        expect.objectContaining({
          id: "gpt-5.4-mini",
          status: "advanced",
          label: "GPT-5.4 mini · 未驗證（舊 sidecar 相容模式）",
        }),
        expect.objectContaining({
          id: "gpt-custom",
          status: "route",
          reason_code: "model_not_in_registry",
        }),
      ]);
  });

  it("turns a missing active credential into one provider veto for every entry", () => {
    const reason = modelProviderReason(null, providerBlock({ reason_code: "task_auth_mode_unsupported" }));
    expect(reason).toBe("missing_active_credential");
    expect(groupedModelEntries([entry("a"), entry("b", { eligible: false })], reason)
      .flatMap((group) => group.entries)
      .map((item) => item.disabledReason))
      .toEqual(["missing_active_credential", "missing_active_credential"]);
  });

  it("gives Settings and Research the same disabled reason for one provider fixture", () => {
    const block = providerBlock({
      executable: false,
      reason_code: "task_auth_mode_unsupported",
    });
    const reason = modelProviderReason(context, block);
    const selected = entry("gpt-5.4-mini");
    const settingsReason = optionReason(selected, reason);
    const researchReason = groupedModelEntries(block.models.concat(selected), reason)
      .flatMap((group) => group.entries)
      .find((item) => item.id === selected.id)?.disabledReason;
    expect(settingsReason).toBe("task_auth_mode_unsupported");
    expect(researchReason).toBe(settingsReason);
  });
});
