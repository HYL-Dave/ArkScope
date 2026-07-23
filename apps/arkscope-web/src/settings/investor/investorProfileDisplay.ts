import type { AssistantStance, CalibrationTopicId, InvestorPreset } from "../../api";
import { stanceLabel, type CommonT } from "../../personalizationDisplay";
import {
  settingsInvestorHorizonLabel,
  settingsInvestorPresetLabel,
  type SettingsT,
} from "../settingsCopy";

export const CALIBRATION_TOPIC_IDS = [
  "loss_response",
  "financial_capacity",
  "time_horizon",
  "single_position_limit",
  "risk_avoidances",
  "behavioral_patterns",
  "investment_approach",
  "assistant_style",
] as const satisfies readonly CalibrationTopicId[];

export const CALIBRATION_PROMPT_IDS = ["loss_response.opening.v1"] as const;

export const PROPOSABLE_INVESTOR_PROFILE_FIELDS = [
  "risk_appetite",
  "drawdown_tolerance_pct",
  "risk_capacity",
  "holding_horizon",
  "concentration_limit_pct",
  "avoidances",
  "behavioral_flags",
  "primary_preset",
  "preferred_edge",
  "default_stance",
] as const;

export type ProposableInvestorProfileField =
  (typeof PROPOSABLE_INVESTOR_PROFILE_FIELDS)[number];

export interface CalibrationTopicDisplay {
  id: string;
  label: string;
  description: string | null;
  developerDiagnostic: string | null;
}

export interface InvestorProfileFieldDisplay {
  field: ProposableInvestorProfileField;
  label: string;
}

function isCalibrationTopicId(id: string): id is CalibrationTopicId {
  return (CALIBRATION_TOPIC_IDS as readonly string[]).includes(id);
}

export function isProposableInvestorProfileField(
  field: string,
): field is ProposableInvestorProfileField {
  return (PROPOSABLE_INVESTOR_PROFILE_FIELDS as readonly string[]).includes(field);
}

function knownTopicDisplay(
  id: CalibrationTopicId,
  t: SettingsT,
): Omit<CalibrationTopicDisplay, "id" | "developerDiagnostic"> {
  switch (id) {
    case "loss_response":
      return {
        label: t(($) => $.investor.workspace.topics.lossResponse.label),
        description: t(($) => $.investor.workspace.topics.lossResponse.description),
      };
    case "financial_capacity":
      return {
        label: t(($) => $.investor.workspace.topics.financialCapacity.label),
        description: t(($) => $.investor.workspace.topics.financialCapacity.description),
      };
    case "time_horizon":
      return {
        label: t(($) => $.investor.workspace.topics.timeHorizon.label),
        description: t(($) => $.investor.workspace.topics.timeHorizon.description),
      };
    case "single_position_limit":
      return {
        label: t(($) => $.investor.workspace.topics.singlePositionLimit.label),
        description: t(($) => $.investor.workspace.topics.singlePositionLimit.description),
      };
    case "risk_avoidances":
      return {
        label: t(($) => $.investor.workspace.topics.riskAvoidances.label),
        description: t(($) => $.investor.workspace.topics.riskAvoidances.description),
      };
    case "behavioral_patterns":
      return {
        label: t(($) => $.investor.workspace.topics.behavioralPatterns.label),
        description: t(($) => $.investor.workspace.topics.behavioralPatterns.description),
      };
    case "investment_approach":
      return {
        label: t(($) => $.investor.workspace.topics.investmentApproach.label),
        description: t(($) => $.investor.workspace.topics.investmentApproach.description),
      };
    case "assistant_style":
      return {
        label: t(($) => $.investor.workspace.topics.assistantStyle.label),
        description: t(($) => $.investor.workspace.topics.assistantStyle.description),
      };
  }
}

export function calibrationTopicDisplay(id: string, t: SettingsT): CalibrationTopicDisplay {
  if (!isCalibrationTopicId(id)) {
    return {
      id,
      label: t(($) => $.investor.workspace.topics.other),
      description: null,
      developerDiagnostic: id,
    };
  }
  return { id, ...knownTopicDisplay(id, t), developerDiagnostic: null };
}

export function calibrationPromptText(
  promptId: string | null,
  canonicalContent: string,
  t: SettingsT,
): string {
  switch (promptId) {
    case "loss_response.opening.v1":
      return t(($) => $.investor.workspace.prompts.lossResponseOpeningV1);
    default:
      return canonicalContent;
  }
}

export function investorProfileFieldLabel(
  field: ProposableInvestorProfileField,
  t: SettingsT,
): string {
  switch (field) {
    case "risk_appetite":
      return t(($) => $.investor.fields.riskAppetite);
    case "drawdown_tolerance_pct":
      return t(($) => $.investor.fields.drawdown);
    case "risk_capacity":
      return t(($) => $.investor.fields.riskCapacity);
    case "holding_horizon":
      return t(($) => $.investor.fields.horizon);
    case "concentration_limit_pct":
      return t(($) => $.investor.fields.concentration);
    case "avoidances":
      return t(($) => $.investor.fields.avoidances);
    case "behavioral_flags":
      return t(($) => $.investor.fields.flags);
    case "primary_preset":
      return t(($) => $.investor.fields.preset);
    case "preferred_edge":
      return t(($) => $.investor.fields.edges);
    case "default_stance":
      return t(($) => $.investor.fields.stance);
  }
}

function sourceValue(value: unknown, t: SettingsT): string {
  if (value === null || value === undefined || value === "") {
    return t(($) => $.investor.fields.unset);
  }
  if (Array.isArray(value)) return value.map(String).join(", ");
  return String(value);
}

export function investorProfileFieldValue(
  field: ProposableInvestorProfileField,
  value: unknown,
  settingsT: SettingsT,
  commonT: CommonT,
): string {
  switch (field) {
    case "primary_preset":
      return typeof value === "string"
        ? settingsInvestorPresetLabel(value as InvestorPreset, settingsT)
        : sourceValue(value, settingsT);
    case "holding_horizon":
      return typeof value === "string"
        ? settingsInvestorHorizonLabel(value, settingsT)
        : sourceValue(value, settingsT);
    case "default_stance":
      return typeof value === "string"
        ? stanceLabel(value as AssistantStance, commonT)
        : sourceValue(value, settingsT);
    default:
      return sourceValue(value, settingsT);
  }
}

export function assistantStanceEffect(stance: AssistantStance, t: SettingsT): string {
  switch (stance) {
    case "off":
      return t(($) => $.investor.workspace.effects.off);
    case "neutral":
      return t(($) => $.investor.workspace.effects.neutral);
    case "aligned":
      return t(($) => $.investor.workspace.effects.aligned);
    case "complementary":
      return t(($) => $.investor.workspace.effects.complementary);
    case "strict_risk_control":
      return t(($) => $.investor.workspace.effects.strictRiskControl);
    case "valuation_rationalist":
      return t(($) => $.investor.workspace.effects.valuationRationalist);
    case "growth_opportunity":
      return t(($) => $.investor.workspace.effects.growthOpportunity);
  }
}

export function orderedCalibrationTopicDisplays(
  topicIds: readonly string[],
  t: SettingsT,
): CalibrationTopicDisplay[] {
  return topicIds.map((id) => calibrationTopicDisplay(id, t));
}

export function orderedInvestorProfileFieldDisplays(
  fields: readonly string[],
  t: SettingsT,
): InvestorProfileFieldDisplay[] {
  return fields.flatMap((field) => isProposableInvestorProfileField(field)
    ? [{ field, label: investorProfileFieldLabel(field, t) }]
    : []);
}
