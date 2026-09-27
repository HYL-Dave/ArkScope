import type { MacroSnapshotItem } from "../api";
import type { SettingsT } from "./settingsCopy";

export const MACRO_INDICATOR_IDS = [
  "FEDFUNDS", "DGS10", "DGS2", "T10Y2Y", "CPIAUCNS", "CPILFESL",
  "UNRATE", "PAYEMS", "GDP", "GDPC1", "VIXCLS",
] as const;
export type MacroIndicatorId = typeof MACRO_INDICATOR_IDS[number];

export function isMacroIndicator(id: string): id is MacroIndicatorId {
  return MACRO_INDICATOR_IDS.some(candidate => candidate === id);
}

export function macroIndicatorCopy(id: MacroIndicatorId, t: SettingsT): string {
  switch (id) {
    case "FEDFUNDS": return t(($) => $.macroStorage.guide.series.FEDFUNDS);
    case "DGS10": return t(($) => $.macroStorage.guide.series.DGS10);
    case "DGS2": return t(($) => $.macroStorage.guide.series.DGS2);
    case "T10Y2Y": return t(($) => $.macroStorage.guide.series.T10Y2Y);
    case "CPIAUCNS": return t(($) => $.macroStorage.guide.series.CPIAUCNS);
    case "CPILFESL": return t(($) => $.macroStorage.guide.series.CPILFESL);
    case "UNRATE": return t(($) => $.macroStorage.guide.series.UNRATE);
    case "PAYEMS": return t(($) => $.macroStorage.guide.series.PAYEMS);
    case "GDP": return t(($) => $.macroStorage.guide.series.GDP);
    case "GDPC1": return t(($) => $.macroStorage.guide.series.GDPC1);
    case "VIXCLS": return t(($) => $.macroStorage.guide.series.VIXCLS);
  }
}

function frequencyKind(frequency: string | null | undefined): string {
  switch (frequency) {
    case "D": case "Daily": return "daily";
    case "M": case "Monthly": return "monthly";
    case "Q": case "Quarterly": return "quarterly";
    default: return "unknown";
  }
}

export function macroFrequencyLabel(frequency: string | null | undefined, t: SettingsT): string {
  switch (frequencyKind(frequency)) {
    case "daily": return t(($) => $.macroStorage.frequency.daily);
    case "monthly": return t(($) => $.macroStorage.frequency.monthly);
    case "quarterly": return t(($) => $.macroStorage.frequency.quarterly);
    default: return frequency || "\u2014";
  }
}

export function macroObservationPeriod(item: MacroSnapshotItem): string {
  const day = item.observation_date;
  if (!day) return "\u2014";
  // FRED dates label the observation period, not the publication date.
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return day;
  if (frequencyKind(item.frequency) === "monthly") return day.slice(0, 7);
  if (frequencyKind(item.frequency) === "quarterly") {
    const month = Number(day.slice(5, 7));
    if (month >= 1 && month <= 12) return `${day.slice(0, 4)} Q${Math.ceil(month / 3)}`;
  }
  return day;
}
