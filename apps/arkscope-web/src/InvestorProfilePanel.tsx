// Track A: Investor Profile + Assistant Stance settings panel (Settings 資料頁).
// Read → edit → 產生設定草稿 (POST /draft, no write) → 儲存設定 (PUT, gated).
// Copy rule: research personalization aid — never financial advice/suitability.

import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  approveCalibrationProposal,
  draftInvestorProfile,
  getCalibrationState,
  getInvestorProfile,
  rejectCalibrationProposal,
  saveInvestorProfile,
  sendCalibrationMessage,
  startCalibrationSession,
  type AssistantStance,
  type CalibrationState,
  type InvestorProfile,
  type InvestorProfileResponse,
  type InvestorPreset,
} from "./api";
import { DeveloperDiagnostics } from "./settings/DeveloperDiagnostics";
import { settingsErrorPresentation } from "./settings/settingsBackendCopy";
import {
  settingsInvestorHorizonLabel,
  settingsInvestorPresetLabel,
  settingsMismatchLabel,
  settingsStanceLabel,
  type SettingsT,
} from "./settings/settingsCopy";
import { Button, InlineAlert, StatusBadge } from "./ui";

const PRESETS: InvestorPreset[] = [
  "growth",
  "value",
  "momentum",
  "income",
  "event_driven",
  "balanced",
  "custom",
];

const STANCES: AssistantStance[] = [
  "neutral",
  "aligned",
  "complementary",
  "strict_risk_control",
  "valuation_rationalist",
  "growth_opportunity",
];

const HORIZONS = ["intraday", "days_weeks", "months", "multi_year", "mixed"];

const EDGES = ["growth", "valuation", "catalyst", "quality", "momentum", "macro", "options", "sentiment"];
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
];

const SCORES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

type InvestorOutcome =
  | "calibration_started"
  | "calibration_updated"
  | "proposal_applied"
  | "proposal_rejected"
  | "draft_generated"
  | "saved";

type CalibrationRunResult = "current" | "stale" | "not_started";

function investorOutcomeLabel(outcome: InvestorOutcome, t: SettingsT): string {
  switch (outcome) {
    case "calibration_started":
      return t(($) => $.investor.calibration.started);
    case "calibration_updated":
      return t(($) => $.investor.calibration.updated);
    case "proposal_applied":
      return t(($) => $.investor.proposal.applied);
    case "proposal_rejected":
      return t(($) => $.investor.proposal.rejected);
    case "draft_generated":
      return t(($) => $.investor.draft.success);
    case "saved":
      return t(($) => $.investor.saveSuccess);
  }
}

