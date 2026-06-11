// 新聞·事件 surface — score-free browse/search over the LOCAL news corpus
// (FTS5 tokenized-AND; PG only serves pre-3b DBs). Read-only: no provider
// fetches — freshness comes from the Data Sources scheduler.

import { useCallback, useEffect, useState } from "react";
import { getNewsFeed, type NewsFeedItem, type NewsFeedResponse } from "./api";

const PAGE = 50;
const DAY_OPTIONS = [7, 30, 90, 365] as const;
const SOURCE_OPTIONS = ["auto", "polygon", "finnhub", "ibkr"] as const;

export function NewsView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [ticker, setTicker] = useState("");
  const [source, setSource] = useState<string>("auto");
  const [days, setDays] = useState<number>(7);
  const [feed, setFeed] = useState<NewsFeedResponse | null>(null);
  const [items, setItems] = useState<NewsFeedItem[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setLoading(true);
      setErr(null);
      try {
        const f = await getNewsFeed({
          q: q || undefined,
          ticker: ticker.trim().toUpperCase() || undefined,
          source,
          days,
          limit: PAGE,
          offset: nextOffset,
        });
        setFeed(f);
        setItems((prev) => (append ? [...prev, ...f.items] : f.items));
        setOffset(nextOffset);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [q, ticker, source, days],
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  // Browse (chronological) → group by date for date headers. Search results are
  // RELEVANCE-ordered — dates interleave, so render one flat list with the date
  // inline instead of fragmented repeating headers.
  const groups: Array<{ date: string; rows: NewsFeedItem[] }> = [];
  if (q) {
    groups.push({ date: "", rows: items });
  } else {
    for (const it of items) {
      const d = it.published_at.slice(0, 10);
      const last = groups[groups.length - 1];
      if (last && last.date === d) last.rows.push(it);
      else groups.push({ date: d, rows: [it] });
    }
  }

  return (
    <main className="main">
      <div className="surface-head">
        <h1 className="surface-title">新聞·事件</h1>
        <span className="muted tiny">
          本地新聞庫（score-free）· 搜尋為字詞 AND
        </span>
      </div>

      <div className="news-toolbar">
        <input
          className="news-search"
          placeholder="搜尋標題／摘要（Enter）"
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setQ(qInput.trim());
          }}
        />
        <input
          className="news-ticker"
          placeholder="Ticker"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void load(0, false);
          }}
        />
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          {SOURCE_OPTIONS.map((s) => (
            <option key={s} value={s}>{s === "auto" ? "全部來源" : s}</option>
          ))}
        </select>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {DAY_OPTIONS.map((d) => (
            <option key={d} value={d}>{d} 天</option>
          ))}
        </select>
        {q && (
          <button className="btn-ghost" onClick={() => { setQ(""); setQInput(""); }}>
            ✕ 清除搜尋
          </button>
        )}
      </div>

      {feed && (
        <p className="muted tiny news-stats">
          共 {feed.total.toLocaleString()} 篇
          {Object.entries(feed.sources).map(([s, n]) => (
            <span key={s}> · {s} {n.toLocaleString()}</span>
          ))}
          {q && <span> · 搜尋「{q}」（按相關性排序，標題加權）</span>}
        </p>
      )}
      {err && <div className="errorbox"><p className="muted">{err}</p></div>}
      {feed && !feed.available && (
        <p className="muted">本地新聞庫尚未建立 — 到 Settings → Data Storage 建立本地市場庫。</p>
      )}

      {groups.map((g) => (
        <section key={g.date || "search"}>
          {g.date && <h4 className="detail-section">{g.date}</h4>}
          <ul className="news-list">
            {g.rows.map((it, i) => (
              <li key={`${it.url ?? it.title}-${i}`} className="news-item">
                <div className="news-row">
                  <span className="muted mono tiny news-time">
                    {q
                      ? it.published_at.slice(5, 16).replace("T", " ")
                      : it.published_at.slice(11, 16)}
                  </span>
                  <button
                    className="news-ticker-chip"
                    onClick={() => onOpenTicker(it.ticker)}
                    title={`開啟 ${it.ticker}`}
                  >
                    {it.ticker}
                  </button>
                  {it.url ? (
                    <a className="news-title" href={it.url} target="_blank" rel="noreferrer">
                      {it.title}
                    </a>
                  ) : (
                    <span className="news-title">{it.title}</span>
                  )}
                  <span className="muted tiny news-meta">
                    {it.publisher ? `${it.publisher} · ` : ""}{it.source}
                  </span>
                </div>
                {it.description && (
                  <div className="news-desc muted tiny">{it.description}</div>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {loading && <p className="muted tiny">loading…</p>}
      {feed && items.length < feed.total && !loading && (
        <button className="btn-ghost" style={{ marginTop: 10 }}
          onClick={() => void load(offset + PAGE, true)}>
          載入更多（{items.length}/{feed.total.toLocaleString()}）
        </button>
      )}
      {feed && feed.available && feed.total === 0 && !loading && (
        <p className="muted">此條件下沒有文章。</p>
      )}
    </main>
  );
}
