import type { TFunction } from "i18next";

import type { AssistantStance, InvestorProfile, PersonalizationTrace } from "./api";

export type CommonT = TFunction<"common">;

export function stanceLabel(stance: AssistantStance, t: CommonT): string {
  switch (stance) {
    case "off":
      return t(($) => $.personalization.stances.off);
    case "neutral":
      return t(($) => $.personalization.stances.neutral);
    case "aligned":
      return t(($) => $.personalization.stances.aligned);
    case "complementary":
      return t(($) => $.personalization.stances.complementary);
    case "strict_risk_control":
      return t(($) => $.personalization.stances.strictRiskControl);
    case "valuation_rationalist":
      return t(($) => $.personalization.stances.valuationRationalist);
    case "growth_opportunity":
      return t(($) => $.personalization.stances.growthOpportunity);
    default:
      return String(stance);
  }
}

export function mismatchLabel(
  mismatch: InvestorProfile["risk_mismatch"],
  t: CommonT,
): string {
  switch (mismatch) {
    case "none":
      return t(($) => $.personalization.mismatch.none);
    case "appetite_above_capacity":
      return t(($) => $.personalization.mismatch.appetiteAboveCapacity);
    case "capacity_above_appetite":
      return t(($) => $.personalization.mismatch.capacityAboveAppetite);
    case "unclear":
      return t(($) => $.personalization.mismatch.unclear);
    default:
      return String(mismatch);
  }
}

export function traceSummary(
  trace: PersonalizationTrace | null | undefined,
  t: CommonT,
): string | null {
  if (!trace || !trace.profile_active || trace.assistant_stance === "off") return null;
  const parts: string[] = [t(($) => $.personalization.trace.stance, {
    stance: stanceLabel(trace.assistant_stance, t),
  })];
  if (trace.applied_skills.length) {
    parts.push(t(($) => $.personalization.trace.appliedSkills, {
      skills: trace.applied_skills.join("、"),
    }));
  } else if (trace.suggested_skills.length) {
    parts.push(t(($) => $.personalization.trace.suggestedSkills, {
      skills: trace.suggested_skills.join("、"),
    }));
  }
  return parts.join("　");
}