export function InvestorProfilePanel({ developerMode = false }: { developerMode?: boolean }) {
  const { t } = useTranslation("settings");
  const [resp, setResp] = useState<InvestorProfileResponse | null>(null);
  const [form, setForm] = useState<InvestorProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<Error | null>(null);
  const [outcome, setOutcome] = useState<InvestorOutcome | null>(null);
  const [calibration, setCalibration] = useState<CalibrationState | null>(null);
  const [calibrationText, setCalibrationText] = useState("");
  const calibrationGenerationRef = useRef(0);

  const applyCalibrationState = (
    state: CalibrationState,
    generation: number,
    expectedProfile?: InvestorProfile,
  ) => {
    if (calibrationGenerationRef.current !== generation) return false;
    setCalibration(state);
    const proposal = state.latest_proposal;
    if (proposal?.status === "draft") {
      setForm((cur) => {
        if (!cur || (expectedProfile && cur !== expectedProfile)) return cur;
        return { ...cur, ...proposal.profile_patch };
      });
    }
    return true;
  };

  useEffect(() => {
    let cancelled = false;
    getInvestorProfile()
      .then(async (r) => {
        if (!cancelled) {
          setResp(r);
          setForm(r.profile);
        }
        const generation = calibrationGenerationRef.current;
        try {
          const c = await getCalibrationState();
          if (!cancelled) applyCalibrationState(c, generation, r.profile);
        } catch {
          // Calibration is advisory. A temporary route failure must not block
          // the base Investor Profile form.
        }
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e : new Error(String(e)));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const errorPresentation = err ? settingsErrorPresentation(err, t) : null;

  if (!form) {
    return (
      <div className="investor-profile-panel">
        <h3>{t(($) => $.registry.sections.investorProfile.title)}</h3>
        {errorPresentation ? (
          <InlineAlert state="failed" title={errorPresentation.message} />
        ) : (
          <StatusBadge state="loading" label={t(($) => $.investor.panel.loading)} />
        )}
        {developerMode ? (
          <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
        ) : null}
      </div>
    );
  }

  const set = <K extends keyof InvestorProfile>(key: K, value: InvestorProfile[K]) =>
    setForm({ ...form, [key]: value });

  const toggleIn = (key: "preferred_edge" | "behavioral_flags", item: string) => {
    const cur = form[key];
    set(key, cur.includes(item) ? cur.filter((x) => x !== item) : [...cur, item]);
  };

  const payload = (): Partial<InvestorProfile> => ({
    enabled: form.enabled,
    primary_preset: form.primary_preset,
    risk_appetite: form.risk_appetite,
    risk_capacity: form.risk_capacity,
    holding_horizon: form.holding_horizon,
    drawdown_tolerance_pct: form.drawdown_tolerance_pct,
    concentration_limit_pct: form.concentration_limit_pct,
    preferred_edge: form.preferred_edge,
    avoidances: form.avoidances,
    behavioral_flags: form.behavioral_flags,
    freeform_notes: form.freeform_notes,
    default_stance: form.default_stance,
  });

  const run = async (
    fn: () => Promise<InvestorProfileResponse>,
    completedOutcome: InvestorOutcome,
  ) => {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setOutcome(null);
    try {
      const r = await fn();
      setResp(r);
      setForm(r.profile);
      setOutcome(completedOutcome);
    } catch (e) {
      setErr(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  };

  const runCalibration = async (
    fn: () => Promise<CalibrationState>,
    completedOutcome: InvestorOutcome,
  ): Promise<CalibrationRunResult> => {
    if (busy) return "not_started";
    const generation = ++calibrationGenerationRef.current;
    setBusy(true);
    setErr(null);
    setOutcome(null);
    try {
      const r = await fn();
      if (!applyCalibrationState(r, generation)) return "stale";
      setOutcome(completedOutcome);
      return "current";
    } catch (e) {
      if (calibrationGenerationRef.current === generation) {
        setErr(e instanceof Error ? e : new Error(String(e)));
        return "current";
      }
      return "stale";
    } finally {
      if (calibrationGenerationRef.current === generation) setBusy(false);
    }
  };

  const sendCalibration = async () => {
    const text = calibrationText.trim();
    if (!text) return;
    const result = await runCalibration(
      () => sendCalibrationMessage({ session_id: calibration?.active_session?.id, content: text }),
      "calibration_updated",
    );
    if (result === "current") setCalibrationText("");
  };

  const approveProposal = async () => {
    const proposal = calibration?.latest_proposal;
    if (!proposal || proposal.status !== "draft") return;
    if (busy) return;
    const generation = ++calibrationGenerationRef.current;
    setBusy(true);
    setErr(null);
    setOutcome(null);
    try {
      await approveCalibrationProposal(proposal.id, payload());
      const profileResp = await getInvestorProfile();
      if (calibrationGenerationRef.current === generation) {
        setResp(profileResp);
        setForm(profileResp.profile);
      }
      const refreshed = await getCalibrationState();
      if (calibrationGenerationRef.current === generation) {
        applyCalibrationState(refreshed, generation);
        setOutcome("proposal_applied");
      }
    } catch (e) {
      if (calibrationGenerationRef.current === generation) {
        setErr(e instanceof Error ? e : new Error(String(e)));
      }
    } finally {
      if (calibrationGenerationRef.current === generation) setBusy(false);
    }
  };

  const rejectProposal = async () => {
    const proposal = calibration?.latest_proposal;
    if (!proposal || proposal.status !== "draft") return;
    await runCalibration(async () => {
      await rejectCalibrationProposal(proposal.id);
      return getCalibrationState();
    }, "proposal_rejected");
  };

  const mismatch = resp?.profile.risk_mismatch ?? form.risk_mismatch;
  const messages = calibration?.messages ?? [];
  const latestProposal = calibration?.latest_proposal?.status === "draft" ? calibration.latest_proposal : null;
  const rationaleEntries = Object.entries(latestProposal?.rationales ?? {});
  const outcomeLabel = outcome ? investorOutcomeLabel(outcome, t) : null;

  return (
    <div className="investor-profile-panel" aria-busy={busy}>
      <h3>{t(($) => $.registry.sections.investorProfile.title)}</h3>
      <p className="muted">{t(($) => $.investor.panel.description)}</p>
      {busy ? <StatusBadge state="running" label={t(($) => $.investor.panel.updating)} /> : null}

      <label className="ip-toggle">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => set("enabled", e.target.checked)}
        />{" "}
        {t(($) => $.investor.fields.enabledWithStance, {
          value: settingsStanceLabel(resp?.effective_stance ?? "off", t),
        })}
      </label>

      <div className="ip-grid">
        <label>
          {t(($) => $.investor.fields.preset)}
          <select
            value={form.primary_preset}
            onChange={(e) => set("primary_preset", e.target.value as InvestorPreset)}
          >
            {PRESETS.map((p) => (
              <option key={p} value={p}>
                {settingsInvestorPresetLabel(p, t)}
              </option>
            ))}
          </select>
        </label>

        <label>
          {t(($) => $.investor.fields.riskAppetite)}
          <select
            value={form.risk_appetite ?? ""}
            onChange={(e) =>
              set("risk_appetite", e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">{t(($) => $.investor.fields.unset)}</option>
            {SCORES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <label>
          {t(($) => $.investor.fields.riskCapacity)}
          <select
            value={form.risk_capacity ?? ""}
            onChange={(e) =>
              set("risk_capacity", e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">{t(($) => $.investor.fields.unset)}</option>
            {SCORES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <label>
          {t(($) => $.investor.fields.horizon)}
          <select
            value={form.holding_horizon}
            onChange={(e) => set("holding_horizon", e.target.value)}
          >
            {HORIZONS.map((h) => (
              <option key={h} value={h}>
                {settingsInvestorHorizonLabel(h, t)}
              </option>
            ))}
          </select>
        </label>

        <label>
          {t(($) => $.investor.fields.drawdown)}
          <input
            type="number"
            min={1}
            max={100}
            value={form.drawdown_tolerance_pct ?? ""}
            onChange={(e) =>
              set(
                "drawdown_tolerance_pct",
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
          />
        </label>

        <label>
          {t(($) => $.investor.fields.concentration)}
          <input
            type="number"
            min={1}
            max={100}
            value={form.concentration_limit_pct ?? ""}
            onChange={(e) =>
              set(
                "concentration_limit_pct",
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
          />
        </label>

        <label>
          {t(($) => $.investor.fields.stance)}
          <select
            value={form.default_stance}
            onChange={(e) => set("default_stance", e.target.value as AssistantStance)}
          >
            {STANCES.map((s) => (
              <option key={s} value={s}>
                {settingsStanceLabel(s, t)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset>
        <legend>{t(($) => $.investor.fields.edges)}</legend>
        {EDGES.map((edge) => (
          <label key={edge} className="ip-chip">
            <input
              type="checkbox"
              checked={form.preferred_edge.includes(edge)}
              onChange={() => toggleIn("preferred_edge", edge)}
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
              checked={form.behavioral_flags.includes(flag)}
              onChange={() => toggleIn("behavioral_flags", flag)}
            />
            {flag}
          </label>
        ))}
      </fieldset>

      <label>
        {t(($) => $.investor.fields.avoidances)}
        <input
          type="text"
          value={form.avoidances.join(", ")}
          onChange={(e) =>
            set(
              "avoidances",
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
        />
      </label>

      <label>
        {t(($) => $.investor.fields.notes)}
        <textarea
          value={form.freeform_notes}
          onChange={(e) => set("freeform_notes", e.target.value)}
        />
      </label>

      <section className="ip-calibration">
        <h4>{t(($) => $.investor.calibration.title)}</h4>
        <p className="muted">{t(($) => $.investor.calibration.description)}</p>
        <div className="ip-actions">
          <Button
            disabled={busy || Boolean(calibration?.active_session)}
            onClick={() => void runCalibration(
              () => startCalibrationSession(false),
              "calibration_started",
            )}
          >
            {t(($) => $.investor.calibration.start)}
          </Button>
        </div>
        {messages.length ? (
          <div className="ip-calibration-log">
            {messages.map((m) => (
              <div key={m.id} className="muted">
                {m.role === "user"
                  ? t(($) => $.investor.calibration.user)
                  : t(($) => $.investor.calibration.assistant)}:{m.content}
              </div>
            ))}
          </div>
        ) : null}
        <label>
          {t(($) => $.investor.calibration.messageLabel)}
          <textarea
            aria-label={t(($) => $.investor.calibration.messageLabel)}
            value={calibrationText}
            onChange={(e) => setCalibrationText(e.target.value)}
          />
        </label>
        <div className="ip-actions">
          <Button disabled={busy || !calibration?.active_session || !calibrationText.trim()} onClick={() => void sendCalibration()}>
            {t(($) => $.investor.calibration.send)}
          </Button>
        </div>
        {latestProposal ? (
          <div className="ip-guardrail">
            <strong>
              {t(($) => $.investor.proposal.title)}{" "}
              <StatusBadge state="partial" label={t(($) => $.investor.proposal.pending)} />
            </strong>
            {rationaleEntries.length ? (
              <ul>
                {rationaleEntries.map(([field, rationale]) => (
                  <li key={field}>
                    {field}:{rationale}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="ip-actions">
              <Button disabled={busy} onClick={() => void approveProposal()}>
                {t(($) => $.investor.proposal.apply)}
              </Button>
              <Button disabled={busy} onClick={() => void rejectProposal()}>
                {t(($) => $.investor.proposal.reject)}
              </Button>
            </div>
          </div>
        ) : null}
      </section>

      <div className="ip-guardrail">
        {t(($) => $.investor.fields.riskComparison)}
        <StatusBadge
          state={mismatch === "none" ? "ready" : "partial"}
          label={settingsMismatchLabel(mismatch, t)}
        />
      </div>
      <div className="muted">{t(($) => $.investor.fields.skillMode)}</div>

      <div className="ip-actions">
        <Button disabled={busy} onClick={() => void run(
          () => draftInvestorProfile(payload()),
          "draft_generated",
        )}>
          {t(($) => $.investor.draft.action)}
        </Button>
        <Button disabled={busy} onClick={() => void run(
          () => saveInvestorProfile(payload()),
          "saved",
        )}>
          {t(($) => $.investor.saveAction)}
        </Button>
      </div>
      {outcomeLabel ? <InlineAlert state="ready" title={outcomeLabel} /> : null}
      {errorPresentation ? (
        <InlineAlert state="failed" title={errorPresentation.message} />
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}
    </div>
  );
}
