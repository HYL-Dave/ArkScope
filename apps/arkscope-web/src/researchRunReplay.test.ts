import { describe, expect, it } from "vitest";

import { shouldEndResearchReplay } from "./researchRunReplay";

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
