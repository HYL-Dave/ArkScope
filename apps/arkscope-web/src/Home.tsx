// Home / 工作台 — the workbench first-screen (vision PDF p13/p20).
//
// Replaces the old dev "Dashboard" (now demoted to System/Health) as the product
// home. v0 is deliberately bounded: an overview strip + the watchlist's top
// movers (reusing the cockpit DTO) + a Recent-AI-cards list. AI lives in the
// per-ticker detail (Watchlist → AI summary), surfaced back here as recent cards.

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getCards,
  getProfileLists,
  getUniverse,
  type CardSummary,
  type RuntimeConfig,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";
import { allActiveRows, customListNameSet } from "./watchlist-derive";
import type { StatusState } from "./Dashboard";
import { CardModal } from "./AICard";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";

type NavTarget = "Home" | "Watchlist" | "System";

export function HomeView({
  status,
  onNavigate,
  onOpenTicker,
  runtime,
  developerMode,
  onNavigateTarget,
}: {
  status: StatusState;
  onNavigate: (view: NavTarget) => void;
  onOpenTicker: (ticker: string) => void;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [active, setActive] = useState<UniverseRow[] | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [archivedCount, setArchivedCount] = useState(0);
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [openCardId, setOpenCardId] = useState<number | null>(null);
  const closeCard = useCallback(() => setOpenCardId(null), []);

  const load = useCallback(async () => {
    try {
      // Home mirrors 自選股: the All-Active set over custom work-lists (NOT the
      // old cockpit-17 overview), so the first screen and the watchlist agree.
      const [u, l, c] = await Promise.all([
        getUniverse(true),
        getProfileLists(false),
        getCards(undefined, 8),
      ]);
      setActive(allActiveRows(u.rows, l.lists)); // active members only (movers)
      // Archived custom-list members have no ACTIVE membership, so count them
      // from all_lists (else the "已封存" sub would always read 0).
      const names = customListNameSet(l.lists);
      setArchivedCount(
        u.rows.filter((r) => r.archived && r.all_lists.some((n) => names.has(n))).length,
      );
      setAsOf(u.as_of);
      setCards(c.cards);
      setErr(null);
    } catch (e) {
      setErr(captureExploreError("home_load_workspace", e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dsCount = status.kind === "ready" ? Object.keys(status.status.data_sources).length : null;
  const rows = (active ?? []).filter((r) => !r.archived);
  const movers = [...rows]
    .sort((a, b) => moverWeight(b) - moverWeight(a))
    .slice(0, 8);

  return (
    <>
      <main className="main">
        <div className="home">
          <section className="home-overview">
            <OvTile
              label={t(($) => $.home.watchlistLabel)}
              value={active ? rows.length : "—"}
              sub={active
                ? t(($) => $.home.rowArchiveSummary, {
                    count: rows.length + archivedCount,
                    archivedCount,
                  })
                : t(($) => $.home.loading)}
            />
            <OvTile
              label={t(($) => $.home.alertLabel)}
              value="—"
              sub={t(($) => $.home.unavailable)}
            />
            <OvTile
              label={t(($) => $.home.dataSource)}
              value={dsCount ?? "—"}
              sub={status.kind === "ready"
                ? t(($) => $.home.toolCount, { count: status.status.tools_registered })
                : "—"}
            />
            <OvTile
              label={t(($) => $.home.dataAsOf)}
              value={asOf ? fmtDate(asOf) : "—"}
              sub={t(($) => $.home.watchlistAsOf)}
            />
          </section>

          {err && (
            <ExploreErrorNotice
              state={err}
              developerMode={developerMode}
              retryLabel={t(($) => $.home.retry)}
              onRetry={() => void load()}
              onNavigate={onNavigateTarget}
            />
          )}

          <section className="home-block">
            <div className="home-block-head">
              <h2>
                {t(($) => $.home.watchlistActivity)}{" "}
                <span className="muted tiny">{t(($) => $.home.topMovers)}</span>
              </h2>
              <button className="btn-ghost" onClick={() => onNavigate("Watchlist")}>
                {t(($) => $.home.viewAll)}
              </button>
            </div>
            {active === null ? (
              <p className="muted">{t(($) => $.home.loading)}</p>
            ) : rows.length === 0 ? (
              <p className="muted">{t(($) => $.home.emptyWatchlist)}</p>
            ) : (
              <table className="home-table">
                <thead>
                  <tr>
                    <th>{t(($) => $.home.ticker)}</th>
                    <th className="num">{t(($) => $.home.close)}</th>
                    <th className="num">{t(($) => $.home.change7d)}</th>
                    <th className="num">{t(($) => $.home.news)}</th>
                    <th>{t(($) => $.home.priority)}</th>
                  </tr>
                </thead>
                <tbody>
                  {movers.map((r) => (
                    <tr key={r.ticker} className="clickrow" onClick={() => onOpenTicker(r.ticker)}>
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
              <h2>
                {t(($) => $.home.recentAiCards)}{" "}
                <span className="muted tiny">{t(($) => $.home.recentResearchCards)}</span>
              </h2>
              <button className="btn-ghost" onClick={() => onNavigate("Watchlist")}>
                {t(($) => $.home.generateInWatchlist)}
              </button>
            </div>
            {cards === null ? (
              <p className="muted">{t(($) => $.home.loading)}</p>
            ) : cards.length === 0 ? (
              <p className="muted">{t(($) => $.home.emptyCards)}</p>
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

      {openCardId != null && (
        <CardModal
          runId={openCardId}
          onClose={closeCard}
          onChanged={() => void load()}
          runtime={runtime}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
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

function moverWeight(r: UniverseRow): number {
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
