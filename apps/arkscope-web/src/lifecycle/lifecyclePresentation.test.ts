import { describe, expect, it } from "vitest";

const PRESENTATION_MODULE = "./lifecyclePresentation";

describe("Lifecycle presentation", () => {
  it("labels source presence and workflow state without mixing their meanings", async () => {
    const { lifecycleSourcePresenceLabel, lifecycleWorkflowLabel } = await import(
      /* @vite-ignore */ PRESENTATION_MODULE
    );

    expect(lifecycleSourcePresenceLabel("source_missing", "en")).toBe(
      "Source observation missing",
    );
    expect(lifecycleWorkflowLabel("unresolved", "en")).toBe("Unresolved");
    expect(lifecycleSourcePresenceLabel("source_missing", "en")).not.toContain("Unresolved");
  });

  it("preserves decimal assessment facts and unknown values", async () => {
    const { formatAssessmentDecimal } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(formatAssessmentDecimal("10.5000", "USD")).toBe("USD 10.5000");
    expect(formatAssessmentDecimal(null, "USD")).toBe("Unknown");
  });

  it("labels closed automation fact values without exposing storage codes", async () => {
    const { lifecycleFactValueLabel } = await import(
      /* @vite-ignore */ PRESENTATION_MODULE
    );

    expect(lifecycleFactValueLabel(
      "tracked_security_effect",
      "symbol_and_venue_change",
      "en",
    )).toBe("Ticker and trading venue changed");
    expect(lifecycleFactValueLabel(
      "tracked_security_effect",
      "symbol_and_venue_change",
      "zh-Hant",
    )).toBe("標的代號與交易市場皆已變更");
    expect(lifecycleFactValueLabel("security_class", "common_stock", "en"))
      .toBe("Common stock");
    expect(lifecycleFactValueLabel("transaction_structure", "asset_acquisition", "en"))
      .toBe("Unrecognized value");
    expect(lifecycleFactValueLabel(
      "tracked_security_effect",
      "future_effect",
      "en",
    )).toBe("Unrecognized value");
    expect(lifecycleFactValueLabel("source_ticker", "HAPN", "en")).toBeNull();
    expect(lifecycleFactValueLabel(
      "transaction_structure",
      { kind: "mixed", terms_status: "not_extracted" },
      "en",
    )).toBe("Mixed consideration · Terms not extracted");
  });

  it("labels transition revalidation without collapsing it into eligibility or a generic block", async () => {
    const {
      lifecycleActionReadinessLabel,
      lifecycleAutomationBlockerLabel,
    } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(lifecycleActionReadinessLabel("waiting_transition_revalidation", "en"))
      .toBe("Waiting to revalidate tracking transition");
    expect(lifecycleActionReadinessLabel("waiting_transition_revalidation", "zh-Hant"))
      .toBe("等待重新驗證追蹤轉移");
    expect(lifecycleAutomationBlockerLabel("transition_approval_changed", "en"))
      .toBe("Transition approval inputs changed; revalidation is scheduled");
    expect(lifecycleAutomationBlockerLabel("transition_approval_unavailable", "zh-Hant"))
      .toBe("追蹤轉移核准暫時無法完成；已排程重新驗證");
    expect(lifecycleActionReadinessLabel("waiting_transition_revalidation", "en"))
      .not.toBe(lifecycleActionReadinessLabel("transition_eligible", "en"));
  });

  it("rejects unsafe evidence links before rendering an external action", async () => {
    const { safeEvidenceUrl } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(safeEvidenceUrl("https://www.sec.gov/Archives/example.htm")).toBe(
      "https://www.sec.gov/Archives/example.htm",
    );
    expect(safeEvidenceUrl("javascript:alert(1)")).toBeNull();
    expect(safeEvidenceUrl("http://example.com/private")).toBeNull();
  });

  it("renders proposals as recommendations rather than completed actions", async () => {
    const { actionProposalPresentation } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(actionProposalPresentation({
      action_type: "archive_manual_memberships",
      status: "proposed",
      block_reason: null,
    }, "en")).toEqual(expect.objectContaining({
      label: "Review removing manual tracking",
      state: "Recommendation only; not applied",
      canApply: false,
    }));

    expect(actionProposalPresentation({
      action_type: "hide_from_active_universe",
      status: "dismissed",
      block_reason: null,
    }, "en")).toEqual(expect.objectContaining({
      label: "Recommend hiding from the active universe",
      state: "Recommendation dismissed; not applied",
      canApply: false,
    }));
  });

  it("labels every persisted proposal block reason without a semantic fallback", async () => {
    const { lifecycleProposalBlockReasonLabel } = await import(
      /* @vite-ignore */ PRESENTATION_MODULE
    );

    expect(lifecycleProposalBlockReasonLabel("successor_evidence_missing", "en"))
      .toBe("Successor evidence is missing");
    expect(lifecycleProposalBlockReasonLabel("action_executor_not_available", "en"))
      .toBe("No action executor is available");
  });

  it("labels cancelled runs without reporting them as failures", async () => {
    const { lifecycleRunStatusLabel } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(lifecycleRunStatusLabel("cancelled", "en")).toBe("Cancelled");
    expect(lifecycleRunStatusLabel("cancelled", "en")).not.toBe("Failed");
  });

  it("keeps provider failure categories distinct in user-facing copy", async () => {
    const { lifecycleErrorPresentation } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(lifecycleErrorPresentation({ code: "credential_missing" }, "en").message)
      .toBe("Search credentials are not configured");
    expect(lifecycleErrorPresentation({ code: "permission_denied" }, "en").message)
      .toBe("Web search permission was denied");
    expect(lifecycleErrorPresentation({ code: "network_error" }, "en").message)
      .toBe("The search service could not be reached");
    expect(lifecycleErrorPresentation({ code: "extract_failed" }, "en").message)
      .toBe("Search results could not be extracted");
    expect(lifecycleErrorPresentation({ code: "unsupported_content" }, "en").message)
      .toBe("The search service returned unsupported content");
  });

  it("sanitizes typed API failures without exposing diagnostic detail", async () => {
    const { lifecycleErrorPresentation } = await import(/* @vite-ignore */ PRESENTATION_MODULE);
    const error = Object.assign(new Error("token=private /home/private/profile.db"), {
      status: 503,
      code: "security_lifecycle_profile_store_unavailable",
      path: "/security-lifecycle/cases?token=private",
      diagnostic: "sqlite3 at /home/private/profile.db",
    });

    const rendered = lifecycleErrorPresentation(error, "en");
    expect(rendered).toEqual({
      code: "security_lifecycle_profile_store_unavailable",
      message: "Security event data is unavailable.",
    });
    expect(JSON.stringify(rendered)).not.toMatch(/token|\/home\/private|sqlite3/);
  });
});
