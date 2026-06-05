// §2 AI research card — the product's core differentiation, rendered in the
// Watchlist detail "AI summary" tab. Generate runs the server-side gather +
// synthesis (objective evidence → validated ResultCard); the card shows the
// fixed §2 schema (conclusion · 反方理由 · 失效條件 · per-claim traceability) and
// can be promoted to a durable report. Recent cards for the ticker are listed
// when nothing is open. AI lives here, per-ticker, not in a separate chat tab.

import { useCallback, useEffect, useState } from "react";
import {
  generateCard,
  getCard,
  getCards,
  saveCard,
  type CardSummary,
  type ResultCard,
} from "./api";

export function AICardTab({ ticker }: { ticker: string }) {
  const [recent, setRecent] = useState<CardSummary[] | null>(null);
  const [card, setCard] = useState<ResultCard | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadRecent = useCallback(async () => {
    try {
      const d = await getCards(ticker, 10);
      setRecent(d.cards);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [ticker]);

  // Reset to the recent-list view whenever the selected ticker changes.
  useEffect(() => {
    setCard(null);
    setRunId(null);
    setSaved(false);
    setErr(null);
    setRecent(null);
    void loadRecent();
  }, [ticker, loadRecent]);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setCard(null);
    setRunId(null);
    setSaved(false);
    try {
      const r = await generateCard(ticker, {
        question: question.trim() || undefined,
        provider: "anthropic",
        include_sa: false,
      });
      setCard(r.card);
      setRunId(r.run_id);
      void loadRecent();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function openCard(rid: number) {
    setErr(null);
    try {
      const d = await getCard(rid);
      setCard(d.card);
      setRunId(d.run_id);
      setSaved(d.status === "saved");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function save() {
    if (runId == null || saved) return;
    try {
      await saveCard(runId);
      setSaved(true);
      void loadRecent();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
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
          saved={saved}
          onSave={() => void save()}
          onBack={() => {
            setCard(null);
            setRunId(null);
            void loadRecent();
          }}
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

function CardView({
  card,
  saved,
  onSave,
  onBack,
}: {
  card: ResultCard;
  saved: boolean;
  onSave: () => void;
  onBack: () => void;
}) {
  const tr = card.traceability;
  return (
    <div className="cardview">
      <div className="cardview-head">
        <button className="btn-ghost" onClick={onBack}>← 卡片列表</button>
        <span className="spacer" />
        <span className={`conf conf-${card.confidence_level}`}>{card.confidence_level.toUpperCase()}</span>
        <button className="btn-ghost" onClick={onSave} disabled={saved}>
          {saved ? "✓ 已存報告" : "存成報告"}
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
