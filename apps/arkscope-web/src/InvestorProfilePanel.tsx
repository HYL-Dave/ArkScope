// Track A: Investor Profile + Assistant Stance settings panel (Settings 資料頁).
// Read → edit → 產生設定草稿 (POST /draft, no write) → 儲存設定 (PUT, gated).
// Copy rule: research personalization aid — never financial advice/suitability.

import React, { useEffect, useState } from "react";

import {
  draftInvestorProfile,
  getInvestorProfile,
  saveInvestorProfile,
  type AssistantStance,
  type InvestorProfile,
  type InvestorProfileResponse,
  type InvestorPreset,
} from "./api";
import { mismatchLabel, stanceLabel } from "./personalizationDisplay";

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

  useEffect(() => {
    let cancelled = false;
    getInvestorProfile()
      .then((r) => {
        if (!cancelled) {
          setResp(r);
          setForm(r.profile);
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
        <div className="muted">{err ?? "載入中…"}</div>
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

  const mismatch = resp?.profile.risk_mismatch ?? form.risk_mismatch;

  return (
    <div className="investor-profile-panel">
      <h3>投資人設定</h3>
      <p className="muted">
        研究個人化輔助（非投資建議、非適足性評估）。啟用後,助手依你的風險輪廓與所選立場調整
        分析重點;證據蒐集與反方論點完全不受影響。
      </p>

      <label>
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

      <div className="ip-guardrail">
        風險胃納 vs 承受能力:{mismatchLabel(mismatch)}
      </div>
      <div className="muted">技能模式:off(技能建議屬後續階段,尚未啟用)</div>

      <div className="ip-actions">
        <button disabled={busy} onClick={() => void run(() => draftInvestorProfile(payload()), "草稿已產生(未儲存)")}>
          產生設定草稿
        </button>
        <button disabled={busy} onClick={() => void run(() => saveInvestorProfile(payload()), "已儲存")}>
          儲存設定
        </button>
      </div>
      {notice ? <div className="muted">{notice}</div> : null}
      {err ? <div className="error">{err}</div> : null}
    </div>
  );
}
