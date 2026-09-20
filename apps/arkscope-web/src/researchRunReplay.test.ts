import { describe, expect, it } from "vitest";

import { shouldApplyResearchEvent, shouldEndResearchReplay } from "./researchRunReplay";

describe("shouldEndResearchReplay", () => {
  it("does not end a terminal replay page while more events remain", () => {
    expect(shouldEndResearchReplay({ status: "succeeded" }, true)).toBe(false);
  });

  it("ends after the final terminal replay page", () => {
    expect(shouldEndResearchReplay({ status: "succeeded" }, false)).toBe(true);
  });

  it("does not end active runs", () => {
    expect(shouldEndResearchReplay({ status: "running" }, false)).toBe(false);
  });
});

describe("completion evidence in replay", () => {
  it("admits done only alongside committed success", () => {
    for (const status of ["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]) {
      expect(shouldApplyResearchEvent({ status }, { type: "done", data: { answer: "Answer" } }))
        .toBe(status === "succeeded");
    }
  });

  it("does not let an old terminal frame override unverified recovery", () => {
    const run = { status: "interrupted", error_code: "run_completion_unverified" };
    expect(shouldApplyResearchEvent(run, { type: "done", data: { answer: "Unverified" } })).toBe(false);
    expect(shouldApplyResearchEvent(run, { type: "error", data: { code: "model_refusal" } })).toBe(false);
    expect(shouldApplyResearchEvent(run, { type: "error", data: { code: run.error_code } })).toBe(true);
    expect(shouldApplyResearchEvent(run, { type: "tool_end", data: { sec_citations: ["retained"] } })).toBe(true);
  });

  it("requires committed failure for an error terminal but keeps nonterminal progress", () => {
    const event = { type: "error", data: { code: "model_refusal" } };
    expect(shouldApplyResearchEvent({ status: "running" }, event)).toBe(false);
    expect(shouldApplyResearchEvent({ status: "succeeded" }, event)).toBe(false);
    expect(shouldApplyResearchEvent({ status: "failed", error_code: "model_refusal" }, event)).toBe(true);
    expect(shouldApplyResearchEvent({ status: "running" }, { type: "text", data: { content: "Partial" } })).toBe(true);
  });
});
