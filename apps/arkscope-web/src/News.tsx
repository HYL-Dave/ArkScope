// 新聞·事件 surface — score-free browse/search over the LOCAL news corpus.
// Two sources, switched at the top of the toolbar:
//   • 市場新聞  — market providers via /news/feed (FTS5 tokenized-AND).
//   • Seeking Alpha — SA analysis articles + market-news via /sa/feed (local
//     sa_capture.db). Score-free. Read-only: no provider fetches.
// (Layer C-1: SA is a source/filter inside this surface, not a new page.)

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getNewsFeed, type NewsContentFilter, type NewsFeedItem, type NewsFeedResponse,
  getSAFeed, type SAFeedItem, type SAFeedResponse,
} from "./api";

const PAGE = 50;
const DAY_OPTIONS = [7, 30, 90, 365] as const;
const SOURCE_OPTIONS = ["auto", "polygon", "finnhub", "ibkr"] as const;
const SA_TYPE_OPTIONS = [
  { v: "", label: "全部類型" },
  { v: "article", label: "分析文章" },
  { v: "market_news", label: "市場新聞" },
] as const;

type Mode = "market" | "sa";

export function NewsView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [mode, setMode] = useState<Mode>("market");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [tickerInput, setTickerInput] = useState(""); // typed value
  const [ticker, setTicker] = useState("");           // applied filter (on Enter)
  const [source, setSource] = useState<string>("auto"); // market providers
  const [content, setContent] = useState<NewsContentFilter>("all");
  const [saType, setSaType] = useState<string>("");      // SA item_type
  const [days, setDays] = useState<number>(7);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [feed, setFeed] = useState<NewsFeedResponse | null>(null);
  const [items, setItems] = useState<NewsFeedItem[]>([]);
  const [saFeed, setSaFeed] = useState<SAFeedResponse | null>(null);
  const [saItems, setSaItems] = useState<SAFeedItem[]>([]);

  // Monotonic request token: rapid source/ticker/days/load-more changes fire
  // overlapping requests; only the latest may commit state, so a slow older
  // response can never overwrite a newer feed/items/offset/loading.
  const reqRef = useRef(0);
  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      const myReq = ++reqRef.current;
      setLoading(true);
      setErr(null);
      try {
        const tk = ticker || undefined; // already trimmed+uppercased on apply
        if (mode === "sa") {
          const f = await getSAFeed({
            q: q || undefined, ticker: tk, item_type: saType || undefined,
            days, limit: PAGE, offset: nextOffset,
          });
          if (myReq !== reqRef.current) return; // stale → drop
          setSaFeed(f);
          setSaItems((prev) => (append ? [...prev, ...f.items] : f.items));
        } else {
          const f = await getNewsFeed({
            q: q || undefined,
            ticker: tk,
            source,
            content,
            days,
            limit: PAGE,
            offset: nextOffset,
          });
          if (myReq !== reqRef.current) return; // stale → drop
          if (!f.content_counts || (content === "unknown" && f.content_counts.unknown <= 0)) {
            setContent("all");
          }
          setFeed(f);
          setItems((prev) => (append ? [...prev, ...f.items] : f.items));
        }
        setOffset(nextOffset);
      } catch (e) {
        if (myReq !== reqRef.current) return;
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (myReq === reqRef.current) setLoading(false);
      }
    },
    [mode, q, ticker, source, content, saType, days],
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  return (
    <main className="main">
      <div className="surface-head">
        <h1 className="surface-title">新聞·事件</h1>
        <span className="muted tiny">
          {mode === "sa"
            ? "Seeking Alpha 文章＋市場新聞（本地 sa_capture.db）"
            : "本地新聞庫（score-free）· 搜尋為字詞 AND"}
        </span>
      </div>

      <div className="news-toolbar">
        <select value={mode} onChange={(e) => setMode(e.target.value as Mode)} title="來源">
          <option value="market">市場新聞</option>
          <option value="sa">Seeking Alpha</option>
        </select>
        <input
          className="news-search"
          placeholder="搜尋標題／摘要（Enter）"
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setQ(qInput.trim()); }}
        />
        <input
          className="news-ticker"
          placeholder="Ticker（Enter）"
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setTicker(tickerInput.trim().toUpperCase()); }}
        />
        {mode === "sa" ? (
          <select value={saType} onChange={(e) => setSaType(e.target.value)} title="SA 類型">
            {SA_TYPE_OPTIONS.map((t) => (
              <option key={t.v} value={t.v}>{t.label}</option>
            ))}
          </select>
        ) : (
          <select value={source} onChange={(e) => setSource(e.target.value)} title="來源">
            {SOURCE_OPTIONS.map((s) => (
              <option key={s} value={s}>{s === "auto" ? "全部來源" : s}</option>
            ))}
          </select>
        )}
        {mode === "market" && feed?.content_counts && (
          <select
            value={content}
            onChange={(e) => setContent(e.target.value as NewsContentFilter)}
            title="內文狀態"
          >
            <option value="all">
              全部 ({Object.values(feed.content_counts).reduce((sum, count) => sum + count, 0)})
            </option>
            <option value="full">有內文 ({feed.content_counts.full})</option>
            <option value="headline_only">
              僅標題 ({feed.content_counts.headline_only})
            </option>
            {feed.content_counts.unknown > 0 && (
              <option value="unknown">狀態不明 ({feed.content_counts.unknown})</option>
            )}
          </select>
        )}
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

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {mode === "sa" ? (
        <SAFeedBody
          feed={saFeed} items={saItems} q={q} loading={loading} offset={offset}
          onMore={() => void load(offset + PAGE, true)} onOpenTicker={onOpenTicker}
        />
      ) : (
        <MarketFeedBody
          feed={feed} items={items} q={q} loading={loading} offset={offset}
          onMore={() => void load(offset + PAGE, true)} onOpenTicker={onOpenTicker}
        />
      )}
    </main>
  );
}

