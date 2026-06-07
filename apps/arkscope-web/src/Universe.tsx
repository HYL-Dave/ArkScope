// Universe / 全部標的 — the full tracked-ticker inventory (distinct from the
// curated 自選股 watchlist). This is where you see EVERY tracked ticker, whether
// or not you're actively watching it: search, filter by your work-lists and by
// classification facets (Category / Theme / Provenance), see which have a market
// summary, and bootstrap classification tags from config. Daily research lives
// in 自選股; this is inventory.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getProfileLists,
  getUniverse,
  importUniverse,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";
import { TAG_FACETS, TagChips } from "./tags";

export function UniverseView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [rows, setRows] = useState<UniverseRow[] | null>(null);
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [meta, setMeta] = useState<{ total: number; summarized: number; archived: number } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [listFilter, setListFilter] = useState<string>("__all__");
  const [tagFilters, setTagFilters] = useState<Record<string, string>>({}); // facet -> value ("" = all)
  const [importing, setImporting] = useState(false);
  const [migratePriority, setMigratePriority] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [u, l] = await Promise.all([getUniverse(true), getProfileLists(false)]);
      setRows(u.rows);
      setLists(l.lists);
      setMeta({ total: u.total, summarized: u.summarized, archived: u.archived_count });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runImport() {
    if (importing) return;
    setImporting(true);
    setImportMsg(null);
    try {
      const r = await importUniverse({ migrate_tier_priority: migratePriority });
      const bits = [`新增 ${r.tags.tags_added} 個分類標籤`];
      if (r.lists_removed > 0) bits.push(`移除 ${r.lists_removed} 個舊清單`);
      if (r.priority_migrated > 0) bits.push(`初始化 ${r.priority_migrated} 檔 priority`);
      let msg = `匯入完成：${bits.join("、")}。`;
      if (!r.groups_ok) msg += " ⚠ 主題來源暫時無法連線，已略過 theme 標籤。";
      setImportMsg(msg);
      await load();
    } catch (e) {
      setImportMsg(`匯入失敗：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
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

  return (
    <main className="main">
      <div className="surface-head">
        <h2 className="surface-title">全部標的 · Universe</h2>
        {meta && (
          <span className="muted">
            {meta.total} 檔 · {meta.summarized} 有摘要 · {meta.total - meta.summarized} 無摘要
            {meta.archived > 0 && ` · ${meta.archived} 已封存`}
          </span>
        )}
        <span className="spacer" />
        <label className="muted tiny universe-migrate" title="用舊 tier 當作 priority 初始值（只填尚未設定的，不覆蓋）">
          <input
            type="checkbox"
            checked={migratePriority}
            onChange={(e) => setMigratePriority(e.target.checked)}
          />
          以舊 tier 初始化 priority
        </label>
        <button className="btn-ghost" onClick={() => void runImport()} disabled={importing}>
          {importing ? "匯入中…" : "⤓ 匯入分類"}
        </button>
        <button className="btn-ghost" onClick={() => void load()}>↻ Refresh</button>
      </div>

      <p className="muted tiny universe-hint">
        庫存來自 active universe 設定（不受清單增減影響）。「匯入分類」會從 config 種入分類標籤
        （category / theme / 來源），並移除舊的 config 清單；可重複執行，使用者自訂的標籤不會被覆蓋。
        分類用標籤管理，清單只放你的工作清單（與「自選股」同一組）。
      </p>
      {importMsg && <p className="tiny universe-importmsg">{importMsg}</p>}
      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {rows && (
        <>
          <div className="universe-filters">
            <input
              className="aicard-q"
              placeholder="搜尋 ticker…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              className="universe-select"
              value={listFilter}
              onChange={(e) => setListFilter(e.target.value)}
            >
              <option value="__all__">所有清單（{customListNames.length}）</option>
              {customListNames.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
            {TAG_FACETS.map((f) =>
              tagValues[f.facet].length > 0 ? (
                <select
                  key={f.facet}
                  className="universe-select"
                  value={tagFilters[f.facet] ?? ""}
                  onChange={(e) => setTagFilters((prev) => ({ ...prev, [f.facet]: e.target.value }))}
                  title={`依 ${f.label} 篩選`}
                >
                  <option value="">{f.label}（全部）</option>
                  {tagValues[f.facet].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              ) : null,
            )}
            {activeTagFilters > 0 && (
              <button className="btn-ghost tiny" onClick={() => setTagFilters({})} title="清除分類篩選">
                清除分類 ✕
              </button>
            )}
            <span className="muted tiny">{filtered.length} / {rows.length}</span>
          </div>

          <table className="wl universe-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th className="num">Close</th>
                <th className="num">7d %</th>
                <th className="num">News</th>
                <th>Lists</th>
                <th>Tags</th>
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
                    {!r.has_summary && <span className="tag-nosum" title="尚無市場摘要">無摘要</span>}
                    {r.archived && <span className="tag-archived">archived</span>}
                    {r.note_count > 0 && <span className="note-dot" title={`${r.note_count} note(s)`}>✎{r.note_count}</span>}
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
                  <td><TagChips tags={r.tags} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="muted tiny">
              {rows.length === 0 ? "尚無標的。按「匯入分類」從現有設定種入。" : "沒有符合的標的。"}
            </p>
          )}
        </>
      )}
      {!rows && !err && <p className="muted">載入中…</p>}
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
