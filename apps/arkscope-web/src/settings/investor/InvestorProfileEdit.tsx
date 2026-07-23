import { ArrowLeft, FileText, Save } from "lucide-react";
import type { RefObject } from "react";
import { useTranslation } from "react-i18next";

import type { AssistantStance, InvestorProfile, InvestorPreset } from "../../api";
import { mismatchLabel, stanceLabel } from "../../personalizationDisplay";
import { Button, StatusBadge } from "../../ui";
import {
  settingsInvestorHorizonLabel,
  settingsInvestorPresetLabel,
  type SettingsT,
} from "../settingsCopy";

const PRESETS: readonly InvestorPreset[] = [
  "growth",
  "value",
  "momentum",
  "income",
  "event_driven",
  "balanced",
  "custom",
];

const STANCES: readonly AssistantStance[] = [
  "neutral",
  "aligned",
  "complementary",
  "strict_risk_control",
  "valuation_rationalist",
  "growth_opportunity",
];

const HORIZONS = ["intraday", "days_weeks", "months", "multi_year", "mixed"] as const;
const EDGES = ["growth", "valuation", "catalyst", "quality", "momentum", "macro", "options", "sentiment"] as const;
const FLAGS = [
  "FOMO",
  "greed",
  "overconfidence",
  "panic selling",
  "loss aversion",
  "anchoring",
  "narrative susceptibility",
  "revenge trading",
  "under-diversification",
] as const;
const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

export interface InvestorProfileEditProps {
  profile: InvestorProfile;
  busy: boolean;
  headingRef: RefObject<HTMLHeadingElement>;
  backButtonRef: RefObject<HTMLButtonElement>;
  onChange: <K extends keyof InvestorProfile>(key: K, value: InvestorProfile[K]) => void;
  onDraft: () => void;
  onSave: () => void;
  onBack: () => void;
  t: SettingsT;
}

