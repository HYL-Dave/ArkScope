// Track A: short zh display labels for investor-profile personalization.
// Labels stay terse (chips/inline), never explanatory paragraphs.

import type { AssistantStance, InvestorProfile, PersonalizationTrace } from "./api";

const STANCE_LABELS: Record<AssistantStance, string> = {
  off: "關閉",
  neutral: "中性",
  aligned: "對齊投資人",
  complementary: "互補投資人",
  strict_risk_control: "嚴格風控",
  valuation_rationalist: "估值理性派",
  growth_opportunity: "成長機會派",
};

const MISMATCH_LABELS: Record<InvestorProfile["risk_mismatch"], string> = {
  none: "一致",
  appetite_above_capacity: "風險胃納高於承受能力",
  capacity_above_appetite: "承受能力高於風險胃納",
  unclear: "未評估",
};

export function stanceLabel(stance: AssistantStance): string {
  return STANCE_LABELS[stance] ?? String(stance);
}

export function mismatchLabel(mismatch: InvestorProfile["risk_mismatch"]): string {
  return MISMATCH_LABELS[mismatch] ?? String(mismatch);
}

export function traceSummary(trace: PersonalizationTrace | null | undefined): string | null {
  if (!trace || !trace.profile_active || trace.assistant_stance === "off") return null;
  const parts = [`立場：${stanceLabel(trace.assistant_stance)}`];
  if (trace.applied_skills.length) parts.push(`套用技能：${trace.applied_skills.join("、")}`);
  else if (trace.suggested_skills.length)
    parts.push(`建議技能：${trace.suggested_skills.join("、")}`);
  return parts.join("　");
}
