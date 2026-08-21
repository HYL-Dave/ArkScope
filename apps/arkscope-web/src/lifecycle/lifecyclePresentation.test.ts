import { describe, expect, it } from "vitest";

const PRESENTATION_MODULE = "./lifecyclePresentation";

describe("Lifecycle presentation", () => {
  it("labels source presence and workflow state without mixing their meanings", async () => {
    const { lifecycleSourcePresenceLabel, lifecycleWorkflowLabel } = await import(
      /* @vite-ignore */ PRESENTATION_MODULE
    );

    expect(lifecycleSourcePresenceLabel("source_missing", "en")).toBe("Source missing");
    expect(lifecycleWorkflowLabel("unresolved", "en")).toBe("Unresolved");
    expect(lifecycleSourcePresenceLabel("source_missing", "en")).not.toContain("Unresolved");
  });

  it("preserves decimal assessment facts and unknown values", async () => {
    const { formatAssessmentDecimal } = await import(/* @vite-ignore */ PRESENTATION_MODULE);

    expect(formatAssessmentDecimal("10.5000", "USD")).toBe("USD 10.5000");
    expect(formatAssessmentDecimal(null, "USD")).toBe("Unknown");
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
      state: "Recommendation only",
      canApply: false,
    }));
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
      message: "Lifecycle data is unavailable.",
    });
    expect(JSON.stringify(rendered)).not.toMatch(/token|\/home\/private|sqlite3/);
  });
});
