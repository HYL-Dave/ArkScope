// Universe / 全部標的 — the full tracked-ticker inventory (distinct from the
// curated cockpit watchlist). This is where you see EVERY ticker the system
// knows about, whether or not you're actively watching it: search, filter by
// list/tier/group, see which have a market summary, and import the universe
// from existing categories. Daily research lives in 自選股; this is inventory.

import { useCallback, useEffect, useMemo, useState } from "react";
import { getUniverse, importUniverse, type UniverseRow } from "./api";

export function UniverseView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [rows, setRows] = useState<UniverseRow[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; summarized: number; archived: number } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [listFilter, setListFilter] = useState<string>("__all__");
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const u = await getUniverse(true);
      setRows(u.rows);
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
      const r = await importUniverse({});
      setImportMsg(
        `匯入完成：新增 ${r.imported.lists_created} 個清單、${r.imported.memberships_added} 筆成員。`,
      );
      await load();
    } catch (e) {
      setImportMsg(`匯入失敗：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
    }
  }

  // List filter options = union of all list names across the universe.
  const allLists = useMemo(() => {
    const s = new Set<string>();
    (rows ?? []).forEach((r) => r.lists.forEach((l) => s.add(l)));
    return [...s].sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase();
    return (rows ?? []).filter((r) => {
      if (q && !r.ticker.toUpperCase().includes(q)) return false;
      if (listFilter !== "__all__" && !r.lists.includes(listFilter)) return false;
      return true;
    });
  }, [rows, query, listFilter]);

  return (
    <main className="main">
      <div className="surface-head">
        <h2 className="surface-title">全部標的 · Universe</h2>
        {meta && (
          <span className="muted">
            {meta.total} 檔 · {meta.summarized} 有摘要 · {meta.total - meta.summarized} 僅在宇宙
            {meta.archived > 0 && ` · ${meta.archived} 已封存`}
          </span>
        )}
        <span className="spacer" />
        <button className="btn-ghost" onClick={() => void runImport()} disabled={importing}>
          {importing ? "匯入中…" : "⤓ 匯入清單"}
        </button>
        <button className="btn-ghost" onClick={() => void load()}>↻ Refresh</button>
      </div>

      <p className="muted tiny universe-hint">
        從 user_profile groups 和 tickers_core tiers 匯入清單；可重複執行，不會恢復已 archive 的項目。
        「全部標的」管理系統知道哪些 ticker；日常研究清單在「自選股」。
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
              <option value="__all__">所有清單（{allLists.length}）</option>
              {allLists.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
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
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="muted tiny">
              {rows.length === 0 ? "宇宙是空的。按「匯入清單」從現有分類種入標的。" : "沒有符合的標的。"}
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
