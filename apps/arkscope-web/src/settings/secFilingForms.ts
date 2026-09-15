import type enSettings from "../i18n/resources/en/settings";
import type { SettingsT } from "./settingsCopy";

type Group = keyof typeof enSettings.secResearch.formGroups;
type Name = keyof typeof enSettings.secResearch.formNames;
type Choice = { form: string; description: string; rank: number };

// Presentation metadata only, never an allowlist. Sources and historical codes:
// docs/superpowers/evidence/2026-09-15-sec-form-labels/README.md
const GROUPS = [
  { id: "reports", forms: [
    ["10-K", "annual"], ["10-Q", "quarterly"], ["20-F", "foreignAnnual"], ["40-F", "canadianAnnual"],
    ["10-K405", "historicalAnnual"], ["NT 10-K", "lateAnnual"], ["NT 10-Q", "lateQuarterly"],
  ] },
  { id: "events", forms: [
    ["8-K", "current"], ["6-K", "foreignCurrent"], ["DEF 14A", "proxy"], ["PRE 14A", "preliminaryProxy"],
    ["DEFA14A", "additionalProxy"], ["DEFR14A", "revisedProxy"], ["DFAN14A", "nonManagementProxy"],
    ["PX14A6G", "exemptProxy"], ["PX14A6N", "rollupProxy"], ["SD", "specialized"], ["IRANNOTICE", "iran"],
  ] },
  { id: "ownership", forms: [
    ["3", "initialOwnership"], ["4", "ownershipChanges"], ["5", "annualOwnership"], ["144", "proposedSale"],
    ["SC 13D", "beneficialOwnership"], ["SC 13G", "shortOwnership"], ["SCHEDULE 13G", "shortOwnership"],
  ] },
  { id: "offering", forms: [
    ["S-3", "registration"], ["S-3ASR", "shelf"], ["S-4", "businessCombination"], ["S-8", "employeePlan"],
    ["S-8 POS", "employeePlanAmendment"], ["424B2", "prospectus"], ["424B3", "prospectus"], ["424B5", "prospectus"],
    ["FWP", "freeWritingProspectus"], ["SC TO-I", "issuerTender"], ["8-A12B", "listedRegistration"],
    ["25", "delisting"], ["25-NSE", "exchangeDelisting"], ["CERT", "listingCertification"], ["CERTNYS", "nyseCertification"],
  ] },
  { id: "other", forms: [["CORRESP", "correspondence"], ["UPLOAD", "secLetter"], ["NO ACT", "noAction"]] },
] as const satisfies readonly { id: Group; forms: readonly (readonly [string, Name])[] }[];

const METADATA = new Map<string, { group: Group; name: Name; rank: number }>(
  GROUPS.flatMap(({ id, forms }) => forms.map(([form, name], rank) => [form, { group: id, name, rank }])),
);

export function groupSecFilingForms(forms: readonly string[], t: SettingsT) {
  const groups = GROUPS.map(({ id }) => ({ id, label: t(($) => $.secResearch.formGroups[id]), choices: [] as Choice[] }));
  const byId = new Map<Group, typeof groups[number]>(groups.map((group) => [group.id, group]));
  for (const form of forms) {
    const amended = form.endsWith("/A");
    const metadata = METADATA.get(amended ? form.slice(0, -2) : form);
    const name = metadata ? t(($) => $.secResearch.formNames[metadata.name]) : t(($) => $.secResearch.unclassifiedForm);
    byId.get(metadata?.group ?? "other")!.choices.push({
      form,
      description: amended && metadata ? t(($) => $.secResearch.amendedForm, { name }) : name,
      rank: metadata ? metadata.rank * 2 + Number(amended) : Number.MAX_SAFE_INTEGER,
    });
  }
  return groups.filter((group) => group.choices.length).map((group) => ({ ...group,
    choices: group.choices.sort((a, b) => a.rank - b.rank || (a.form < b.form ? -1 : a.form > b.form ? 1 : 0)),
  }));
}
