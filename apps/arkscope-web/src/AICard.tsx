// §2 AI research card — the product's core differentiation, rendered in the
// Watchlist detail "AI summary" tab. This is a per-ticker *scoped entrypoint*
// for the card capability; conversational follow-up belongs to the unified
// AI-Research thread pool (ProductSpec §6), not a separate per-ticker chat room.
//
// Generate runs the server-side gather + synthesis (objective evidence →
// validated ResultCard); the card shows the fixed §2 schema (conclusion · 反方
// 理由 · 失效條件 · per-claim traceability) and can be promoted to a report.
// CardView / CardModal are exported so Home can read a card in place.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  generateCard,
  getCard,
  getCards,
  saveCard,
  type CardSummary,
  type EvidenceItem,
  type EvidencePacket,
  type ResultCard,
} from "./api";

export function AICardTab({ ticker }: { ticker: string }) {
  const [recent, setRecent] = useState<CardSummary[] | null>(null);
  const [card, setCard] = useState<ResultCard | null>(null);
  const [evidencePacket, setEvidencePacket] = useState<EvidencePacket | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Request token for IN-INSTANCE supersession: generate() and openCard() bump
  // it, so if the user opens a recent card (or starts another generate) while a
  // 1-2 min generate is still running, the stale response is dropped instead of
  // clobbering the newer one. Cross-ticker isolation comes from the parent
  // remounting this component per ticker (Watchlist keys TickerDetail by
  // ticker), NOT from this token.
  const reqRef = useRef(0);

  const loadRecent = useCallback(async () => {
    const id = reqRef.current;
    try {
      const d = await getCards(ticker, 10);
      if (id === reqRef.current) setRecent(d.cards);
    } catch (e) {
      if (id === reqRef.current) setErr(e instanceof Error ? e.message : String(e));
    }
  }, [ticker]);

  useEffect(() => {
    reqRef.current++; // invalidate any in-flight response from a prior ticker
    setCard(null);
    setEvidencePacket(null);
    setRunId(null);
    setSaved(false);
    setSaving(false);
    setBusy(false);
    setErr(null);
    setRecent(null);
    void loadRecent();
  }, [ticker, loadRecent]);

  async function generate() {
    if (busy) return;
    const id = ++reqRef.current;
    setBusy(true);
    setErr(null);
    setCard(null);
    setEvidencePacket(null);
    setRunId(null);
    setSaved(false);
    try {
      const r = await generateCard(ticker, {
        question: question.trim() || undefined,
        provider: "anthropic",
        // include_sa intentionally omitted → backend uses config.sa_enabled.
      });
      if (id !== reqRef.current) return; // superseded (ticker switch / new action)
      setCard(r.card);
      setEvidencePacket(r.evidence_packet);
      setRunId(r.run_id);
      void loadRecent();
    } catch (e) {
      if (id === reqRef.current) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      if (id === reqRef.current) setBusy(false);
    }
  }

  async function openCard(rid: number) {
    const id = ++reqRef.current;
    setErr(null);
    try {
      const d = await getCard(rid);
      if (id !== reqRef.current) return;
      setCard(d.card);
      setEvidencePacket(d.evidence_packet);
      setRunId(d.run_id);
      setSaved(d.status === "saved");
    } catch (e) {
      if (id === reqRef.current) setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function save() {
    if (runId == null || saved || saving) return;
    setSaving(true);
    try {
      await saveCard(runId);
      setSaved(true);
      void loadRecent();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  function backToList() {
    setCard(null);
    setEvidencePacket(null);
    setRunId(null);
    void loadRecent();
  }

  return (
    <div className="aicard">
      <div className="aicard-actions">
        <input
          className="aicard-q"
          placeholder={`針對 ${ticker} 的問題（可留空）…`}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter") void generate();
          }}
        />
        <button className="btn-ghost" onClick={() => void generate()} disabled={busy}>
          {busy ? "產生中…" : "✨ 產生卡片"}
        </button>
      </div>
      {busy && <p className="muted tiny">蒐集客觀證據 + 合成卡片，單檔約 1–2 分鐘…</p>}
      {err && <p className="refresh-err tiny">{err}</p>}

      {card ? (
        <CardView
          card={card}
          evidencePacket={evidencePacket}
          saved={saved}
          saving={saving}
          onSave={() => void save()}
          onBack={backToList}
        />
      ) : (
        !busy && (
          <>
            <h4 className="detail-section">最近卡片</h4>
            {recent === null ? (
              <p className="muted tiny">loading…</p>
            ) : recent.length === 0 ? (
              <p className="muted tiny">尚無卡片。按上方「產生卡片」建立第一張。</p>
            ) : (
              <ul className="aicard-recent">
                {recent.map((c) => (
                  <li key={c.run_id} onClick={() => void openCard(c.run_id)}>
                    <span className={`conf conf-${c.confidence_level ?? "na"}`}>
                      {(c.confidence_level ?? "—").toUpperCase()}
                    </span>
                    <span className="aicard-recent-concl">{c.conclusion ?? "—"}</span>
                    {c.status === "saved" && <span className="saved-star" title="saved as report">★</span>}
                  </li>
                ))}
              </ul>
            )}
          </>
        )
      )}
    </div>
  );
}

// Full card renderer. `onBack` is optional — omit it (e.g. in a modal that has
// its own close button) to hide the internal back button.
export function CardView({
  card,
  evidencePacket,
  saved,
  saving,
  onSave,
  onBack,
  backLabel = "← 卡片列表",
}: {
  card: ResultCard;
  evidencePacket?: EvidencePacket | null;
  saved: boolean;
  saving?: boolean;
  onSave: () => void;
  onBack?: () => void;
  backLabel?: string;
}) {
  const tr = card.traceability;
  const evidenceById = new Map(
    (evidencePacket?.items ?? []).map((item) => [item.evidence_id, item]),
  );
  const citedEvidenceIds = unique(
    tr.claims.flatMap((claim) => claim.evidence_ids),
  );
  const shownEvidence =
    citedEvidenceIds.length > 0
      ? citedEvidenceIds.map((id) => evidenceById.get(id)).filter((x): x is EvidenceItem => Boolean(x))
      : (evidencePacket?.items ?? []);

  return (
    <div className="cardview">
      <div className="cardview-head">
        {onBack && (
          <button className="btn-ghost" onClick={onBack}>
            {backLabel}
          </button>
        )}
        <span className="spacer" />
        <span className={`conf conf-${card.confidence_level}`}>{card.confidence_level.toUpperCase()}</span>
        <button className="btn-ghost" onClick={onSave} disabled={saved || saving}>
          {saved ? "✓ 已存報告" : saving ? "存檔中…" : "存成報告"}
        </button>
      </div>

      {card.question && <p className="cardview-q muted tiny">Q：{card.question}</p>}
      <p className="cardview-concl">{card.conclusion}</p>
      {card.confidence_rationale && (
        <p className="muted tiny">可信度說明：{card.confidence_rationale}</p>
      )}

      <Section title="主要理由" items={card.primary_reasons} />
      <Section title="反方理由" items={card.counter_thesis} counter />
      <Section title="失效條件" items={card.invalidation_conditions} />
      <Section title="觸發條件" items={card.trigger_conditions} />
      <Section title="關鍵假設" items={card.key_assumptions} />
      <Section title="風險" items={card.risks} />
      <Section title="觀察清單" items={card.watch_list} />
      {card.market_narrative && <Para title="市場敘事" text={card.market_narrative} />}
      {card.divergence && <Para title="與共識分歧" text={card.divergence} />}

      <details className="cardview-trace">
        <summary>
          資料來源 · 可追溯性（{tr.data_sources.length} 源 · {tr.claims.length} 引用）
        </summary>
        <ul className="trace-sources">
          {tr.data_sources.map((s, i) => (
            <li key={i}>
              <span className="strong">{s.name}</span>
              {s.as_of && <span className="muted tiny"> · {s.as_of}</span>}
            </li>
          ))}
        </ul>
        {tr.claims.length > 0 && (
          <div className="trace-claims-wrap">
            <div className="muted tiny trace-claims-h">每條主張的引用（claim → evidence_id）</div>
            <ul className="trace-claims">
              {tr.claims.map((c, i) => (
                <li key={i}>
                  <span className="claim-txt">{c.claim}</span>
                  <span className="claim-cite">
                    {c.evidence_ids.length ? c.evidence_ids.join(" · ") : "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {evidencePacket && (
          <div className="trace-evidence-wrap">
            <div className="muted tiny trace-claims-h">
              引用證據摘要（{shownEvidence.length || evidencePacket.items.length} / {evidencePacket.items.length}）
            </div>
            {shownEvidence.length === 0 ? (
              <p className="muted tiny">此卡片沒有可對應的 evidence item。</p>
            ) : (
              <ul className="trace-evidence">
                {shownEvidence.map((item) => (
                  <li key={item.evidence_id}>
                    <div className="evidence-head">
                      <span className="claim-cite">{item.evidence_id}</span>
                      <span className="strong">{item.source}</span>
                      <span className="muted tiny">{item.source_type}</span>
                    </div>
                    <div className="muted tiny">
                      {item.as_of ? `as-of ${item.as_of}` : "as-of —"}
                      {item.freshness ? ` · ${item.freshness}` : ""}
                      {item.is_real_time ? " · realtime" : ""}
                    </div>
                    {item.note && <div className="muted tiny">{item.note}</div>}
                    <div className="evidence-data tiny">{summarizeEvidenceData(item.data)}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="muted tiny">
          completeness — news {yn(tr.completeness.news)} · fundamentals {yn(tr.completeness.fundamentals)} ·
          technicals {yn(tr.completeness.technicals)}
          {tr.completeness.note ? ` · ${tr.completeness.note}` : ""}
        </div>
        <div className="muted tiny">single-model inference: {yn(tr.is_single_model_inference)}</div>
      </details>
    </div>
  );
}

// Read a card in place (e.g. from Home) without navigating. Owns its own fetch
// + save state; CardView renders without an internal back button (the modal has
// its own close).
export function CardModal({
  runId,
  onClose,
  onChanged,
}: {
  runId: number;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const [card, setCard] = useState<ResultCard | null>(null);
  const [evidencePacket, setEvidencePacket] = useState<EvidencePacket | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  // Escape closes; move focus into the dialog on open and restore it on close.
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeBtnRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [onClose]);

  useEffect(() => {
    let alive = true;
    setCard(null);
    setEvidencePacket(null);
    setErr(null);
    setSaved(false);
    setSaving(false);
    getCard(runId)
      .then((d) => {
        if (alive) {
          setCard(d.card);
          setEvidencePacket(d.evidence_packet);
          setSaved(d.status === "saved");
        }
      })
      .catch((e) => {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [runId, reload]);

  async function save() {
    if (saving || saved) return;
    setSaving(true);
    try {
      await saveCard(runId);
      setSaved(true);
      onChanged?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={card ? `${card.ticker} AI 卡片` : "AI 卡片"}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <span className="strong">{card ? `${card.ticker} · AI 卡片` : "AI 卡片"}</span>
          <span className="spacer" />
          <button ref={closeBtnRef} className="btn-ghost" onClick={onClose}>✕ 關閉</button>
        </div>
        {err && <p className="refresh-err tiny">{err}</p>}
        {!card && err ? (
          <div>
            <p className="muted">卡片載入失敗。</p>
            <button className="btn-ghost" onClick={() => setReload((x) => x + 1)}>
              重試
            </button>
          </div>
        ) : !card ? (
          <p className="muted">載入中…</p>
        ) : (
          <CardView
            card={card}
            evidencePacket={evidencePacket}
            saved={saved}
            saving={saving}
            onSave={() => void save()}
          />
        )}
      </div>
    </div>
  );
}

function Section({ title, items, counter }: { title: string; items: string[]; counter?: boolean }) {
  if (!items || items.length === 0) return null;
  return (
    <div className={`card-sec ${counter ? "card-sec-counter" : ""}`}>
      <h5>{title}</h5>
      <ul>
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}

function Para({ title, text }: { title: string; text: string }) {
  return (
    <div className="card-sec">
      <h5>{title}</h5>
      <p>{text}</p>
    </div>
  );
}

function yn(b: boolean): string {
  return b ? "✓" : "—";
}

function unique(xs: string[]): string[] {
  return Array.from(new Set(xs.filter(Boolean)));
}

function summarizeEvidenceData(data: Record<string, unknown>): string {
  const entries = Object.entries(data).slice(0, 6);
  if (entries.length === 0) return "no structured payload";
  return entries.map(([key, value]) => `${key}: ${summarizeValue(value)}`).join(" · ");
}

function summarizeValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return clip(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return `{${keys.slice(0, 4).join(", ")}${keys.length > 4 ? ", …" : ""}}`;
  }
  return clip(String(value));
}

function clip(s: string): string {
  return s.length > 120 ? `${s.slice(0, 117)}…` : s;
}
