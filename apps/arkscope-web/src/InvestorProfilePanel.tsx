// Track A: Investor Profile + Assistant Stance settings panel (Settings 資料頁).
// Read → edit → 產生設定草稿 (POST /draft, no write) → 儲存設定 (PUT, gated).
// Copy rule: research personalization aid — never financial advice/suitability.

import React, { useEffect, useState } from "react";

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
import { mismatchLabel, stanceLabel } from "./personalizationDisplay";
import { Button, InlineAlert, StatusBadge } from "./ui";

const PRESETS: Array<{ value: InvestorPreset; label: string }> = [
  { value: "growth", label: "成長投資人（預設）" },
  { value: "value", label: "價值" },
  { value: "momentum", label: "動能" },
  { value: "income", label: "收益" },
  { value: "event_driven", label: "事件驅動" },
  { value: "balanced", label: "均衡" },
  { value: "custom", label: "自訂" },
];

const STANCES: AssistantStance[] = [
  "neutral",
  "aligned",
  "complementary",
  "strict_risk_control",
  "valuation_rationalist",
  "growth_opportunity",
];

const HORIZONS: Array<{ value: string; label: string }> = [
  { value: "intraday", label: "當沖" },
  { value: "days_weeks", label: "數天〜數週" },
  { value: "months", label: "數月" },
  { value: "multi_year", label: "多年" },
  { value: "mixed", label: "混合" },
];

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

