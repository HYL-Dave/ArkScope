// Home / 工作台 — the workbench first-screen (vision PDF p13/p20).
//
// Replaces the old dev "Dashboard" (now demoted to System/Health) as the product
// home. v0 is deliberately bounded: an overview strip + the watchlist's top
// movers (reusing the cockpit DTO) + a Recent-AI-cards list. AI lives in the
// per-ticker detail (Watchlist → AI summary), surfaced back here as recent cards.

import { useCallback, useEffect, useState } from "react";
import {
  getCards,
  getCockpitWatchlist,
  type CardSummary,
  type CockpitRow,
  type CockpitWatchlist,
} from "./api";
import type { StatusState } from "./Dashboard";
import { CardModal } from "./AICard";

type NavTarget = "Home" | "Watchlist" | "System";

export function HomeView({
  status,
  onNavigate,
}: {
  status: StatusState;
  onNavigate: (view: NavTarget) => void;
}) {
  const [wl, setWl] = useState<CockpitWatchlist | null>(null);
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openCardId, setOpenCardId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [w, c] = await Promise.all([getCockpitWatchlist(false), getCards(undefined, 8)]);
      setWl(w);
      setCards(c.cards);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dsCount = status.kind === "ready" ? Object.keys(status.status.data_sources).length : null;
  const rows = wl?.rows ?? [];
  const movers = [...rows]
    .sort((a, b) => moverWeight(b) - moverWeight(a))
    .slice(0, 8);

  return (
    <>
      <main className="main">
        <div className="home">
          <section className="home-overview">
            <OvTile label="自選股" value={wl ? wl.shown : "—"}
              sub={wl ? `${wl.total} 檔 · ${wl.archived_count} 已封存` : "loading…"} />
            <OvTile label="告警" value="—" sub="尚未啟用" />
            <OvTile label="資料來源" value={dsCount ?? "—"}
              sub={status.kind === "ready" ? `${status.status.tools_registered} tools` : "—"} />
            <OvTile label="資料時間" value={wl?.as_of ? fmtDate(wl.as_of) : "—"} sub="watchlist as-of" />
          </section>

          {err && (
            <div className="refresh-err">
              無法載入工作台資料：{err}{" "}
              <button className="btn-ghost" onClick={() => void load()}>重試</button>
            </div>
          )}

          <section className="home-block">
            <div className="home-block-head">
              <h2>自選股動態 <span className="muted tiny">top movers · 7d</span></h2>
              <button className="btn-ghost" onClick={() => onNavigate("Watchlist")}>查看全部 →</button>
            </div>
            {rows.length === 0 ? (
              <p className="muted">尚無自選股資料。</p>
            ) : (
              <table className="home-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th className="num">Close</th>
                    <th className="num">7d %</th>
                    <th className="num">News</th>
                    <th>Priority</th>
                  </tr>
                </thead>
                <tbody>
                  {movers.map((r) => (
                    <tr key={r.ticker}>
                      <td className="strong">{r.ticker}</td>
                      <td className="num">{fmtNum(r.latest_close)}</td>
                      <td className={`num ${changeClass(r.change_7d_pct)}`}>{fmtPct(r.change_7d_pct)}</td>
                      <td className="num">{r.news_count_7d}</td>
                      <td>{r.priority || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="home-block">
            <div className="home-block-head">
              <h2>最近 AI 卡片 <span className="muted tiny">recent research cards</span></h2>
              <button className="btn-ghost" onClick={() => onNavigate("Watchlist")}>到自選股產生 →</button>
            </div>
            {cards === null ? (
              <p className="muted">載入中…</p>
            ) : cards.length === 0 ? (
              <p className="muted">尚無 AI 卡片。在自選股詳情頁產生第一張研究卡片。</p>
            ) : (
              <ul className="card-list">
                {cards.map((c) => (
                  <li key={c.run_id} className="card-row" onClick={() => setOpenCardId(c.run_id)}>
                    <span className="card-ticker">{c.ticker}</span>
                    <span className={`conf conf-${c.confidence_level ?? "na"}`}>
                      {(c.confidence_level ?? "—").toUpperCase()}
                    </span>
                    <span className="card-concl">{c.conclusion ?? "—"}</span>
                    <span className="card-time muted tiny">{fmtDate(c.generated_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </main>

      <aside className="rightpanel">
        <h3>今日重點</h3>
        <p className="muted">
          事件 / 告警 / AI 摘要 — 規劃中。AI 會嵌入各頁，AI 研究頁集中管理對話 threads。
        </p>
      </aside>

      {openCardId != null && (
        <CardModal
          runId={openCardId}
          onClose={() => setOpenCardId(null)}
          onChanged={() => void load()}
        />
      )}
    </>
  );
}

function OvTile({ label, value, sub }: { label: string; value: number | string; sub: string }) {
  return (
    <div className="ov-tile">
      <div className="ov-label">{label}</div>
      <div className="ov-value">{value}</div>
      <div className="ov-sub muted tiny">{sub}</div>
    </div>
  );
}

// --- local presentation helpers (kept self-contained for this v0 shell) ---

function moverWeight(r: CockpitRow): number {
  return r.change_7d_pct == null ? -1 : Math.abs(r.change_7d_pct);
}
function fmtNum(v: number | null): string {
  return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function fmtPct(v: number | null): string {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function changeClass(v: number | null): string {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
function fmtDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime())
    ? s
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
