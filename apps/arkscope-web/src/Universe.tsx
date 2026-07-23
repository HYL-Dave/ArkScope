// Universe / 全部標的 — the full tracked-ticker inventory (distinct from the
// curated 自選股 watchlist). This is where you see EVERY tracked ticker, whether
// or not you're actively watching it: search, filter by your work-lists and by
// classification facets (Category / Theme / Provenance), see which have a market
// summary, and bootstrap classification tags from config. Daily research lives
// in 自選股; this is inventory.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getProfileLists,
  getUniverse,
  importUniverse,
  setTickerHidden,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  presentUniverseImportOutcome,
  type ExploreErrorState,
  type UniverseImportOutcome,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";
import { TAG_FACETS, TagChips, facetLabel } from "./tags";

type UniverseFeedback = UniverseImportOutcome | ExploreErrorState;

function isImportOutcome(value: UniverseFeedback): value is UniverseImportOutcome {
  return "kind" in value && value.kind === "universe_import_succeeded";
}

export function UniverseView({
  onOpenTicker,
  developerMode,
  onNavigateTarget,
}: {
  onOpenTicker: (ticker: string) => void;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [rows, setRows] = useState<UniverseRow[] | null>(null);
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [meta, setMeta] = useState<{ total: number; summarized: number; archived: number } | null>(null);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [query, setQuery] = useState("");
  const [listFilter, setListFilter] = useState<string>("__all__");
  const [tagFilters, setTagFilters] = useState<Record<string, string>>({}); // facet -> value ("" = all)
  const [importing, setImporting] = useState(false);
  const [busyTicker, setBusyTicker] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<UniverseFeedback | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [u, l] = await Promise.all([getUniverse(true), getProfileLists(false)]);
      setRows(u.rows);
      setLists(l.lists);
      setMeta({ total: u.total, summarized: u.summarized, archived: u.archived_count });
    } catch (e) {
      setErr(captureExploreError("universe_load", e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = useCallback(async () => {
    setFeedback(null);
    await load();
  }, [load]);

  async function runImport() {
    if (importing) return;
    setImporting(true);
    setFeedback(null);
    try {
      const r = await importUniverse({});
      setFeedback({
        kind: "universe_import_succeeded",
        tagsAdded: r.tags.tags_added,
        listsRemoved: r.lists_removed,
        groupsAvailable: r.groups_ok,
      });
      await load();
    } catch (e) {
      setFeedback(captureExploreError("universe_import", e));
    } finally {
      setImporting(false);
    }
  }

  async function removeFromUniverse(ticker: string) {
    if (busyTicker) return;
    // No restore UI (per the model decision), so confirm before suppressing.
    if (!window.confirm(t(($) => $.universe.hideConfirmation, { ticker }))) return;
    setFeedback(null);
    setBusyTicker(ticker);
    try {
      await setTickerHidden(ticker, true);
      await load();
    } catch (e) {
      setFeedback(captureExploreError("universe_hide_ticker", e));
    } finally {
      setBusyTicker(null);
    }
  }

  // List filter = the user's work-lists (custom), aligned with the 自選股 rail —
  // classification (tier/theme/etc.) lives in tag facets, not lists.
  const customListNames = useMemo(
    () => lists.filter((l) => l.kind === "custom").map((l) => l.name).sort(),
    [lists],
  );

  // Distinct tag values per facet, for the Category/Theme/Provenance dropdowns.
  // A facet with no values is hidden.
  const tagValues = useMemo(() => {
    const by: Record<string, Set<string>> = {};
    for (const f of TAG_FACETS) by[f.facet] = new Set();
    (rows ?? []).forEach((r) => (r.tags ?? []).forEach((t) => by[t.facet]?.add(t.value)));
    const out: Record<string, string[]> = {};
    for (const f of TAG_FACETS) out[f.facet] = [...by[f.facet]].sort();
    return out;
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    return (rows ?? []).filter((r) => {
      if (q && !r.ticker.toUpperCase().includes(q)) return false;
      if (listFilter !== "__all__" && !r.lists.includes(listFilter)) return false;
      // Facets are ANDed; within a facet the selected value must be present.
      for (const f of TAG_FACETS) {
        const sel = tagFilters[f.facet];
        if (sel && !(r.tags ?? []).some((t) => t.facet === f.facet && t.value === sel)) return false;
      }
      return true;
    });
  }, [rows, query, listFilter, tagFilters]);

  const activeTagFilters = useMemo(
    () => Object.values(tagFilters).filter(Boolean).length,
    [tagFilters],
  );
  const importPresentation = feedback && isImportOutcome(feedback)
    ? presentUniverseImportOutcome(feedback, t)
    : null;
  const feedbackError = feedback && !isImportOutcome(feedback) ? feedback : null;

  const errorNotice = (state: ExploreErrorState) => (
    <ExploreErrorNotice
      state={state}
      developerMode={developerMode}
      retryLabel={t(($) => $.universe.refresh)}
      onRetry={() => void refresh()}
      onNavigate={state.code === "active_universe_unavailable"
        ? onNavigateTarget
        : undefined}
    />
  );

  return (
    <main className="main">
      <div className="surface-head">
        <h2 className="surface-title">{t(($) => $.universe.title)}</h2>
        {meta && (
          <span className="muted">
            {t(($) => $.universe.summaryCounts, {
              total: meta.total,
              summarized: meta.summarized,
              withoutSummary: meta.total - meta.summarized,
            })}
            {meta.archived > 0 && (
              <> {t(($) => $.universe.archivedCount, { count: meta.archived })}</>
            )}
          </span>
        )}
        <span className="spacer" />
        <button className="btn-ghost" onClick={() => void runImport()} disabled={importing}>
          {importing
            ? t(($) => $.universe.importing)
            : t(($) => $.universe.importCategories)}
        </button>
        <button className="btn-ghost" onClick={() => void refresh()}>
          {t(($) => $.universe.refresh)}
        </button>
      </div>

      <p className="muted tiny universe-hint">
        {t(($) => $.universe.description)}
      </p>
      {importPresentation && (
        <p className="tiny universe-importmsg">
          {importPresentation.title}
          {importPresentation.warning ? (
            <>{" "}{importPresentation.warning}</>
          ) : null}
        </p>
      )}
      {feedbackError && errorNotice(feedbackError)}
      {err && errorNotice(err)}

      {rows && (
        <>
          <div className="universe-filters">
            <input
              className="aicard-q"
              placeholder={t(($) => $.universe.searchPlaceholder)}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              className="universe-select"
              value={listFilter}
              onChange={(e) => setListFilter(e.target.value)}
            >
              <option value="__all__">
                {t(($) => $.universe.allListsCount, { count: customListNames.length })}
              </option>
              {customListNames.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            {TAG_FACETS.map((facet) => {
              const f = { ...facet, label: facetLabel(facet.facet, t) };
              return tagValues[f.facet].length > 0 ? (
                <select
                  key={f.facet}
                  className="universe-select"
                  value={tagFilters[f.facet] ?? ""}
                  onChange={(e) => setTagFilters((prev) => ({ ...prev, [f.facet]: e.target.value }))}
                  title={t(($) => $.universe.filterBy, { label: f.label })}
                >
                  <option value="">{f.label}{t(($) => $.universe.all)}</option>
                  {tagValues[f.facet].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              ) : null;
            })}
            {activeTagFilters > 0 && (
              <button
                className="btn-ghost tiny"
                onClick={() => setTagFilters({})}
                title={t(($) => $.universe.clearFacetFilters)}
              >
                {t(($) => $.universe.clearCategory)}
              </button>
            )}
            <span className="muted tiny">{filtered.length} / {rows.length}</span>
          </div>

          <table className="wl universe-table">
            <thead>
              <tr>
                <th>{t(($) => $.universe.ticker)}</th>
                <th className="num">{t(($) => $.universe.close)}</th>
                <th className="num">{t(($) => $.universe.change7d)}</th>
                <th className="num">{t(($) => $.universe.news)}</th>
                <th>{t(($) => $.universe.lists)}</th>
                <th>{t(($) => $.universe.tags)}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.ticker}
                  className={`clickrow ${r.has_summary ? "" : "no-summary"} ${r.archived ? "archived" : ""}`}
                  onClick={() => onOpenTicker(r.ticker)}
                >
                  <td className="mono strong">
                    {r.ticker}
                    {!r.has_summary && (
                      <span className="tag-nosum" title={t(($) => $.universe.noMarketSummary)}>
                        {t(($) => $.universe.noSummary)}
                      </span>
                    )}
                    {r.archived && (
                      <span className="tag-archived">{t(($) => $.universe.archived)}</span>
                    )}
                    {r.note_count > 0 && (
                      <span
                        className="note-dot"
                        title={t(($) => $.universe.noteCount, { count: r.note_count })}
                      >
                        ✎{r.note_count}
                      </span>
                    )}
                  </td>
                  <td className="num">{r.has_summary ? fmtNum(r.latest_close) : "—"}</td>
                  <td className={`num ${changeClass(r.change_7d_pct)}`}>
                    {r.has_summary ? fmtPct(r.change_7d_pct) : "—"}
                  </td>
                  <td className="num">{r.has_summary ? r.news_count_7d : "—"}</td>
                  <td>
                    <span className="chips">
                      {r.lists.slice(0, 4).map((l) => (
                        <span key={l} className="list-chip">{l}</span>
                      ))}
                      {r.lists.length > 4 && <span className="muted tiny">+{r.lists.length - 4}</span>}
                    </span>
                  </td>
                  <td><TagChips tags={r.tags} t={t} /></td>
                  <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="rowx"
                      title={t(($) => $.universe.hideTicker)}
                      disabled={busyTicker === r.ticker}
                      onClick={() => void removeFromUniverse(r.ticker)}
                    >
                      {busyTicker === r.ticker ? "…" : "✕"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="muted tiny">
              {rows.length === 0
                ? t(($) => $.universe.emptyUniverse)
                : t(($) => $.universe.noMatches)}
            </p>
          )}
        </>
      )}
      {!rows && !err && <p className="muted">{t(($) => $.universe.loading)}</p>}
    </main>
  );
}

function fmtNum(v: number | null): string {
  return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function fmtPct(v: number | null): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function changeClass(v: number | null): string {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