// --- market providers feed (unchanged behaviour) ---------------------------
function MarketFeedBody({
  feed, items, q, loading, onMore, onOpenTicker,
}: {
  feed: NewsFeedResponse | null;
  items: NewsFeedItem[];
  q: string;
  loading: boolean;
  offset: number;
  onMore: () => void;
  onOpenTicker: (t: string) => void;
}) {
  // Browse (chronological) groups by date; search results are relevance-ordered
  // (dates interleave) → one flat list.
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
  const showContentLabels = Boolean(feed?.content_counts);

  return (
    <>
      {feed && (
        <p className="muted tiny news-stats">
          共 {feed.total.toLocaleString()} 篇
          {Object.entries(feed.sources).map(([s, n]) => (
            <span key={s}> · {s} {n.toLocaleString()}</span>
          ))}
          {q && <span> · 搜尋「{q}」（按相關性排序，標題加權）</span>}
        </p>
      )}
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
                    {q ? it.published_at.slice(5, 16).replace("T", " ") : it.published_at.slice(11, 16)}
                  </span>
                  <button className="news-ticker-chip" onClick={() => onOpenTicker(it.ticker)} title={`開啟 ${it.ticker}`}>
                    {it.ticker}
                  </button>
                  {showContentLabels && contentLabel(it) && (
                    <span className="list-chip">{contentLabel(it)}</span>
                  )}
                  {it.url ? (
                    <a className="news-title" href={it.url} target="_blank" rel="noreferrer">{it.title}</a>
                  ) : (
                    <span className="news-title">{it.title}</span>
                  )}
                  <span className="muted tiny news-meta">
                    {it.publisher ? `${it.publisher} · ` : ""}{it.source}
                  </span>
                </div>
                {it.description && <div className="news-desc muted tiny">{it.description}</div>}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {loading && <p className="muted tiny">loading…</p>}
      {feed && items.length < feed.total && !loading && (
        <button className="btn-ghost" style={{ marginTop: 10 }} onClick={onMore}>
          載入更多（{items.length}/{feed.total.toLocaleString()}）
        </button>
      )}
      {feed && feed.available && feed.total === 0 && !loading && (
        <p className="muted">此條件下沒有文章。</p>
      )}
    </>
  );
}

function contentLabel(item: NewsFeedItem): string | null {
  if (item.content_availability === "unknown") return "內文狀態不明";
  if (item.content_availability !== "headline_only") return null;
  if (item.content_recovery === "retryable") return "僅標題 · 內文待處理";
  if (item.content_recovery === "terminal") return "僅標題 · 來源未提供內文";
  return null;
}

// --- Seeking Alpha evidence feed (Layer C-1) -------------------------------
function SAFeedBody({
  feed, items, q, loading, onMore, onOpenTicker,
}: {
  feed: SAFeedResponse | null;
  items: SAFeedItem[];
  q: string;
  loading: boolean;
  offset: number;
  onMore: () => void;
  onOpenTicker: (t: string) => void;
}) {
  const typeLabel = (t: string) => (t === "article" ? "分析文章" : "市場新聞");
  // available=false is a DEGRADED state (e.g. SA not local-first), not an error.
  const degraded =
    feed && !feed.available
      ? feed.empty_reason === "requires_local_sa"
        ? "Seeking Alpha 本地資料路徑尚未就緒。"
        : "Seeking Alpha 資料尚未就緒。"
      : null;

  return (
    <>
      {feed && (
        <p className="muted tiny news-stats">
          共 {feed.total.toLocaleString()} 筆
          {Object.entries(feed.by_type).map(([t, n]) => (
            <span key={t}> · {typeLabel(t)} {n.toLocaleString()}</span>
          ))}
          {q && <span> · 搜尋「{q}」</span>}
        </p>
      )}
      {degraded && <p className="muted">{degraded}</p>}

      <ul className="news-list">
        {items.map((it, i) => (
          <li key={`${it.type}-${it.id}-${i}`} className="news-item">
            <div className="news-row">
              <span className="muted mono tiny news-time">
                {it.published_at.slice(5, 16).replace("T", " ")}
              </span>
              <span className="list-chip">{typeLabel(it.type)}</span>
              {it.tickers.map((t) => (
                <button key={t} className="news-ticker-chip" onClick={() => onOpenTicker(t)} title={`開啟 ${t}`}>
                  {t}
                </button>
              ))}
              {it.url ? (
                <a className="news-title" href={it.url} target="_blank" rel="noreferrer">{it.title}</a>
              ) : (
                <span className="news-title">{it.title}</span>
              )}
              <span className="muted tiny news-meta">
                SA{it.comments_count > 0 ? ` · 💬 ${it.comments_count.toLocaleString()}` : ""}
                {it.url ? " · 原文 ↗" : ""}
              </span>
            </div>
            {/* snippet is server-cleaned plain text (src/text_snippet.py) — render as
                text only; do NOT add a markdown/HTML renderer here. */}
            {it.snippet && <div className="news-desc muted tiny">{it.snippet}</div>}
          </li>
        ))}
      </ul>

      {loading && <p className="muted tiny">loading…</p>}
      {feed && items.length < feed.total && !loading && (
        <button className="btn-ghost" style={{ marginTop: 10 }} onClick={onMore}>
          載入更多（{items.length}/{feed.total.toLocaleString()}）
        </button>
      )}
      {feed && feed.available && feed.total === 0 && !loading && (
        <p className="muted">此條件下沒有 Seeking Alpha 內容。</p>
      )}
    </>
  );
}