export function InvestorProfilePanel() {
  const [resp, setResp] = useState<InvestorProfileResponse | null>(null);
  const [form, setForm] = useState<InvestorProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [calibration, setCalibration] = useState<CalibrationState | null>(null);
  const [calibrationText, setCalibrationText] = useState("");

  useEffect(() => {
    let cancelled = false;
    getInvestorProfile()
      .then(async (r) => {
        if (!cancelled) {
          setResp(r);
          setForm(r.profile);
        }
        try {
          const c = await getCalibrationState();
          if (!cancelled) applyCalibrationState(c);
        } catch {
          // Calibration is advisory. A temporary route failure must not block
          // the base Investor Profile form.
        }
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!form) {
    return (
      <div className="investor-profile-panel">
        <h3>投資人設定</h3>
        {err ? (
          <InlineAlert state="failed" title="投資人設定失敗">{err}</InlineAlert>
        ) : (
          <StatusBadge state="loading" label="載入投資人設定" />
        )}
      </div>
    );
  }

  const set = <K extends keyof InvestorProfile>(key: K, value: InvestorProfile[K]) =>
    setForm({ ...form, [key]: value });

  const applyCalibrationState = (state: CalibrationState) => {
    setCalibration(state);
    const proposal = state.latest_proposal;
    if (proposal?.status === "draft") {
      setForm((cur) => (cur ? { ...cur, ...proposal.profile_patch } : cur));
    }
  };

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

  const run = async (fn: () => Promise<InvestorProfileResponse>, doneNote: string) => {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const r = await fn();
      setResp(r);
      setForm(r.profile);
      setNotice(doneNote);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runCalibration = async (fn: () => Promise<CalibrationState>, doneNote: string) => {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const r = await fn();
      applyCalibrationState(r);
      setNotice(doneNote);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const sendCalibration = async () => {
    const text = calibrationText.trim();
    if (!text) return;
    await runCalibration(
      () => sendCalibrationMessage({ session_id: calibration?.active_session?.id, content: text }),
      "校準回覆已更新",
    );
    setCalibrationText("");
  };

  const approveProposal = async () => {
    const proposal = calibration?.latest_proposal;
    if (!proposal || proposal.status !== "draft") return;
    if (busy) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      await approveCalibrationProposal(proposal.id, payload());
      const profileResp = await getInvestorProfile();
      setResp(profileResp);
      setForm(profileResp.profile);
      const refreshed = await getCalibrationState();
      applyCalibrationState(refreshed);
      setNotice("校準提案已套用");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const rejectProposal = async () => {
    const proposal = calibration?.latest_proposal;
    if (!proposal || proposal.status !== "draft") return;
    await runCalibration(async () => {
      await rejectCalibrationProposal(proposal.id);
      return getCalibrationState();
    }, "校準提案已拒絕");
  };

  const mismatch = resp?.profile.risk_mismatch ?? form.risk_mismatch;
  const messages = calibration?.messages ?? [];
  const latestProposal = calibration?.latest_proposal?.status === "draft" ? calibration.latest_proposal : null;
  const rationaleEntries = Object.entries(latestProposal?.rationales ?? {});

  return (
    <div className="investor-profile-panel">
      <h3>投資人設定</h3>
      <p className="muted">
        研究個人化輔助（非投資建議、非適足性評估）。啟用後,助手依你的風險輪廓與所選立場調整
        分析重點;證據蒐集與反方論點完全不受影響。
      </p>

      <label className="ip-toggle">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => set("enabled", e.target.checked)}
        />{" "}
        啟用個人化(目前生效立場:{stanceLabel(resp?.effective_stance ?? "off")})
      </label>

      <div className="ip-grid">
        <label>
          投資風格
          <select
            value={form.primary_preset}
            onChange={(e) => set("primary_preset", e.target.value as InvestorPreset)}
          >
            {PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          風險胃納(1-10)
          <select
            value={form.risk_appetite ?? ""}
            onChange={(e) =>
              set("risk_appetite", e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">未設定</option>
            {SCORES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <label>
          風險承受能力(1-10)
          <select
            value={form.risk_capacity ?? ""}
            onChange={(e) =>
              set("risk_capacity", e.target.value === "" ? null : Number(e.target.value))
            }
          >
            <option value="">未設定</option>
            {SCORES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <label>
          持有週期
          <select
            value={form.holding_horizon}
            onChange={(e) => set("holding_horizon", e.target.value)}
          >
            {HORIZONS.map((h) => (
              <option key={h.value} value={h.value}>
                {h.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          可承受回撤 %
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
          單一部位上限 %
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
          預設助手立場
          <select
            value={form.default_stance}
            onChange={(e) => set("default_stance", e.target.value as AssistantStance)}
          >
            {STANCES.map((s) => (
              <option key={s} value={s}>
                {stanceLabel(s)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset>
        <legend>偏好優勢</legend>
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
        <legend>行為傾向(供助手校準,非診斷)</legend>
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
        想避開的(逗號分隔)
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
        自由描述(目標、自我觀察、想被怎麼協助)
        <textarea
          value={form.freeform_notes}
          onChange={(e) => set("freeform_notes", e.target.value)}
        />
      </label>

      <section className="ip-calibration">
        <h4>校準對話</h4>
        <p className="muted">
          校準對話只用來整理投資人輪廓,不是投資建議或個股推薦。只有你核准的結構化設定會影響研究;原始對話不會進入研究 prompt。
        </p>
        <div className="ip-actions">
          <Button
            disabled={busy || Boolean(calibration?.active_session)}
            onClick={() => void runCalibration(() => startCalibrationSession(false), "校準對話已開始")}
          >
            開始校準對話
          </Button>
        </div>
        {messages.length ? (
          <div className="ip-calibration-log">
            {messages.map((m) => (
              <div key={m.id} className="muted">
                {m.role === "user" ? "你" : "助手"}:{m.content}
              </div>
            ))}
          </div>
        ) : null}
        <label>
          校準訊息
          <textarea
            aria-label="校準訊息"
            value={calibrationText}
            onChange={(e) => setCalibrationText(e.target.value)}
          />
        </label>
        <div className="ip-actions">
          <Button disabled={busy || !calibration?.active_session || !calibrationText.trim()} onClick={() => void sendCalibration()}>
            送出校準訊息
          </Button>
        </div>
        {latestProposal ? (
          <div className="ip-guardrail">
            <strong>
              校準提案 <StatusBadge state="partial" label="待核准校準提案" />
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
                套用校準提案
              </Button>
              <Button disabled={busy} onClick={() => void rejectProposal()}>
                拒絕提案
              </Button>
            </div>
          </div>
        ) : null}
      </section>

      <div className="ip-guardrail">
        風險胃納 vs 承受能力:
        <StatusBadge
          state={mismatch === "none" ? "ready" : "partial"}
          label={mismatchLabel(mismatch)}
        />
      </div>
      <div className="muted">技能模式:off(技能建議屬後續階段,尚未啟用)</div>

      <div className="ip-actions">
        <Button disabled={busy} onClick={() => void run(() => draftInvestorProfile(payload()), "草稿已產生(未儲存)")}>
          產生設定草稿
        </Button>
        <Button disabled={busy} onClick={() => void run(() => saveInvestorProfile(payload()), "已儲存")}>
          儲存設定
        </Button>
      </div>
      {notice ? <InlineAlert state="ready" title={notice} /> : null}
      {err ? <InlineAlert state="failed" title="投資人設定失敗">{err}</InlineAlert> : null}
    </div>
  );
}