export function InvestorProfileEdit({
  profile,
  busy,
  headingRef,
  backButtonRef,
  onChange,
  onDraft,
  onSave,
  onBack,
  t,
}: InvestorProfileEditProps) {
  const { t: commonT } = useTranslation("common");
  const toggle = (key: "preferred_edge" | "behavioral_flags", item: string) => {
    const values = profile[key];
    onChange(key, values.includes(item)
      ? values.filter((value) => value !== item)
      : [...values, item]);
  };

  return (
    <section data-testid="investor-profile-edit">
      <div className="ip-actions">
        <Button
          ref={backButtonRef}
          icon={<ArrowLeft size={16} />}
          onClick={onBack}
        >
          {t(($) => $.investor.workspace.actions.backSummary)}
        </Button>
      </div>
      <h3 ref={headingRef} tabIndex={-1} data-investor-mode-heading="edit">
        {t(($) => $.investor.workspace.mode.edit)}
      </h3>

      <label className="ip-toggle">
        <input
          name="enabled"
          type="checkbox"
          checked={profile.enabled}
          disabled={busy}
          onChange={(event) => onChange("enabled", event.target.checked)}
        />{" "}
        {profile.enabled
          ? t(($) => $.investor.workspace.summary.personalizationEnabled)
          : t(($) => $.investor.workspace.summary.personalizationDisabled)}
      </label>

      <div className="ip-grid">
        <label>
          {t(($) => $.investor.fields.preset)}
          <select
            name="primary_preset"
            value={profile.primary_preset}
            disabled={busy}
            onChange={(event) => onChange("primary_preset", event.target.value as InvestorPreset)}
          >
            {PRESETS.map((preset) => (
              <option key={preset} value={preset}>{settingsInvestorPresetLabel(preset, t)}</option>
            ))}
          </select>
        </label>
        <label>
          {t(($) => $.investor.fields.riskAppetite)}
          <select
            name="risk_appetite"
            value={profile.risk_appetite ?? ""}
            disabled={busy}
            onChange={(event) => onChange(
              "risk_appetite",
              event.target.value === "" ? null : Number(event.target.value),
            )}
          >
            <option value="">{t(($) => $.investor.fields.unset)}</option>
            {SCORES.map((score) => <option key={score} value={score}>{score}</option>)}
          </select>
        </label>
        <label>
          {t(($) => $.investor.fields.riskCapacity)}
          <select
            name="risk_capacity"
            value={profile.risk_capacity ?? ""}
            disabled={busy}
            onChange={(event) => onChange(
              "risk_capacity",
              event.target.value === "" ? null : Number(event.target.value),
            )}
          >
            <option value="">{t(($) => $.investor.fields.unset)}</option>
            {SCORES.map((score) => <option key={score} value={score}>{score}</option>)}
          </select>
        </label>
        <label>
          {t(($) => $.investor.fields.horizon)}
          <select
            name="holding_horizon"
            value={profile.holding_horizon}
            disabled={busy}
            onChange={(event) => onChange("holding_horizon", event.target.value)}
          >
            {HORIZONS.map((horizon) => (
              <option key={horizon} value={horizon}>{settingsInvestorHorizonLabel(horizon, t)}</option>
            ))}
          </select>
        </label>
        <label>
          {t(($) => $.investor.fields.drawdown)}
          <input
            name="drawdown_tolerance_pct"
            type="number"
            min={1}
            max={100}
            value={profile.drawdown_tolerance_pct ?? ""}
            disabled={busy}
            onChange={(event) => onChange(
              "drawdown_tolerance_pct",
              event.target.value === "" ? null : Number(event.target.value),
            )}
          />
        </label>
        <label>
          {t(($) => $.investor.fields.concentration)}
          <input
            name="concentration_limit_pct"
            type="number"
            min={1}
            max={100}
            value={profile.concentration_limit_pct ?? ""}
            disabled={busy}
            onChange={(event) => onChange(
              "concentration_limit_pct",
              event.target.value === "" ? null : Number(event.target.value),
            )}
          />
        </label>
        <label>
          {t(($) => $.investor.fields.stance)}
          <select
            name="default_stance"
            value={profile.default_stance}
            disabled={busy}
            onChange={(event) => onChange("default_stance", event.target.value as AssistantStance)}
          >
            {STANCES.map((stance) => (
              <option key={stance} value={stance}>{stanceLabel(stance, commonT)}</option>
            ))}
          </select>
        </label>
      </div>

      <details data-testid="risk-disclosure">
        <summary>{t(($) => $.investor.workspace.disclosures.riskTitle)}</summary>
        <p>{t(($) => $.investor.workspace.disclosures.riskBody)}</p>
      </details>

      <fieldset>
        <legend>{t(($) => $.investor.fields.edges)}</legend>
        {EDGES.map((edge) => (
          <label key={edge} className="ip-chip">
            <input
              type="checkbox"
              checked={profile.preferred_edge.includes(edge)}
              disabled={busy}
              onChange={() => toggle("preferred_edge", edge)}
            />
            {edge}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>{t(($) => $.investor.fields.flags)}</legend>
        {FLAGS.map((flag) => (
          <label key={flag} className="ip-chip">
            <input
              type="checkbox"
              checked={profile.behavioral_flags.includes(flag)}
              disabled={busy}
              onChange={() => toggle("behavioral_flags", flag)}
            />
            {flag}
          </label>
        ))}
      </fieldset>

      <label>
        {t(($) => $.investor.fields.avoidances)}
        <input
          name="avoidances"
          type="text"
          value={profile.avoidances.join(", ")}
          disabled={busy}
          onChange={(event) => onChange(
            "avoidances",
            event.target.value.split(",").map((value) => value.trim()).filter(Boolean),
          )}
        />
      </label>

      <label>
        {t(($) => $.investor.fields.notes)}
        <textarea
          name="freeform_notes"
          value={profile.freeform_notes}
          disabled={busy}
          onChange={(event) => onChange("freeform_notes", event.target.value)}
        />
      </label>
      <p className="muted">{t(($) => $.investor.workspace.notes.nonCausalHelp)}</p>

      <div className="ip-guardrail">
        {t(($) => $.investor.workspace.summary.riskComparison)}
        <StatusBadge
          state={profile.risk_mismatch === "none" ? "ready" : "partial"}
          label={mismatchLabel(profile.risk_mismatch, commonT)}
        />
      </div>
      <div className="muted">{t(($) => $.investor.fields.skillMode)}</div>

      <div className="ip-actions">
        <Button
          icon={<FileText size={16} />}
          disabled={busy}
          onClick={onDraft}
        >
          {t(($) => $.investor.workspace.actions.saveDraft)}
        </Button>
        <Button
          tone="primary"
          icon={<Save size={16} />}
          busy={busy}
          onClick={onSave}
        >
          {busy
            ? t(($) => $.investor.workspace.actions.saving)
            : t(($) => $.investor.workspace.actions.saveProfile)}
        </Button>
      </div>
    </section>
  );
}
