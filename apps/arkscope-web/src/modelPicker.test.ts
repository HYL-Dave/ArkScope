import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
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
import { modelEntryLabel } from "./modelRoutingUx";

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

const commonT = (locale: "zh-Hant" | "en") => {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "common");
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
    expect(groupedModelEntries([custom], null, commonT("zh-Hant"))[3].entries[0]).toMatchObject({
      id: "gpt-future",
      reason_code: "model_not_in_registry",
      disabledReason: null,
    });
  });

  it("preserves visible, disabled, advanced, and route group ordering", () => {
    const entries = [
      entry("ready"),
      entry("disabled", { eligible: false }),
      entry("advanced", { status: "advanced" }),
      entry("route", { status: "route" }),
    ];
    const groups = groupedModelEntries(entries, null, commonT("zh-Hant"));
    expect(groups.map((group) => [group.id, group.label, group.entries.map((item) => item.id)]))
      .toEqual([
        ["available", "可供此任務使用", ["ready"]],
        ["visible_disabled", "此登入可見", ["disabled"]],
        ["advanced", "其他模型", ["advanced"]],
        ["current", "目前路由", ["route"]],
      ]);
    expect(groups.flatMap((group) => group.entries).map((item) => ({
      id: item.id,
      baseLabel: item.baseLabel,
      compatibility: item.compatibility,
    }))).toEqual([
      { id: "ready", baseLabel: "ready", compatibility: null },
      { id: "disabled", baseLabel: "disabled", compatibility: null },
      { id: "advanced", baseLabel: "advanced", compatibility: null },
      { id: "route", baseLabel: "route", compatibility: null },
    ]);
    expect(groupedModelEntries(entries, null, commonT("en")).map((group) => group.label))
      .toEqual([
        "Available for this task",
        "Visible to this sign-in",
        "Other models",
        "Current route",
      ]);
  });

  it("places eligible seed-only defaults with available models without an unverified claim", () => {
    const seed = entry("claude-sonnet-5", {
      status: "seed",
      visible_to_credential: null,
      eligible: true,
    });

    const groups = groupedModelEntries(
      [seed],
      null,
      commonT("zh-Hant"),
      "seed_only",
    );

    expect(groups.find((group) => group.id === "available")?.entries.map((item) => item.id))
      .toEqual(["claude-sonnet-5"]);
    expect(groups.find((group) => group.id === "advanced")?.entries).toEqual([]);
  });

  it("keeps old-sidecar compatibility entries visibly unverified", () => {
    const seed: ModelOption = {
      id: "gpt-5.4-mini",
      provider: "openai",
      label: "GPT-5.4 mini · source label",
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
    const compatibility = compatEntries(
      "openai",
      { model: "gpt-custom" },
      { openai: [seed], anthropic: [] },
      commonT("zh-Hant"),
    );
    expect(compatibility).toEqual([
        expect.objectContaining({
          id: "gpt-5.4-mini",
          status: "advanced",
          label: "GPT-5.4 mini · source label · 未驗證（舊 sidecar 相容模式）",
          baseLabel: "GPT-5.4 mini · source label",
          compatibility: "legacy_unverified",
        }),
        expect.objectContaining({
          id: "gpt-custom",
          status: "route",
          reason_code: "model_not_in_registry",
          baseLabel: "gpt-custom",
          compatibility: "legacy_unverified",
        }),
      ]);
    const groupedCompatibility = groupedModelEntries(compatibility, null, commonT("zh-Hant"))
      .flatMap((group) => group.entries);
    expect(groupedCompatibility.map((item) => ({
      id: item.id,
      baseLabel: item.baseLabel,
      compatibility: item.compatibility,
    }))).toEqual([
      {
        id: "gpt-5.4-mini",
        baseLabel: "GPT-5.4 mini · source label",
        compatibility: "legacy_unverified",
      },
      {
        id: "gpt-custom",
        baseLabel: "gpt-custom",
        compatibility: "legacy_unverified",
      },
    ]);
    expect(groupedCompatibility.map((item) => modelEntryLabel(
      item.baseLabel,
      item.compatibility,
      commonT("zh-Hant"),
    )))
      .toEqual([
        "GPT-5.4 mini · source label · 未驗證（舊 sidecar 相容模式）",
        "gpt-custom · 未驗證（舊 sidecar 相容模式）",
      ]);
    expect(groupedCompatibility.map((item) => modelEntryLabel(
      item.baseLabel,
      item.compatibility,
      commonT("en"),
    )))
      .toEqual([
        "GPT-5.4 mini · source label · Unverified (legacy sidecar compatibility mode)",
        "gpt-custom · Unverified (legacy sidecar compatibility mode)",
      ]);
    expect(compatEntries(
      "openai",
      { model: "gpt-custom" },
      { openai: [seed], anthropic: [] },
      commonT("en"),
    ).map(({ id, label, baseLabel, compatibility: context }) => ({
      id,
      label,
      baseLabel,
      compatibility: context,
    }))).toEqual([
      {
        id: "gpt-5.4-mini",
        label: "GPT-5.4 mini · source label · Unverified (legacy sidecar compatibility mode)",
        baseLabel: "GPT-5.4 mini · source label",
        compatibility: "legacy_unverified",
      },
      {
        id: "gpt-custom",
        label: "gpt-custom · Unverified (legacy sidecar compatibility mode)",
        baseLabel: "gpt-custom",
        compatibility: "legacy_unverified",
      },
    ]);
  });

  it("turns a missing active credential into one provider veto for every entry", () => {
    const reason = modelProviderReason(null, providerBlock({ reason_code: "task_auth_mode_unsupported" }));
    expect(reason).toBe("missing_active_credential");
    expect(groupedModelEntries(
      [entry("a"), entry("b", { eligible: false })],
      reason,
      commonT("zh-Hant"),
    )
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
    const researchReason = groupedModelEntries(
      block.models.concat(selected),
      reason,
      commonT("zh-Hant"),
    )
      .flatMap((group) => group.entries)
      .find((item) => item.id === selected.id)?.disabledReason;
    expect(settingsReason).toBe("task_auth_mode_unsupported");
    expect(researchReason).toBe(settingsReason);
  });
});
