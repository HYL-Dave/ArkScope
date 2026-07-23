// 新聞·事件 surface — score-free browse/search over the LOCAL news corpus.
// Two sources, switched at the top of the toolbar:
//   • 市場新聞  — market providers via /news/feed (FTS5 tokenized-AND).
//   • Seeking Alpha — SA analysis articles + market-news via /sa/feed (local
//     sa_capture.db). Score-free. Read-only: no provider fetches.
// (Layer C-1: SA is a source/filter inside this surface, not a new page.)

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getNewsFeed, type NewsContentFilter, type NewsFeedItem, type NewsFeedResponse,
  getSAFeed, type SAFeedItem, type SAFeedResponse,
} from "./api";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
  type ExploreT,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";

const PAGE = 50;
const DAY_OPTIONS = [7, 30, 90, 365] as const;
const SOURCE_OPTIONS = ["auto", "polygon", "finnhub", "ibkr"] as const;
const SA_TYPE_OPTIONS = ["", "article", "market_news"] as const;

const NEWS_STORAGE_TARGET = {
  kind: "settings_section",
  section: "news_storage",
} as const satisfies NavigationTarget;

const DATA_SOURCES_TARGET = {
  kind: "settings_section",
  section: "data_sources",
} as const satisfies NavigationTarget;

type Mode = "market" | "sa";

export function NewsView({
  onOpenTicker,
  developerMode,
  onNavigateTarget,
}: {
  onOpenTicker: (ticker: string) => void;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
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
  const [err, setErr] = useState<ExploreErrorState | null>(null);

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
      const operation = append
        ? "news_load_more"
        : mode === "sa"
          ? "news_load_seeking_alpha"
          : "news_load_market";
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
        setErr(captureExploreError(operation, e));
      } finally {
        if (myReq === reqRef.current) setLoading(false);
      }
    },
    [mode, q, ticker, source, content, saType, days],
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  const retryFailedLoad = () => {
    if (!err) return;
    if (err.operation === "news_load_more") {
      void load(offset + PAGE, true);
      return;
    }
    void load(0, false);
  };

  return (
    <main className="main">
      <div className="surface-head">
        <h1 className="surface-title">{t(($) => $.news.title)}</h1>
        <span className="muted tiny">
          {mode === "sa"
            ? t(($) => $.news.seekingAlphaDescription)
            : t(($) => $.news.marketDescription)}
        </span>
      </div>

      <div className="news-toolbar">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as Mode)}
          title={t(($) => $.news.sourceLabel)}
        >
          <option value="market">{t(($) => $.news.marketNewsTitle)}</option>
          <option value="sa">{t(($) => $.news.seekingAlpha)}</option>
        </select>
        <input
          className="news-search"
          placeholder={t(($) => $.news.searchLabel)}
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setQ(qInput.trim()); }}
        />
        <input
          className="news-ticker"
          placeholder={t(($) => $.news.tickerInputLabel)}
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setTicker(tickerInput.trim().toUpperCase()); }}
        />
        {mode === "sa" ? (
          <select
            value={saType}
            onChange={(e) => setSaType(e.target.value)}
            title={t(($) => $.news.saTypeLabel)}
          >
            {SA_TYPE_OPTIONS.map((type) => (
              <option key={type} value={type}>{saFilterTypeLabel(type, t)}</option>
            ))}
          </select>
        ) : (
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            title={t(($) => $.news.sourceLabel)}
          >
            {SOURCE_OPTIONS.map((sourceOption) => (
              <option key={sourceOption} value={sourceOption}>
                {sourceOption === "auto" ? t(($) => $.news.allSources) : sourceOption}
              </option>
            ))}
          </select>
        )}
        {mode === "market" && feed?.content_counts && (
          <select
            value={content}
            onChange={(e) => setContent(e.target.value as NewsContentFilter)}
            title={t(($) => $.news.contentStateLabel)}
          >
            <option value="all">
              {t(($) => $.news.allCount)}
              {Object.values(feed.content_counts).reduce((sum, count) => sum + count, 0)})
            </option>
            <option value="full">
              {t(($) => $.news.withContentCount)}{feed.content_counts.full})
            </option>
            <option value="headline_only">
              {t(($) => $.news.titleOnlyCount)}{feed.content_counts.headline_only})
            </option>
            {feed.content_counts.unknown > 0 && (
              <option value="unknown">
                {t(($) => $.news.unknownCount)}{feed.content_counts.unknown})
              </option>
            )}
          </select>
        )}
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {DAY_OPTIONS.map((dayOption) => (
            <option key={dayOption} value={dayOption}>
              {dayOption} {t(($) => $.news.daysSuffix)}
            </option>
          ))}
        </select>
        {q && (
          <button className="btn-ghost" onClick={() => { setQ(""); setQInput(""); }}>
            {t(($) => $.news.clearSearch)}
          </button>
        )}
      </div>

      {err && (
        <ExploreErrorNotice
          state={err}
          developerMode={developerMode}
          retryLabel={t(($) => $.home.retry)}
          onRetry={retryFailedLoad}
          onNavigate={mode === "sa" && err.code === "sa_extension_health_unavailable"
            ? onNavigateTarget
            : undefined}
        />
      )}

      {mode === "sa" ? (
        <SAFeedBody
          feed={saFeed}
          items={saItems}
          q={q}
          loading={loading}
          onMore={() => void load(offset + PAGE, true)}
          onOpenTicker={onOpenTicker}
          onNavigateTarget={onNavigateTarget}
          t={t}
        />
      ) : (
        <MarketFeedBody
          feed={feed}
          items={items}
          q={q}
          loading={loading}
          onMore={() => void load(offset + PAGE, true)}
          onOpenTicker={onOpenTicker}
          onNavigateTarget={onNavigateTarget}
          t={t}
        />
      )}
    </main>
  );
}

// --- market providers feed (unchanged behaviour) ---------------------------
function MarketFeedBody({
  feed, items, q, loading, onMore, onOpenTicker, onNavigateTarget, t,
}: {
  feed: NewsFeedResponse | null;
  items: NewsFeedItem[];
  q: string;
  loading: boolean;
  onMore: () => void;
  onOpenTicker: (ticker: string) => void;
  onNavigateTarget: (target: NavigationTarget) => void;
  t: ExploreT;
}) {
  // Browse (chronological) groups by date; search results are relevance-ordered
  // (dates interleave) → one flat list.
  const groups: Array<{ date: string; rows: NewsFeedItem[] }> = [];
  if (q) {
    groups.push({ date: "", rows: items });
  } else {
    for (const item of items) {
      const date = item.published_at.slice(0, 10);
      const last = groups[groups.length - 1];
      if (last && last.date === date) last.rows.push(item);
      else groups.push({ date, rows: [item] });
    }
  }
  const showContentLabels = Boolean(feed?.content_counts);

  return (
    <>
      {feed && (
        <p className="muted tiny news-stats">
          {t(($) => $.news.totalPrefix)} {feed.total.toLocaleString()} {t(($) => $.news.articlesSuffix)}
          {Object.entries(feed.sources).map(([source, count]) => (
            <span key={source}> · {source} {count.toLocaleString()}</span>
          ))}
          {q && (
            <span> {t(($) => $.news.marketSearchSummary, { query: q })}</span>
          )}
        </p>
      )}
      {feed && !feed.available && (
        <>
          <p className="muted">{t(($) => $.news.localStoreMissing)}</p>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => onNavigateTarget(NEWS_STORAGE_TARGET)}
          >
            {t(($) => $.errors.recovery.newsStorage)}
          </button>
        </>
      )}

      {groups.map((group) => (
        <section key={group.date || "search"}>
          {group.date && <h4 className="detail-section">{group.date}</h4>}
          <ul className="news-list">
            {group.rows.map((item, index) => {
              const availabilityLabel = showContentLabels ? contentLabel(item, t) : null;
              return (
                <li key={`${item.url ?? item.title}-${index}`} className="news-item">
                  <div className="news-row">
                    <span className="muted mono tiny news-time">
                      {q
                        ? item.published_at.slice(5, 16).replace("T", " ")
                        : item.published_at.slice(11, 16)}
                    </span>
                    <button
                      className="news-ticker-chip"
                      onClick={() => onOpenTicker(item.ticker)}
                      title={t(($) => $.news.openTicker, { ticker: item.ticker })}
                    >
                      {item.ticker}
                    </button>
                    {availabilityLabel && <span className="list-chip">{availabilityLabel}</span>}
                    {item.url ? (
                      <a className="news-title" href={item.url} target="_blank" rel="noreferrer">
                        {item.title}
                      </a>
                    ) : (
                      <span className="news-title">{item.title}</span>
                    )}
                    <span className="muted tiny news-meta">
                      {item.publisher ? (
                        <>{t(($) => $.news.publisher, { publisher: item.publisher })} </>
                      ) : null}
                      {item.source}
                    </span>
                  </div>
                  {item.description && <div className="news-desc muted tiny">{item.description}</div>}
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {loading && <p className="muted tiny">{t(($) => $.news.loadingLower)}</p>}
      {feed && items.length < feed.total && !loading && (
        <button className="btn-ghost" style={{ marginTop: 10 }} onClick={onMore}>
          {t(($) => $.news.loadMoreProgress, {
            visible: items.length,
            total: feed.total.toLocaleString(),
          })}
        </button>
      )}
      {feed && feed.available && feed.total === 0 && !loading && (
        <p className="muted">{t(($) => $.news.emptyArticles)}</p>
      )}
    </>
  );
}

function contentLabel(item: NewsFeedItem, t: ExploreT): string | null {
  if (item.content_availability === "unknown") return t(($) => $.news.contentUnknown);
  if (item.content_availability !== "headline_only") return null;
  if (item.content_recovery === "retryable") return t(($) => $.news.titleOnlyPending);
  if (item.content_recovery === "terminal") return t(($) => $.news.titleOnlyUnavailable);
  return null;
}

// --- Seeking Alpha evidence feed (Layer C-1) -------------------------------
function SAFeedBody({
  feed, items, q, loading, onMore, onOpenTicker, onNavigateTarget, t,
}: {
  feed: SAFeedResponse | null;
  items: SAFeedItem[];
  q: string;
  loading: boolean;
  onMore: () => void;
  onOpenTicker: (ticker: string) => void;
  onNavigateTarget: (target: NavigationTarget) => void;
  t: ExploreT;
}) {
  // available=false is a DEGRADED state (e.g. SA not local-first), not an error.
  const requiresLocalSa = Boolean(
    feed && !feed.available && feed.empty_reason === "requires_local_sa",
  );
  const degraded = feed && !feed.available
    ? requiresLocalSa
      ? t(($) => $.news.seekingAlphaPathUnavailable)
      : t(($) => $.news.seekingAlphaUnavailable)
    : null;

  return (
    <>
      {feed && (
        <p className="muted tiny news-stats">
          {t(($) => $.news.totalPrefix)} {feed.total.toLocaleString()} {t(($) => $.news.rowsSuffix)}
          {Object.entries(feed.by_type).map(([type, count]) => (
            <span key={type}> · {saRuntimeTypeLabel(type, t)} {count.toLocaleString()}</span>
          ))}
          {q && (
            <span> {t(($) => $.news.seekingAlphaSearchSummary, { query: q })}</span>
          )}
        </p>
      )}
      {degraded && (
        <>
          <p className="muted">{degraded}</p>
          {requiresLocalSa && (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => onNavigateTarget(DATA_SOURCES_TARGET)}
            >
              {t(($) => $.errors.recovery.dataSources)}
            </button>
          )}
        </>
      )}

      <ul className="news-list">
        {items.map((item, index) => (
          <li key={`${item.type}-${item.id}-${index}`} className="news-item">
            <div className="news-row">
              <span className="muted mono tiny news-time">
                {item.published_at.slice(5, 16).replace("T", " ")}
              </span>
              <span className="list-chip">{saRuntimeTypeLabel(item.type, t)}</span>
              {item.tickers.map((ticker) => (
                <button
                  key={ticker}
                  className="news-ticker-chip"
                  onClick={() => onOpenTicker(ticker)}
                  title={t(($) => $.news.openTickerChip, { ticker })}
                >
                  {ticker}
                </button>
              ))}
              {item.url ? (
                <a className="news-title" href={item.url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
              ) : (
                <span className="news-title">{item.title}</span>
              )}
              <span className="muted tiny news-meta">
                {t(($) => $.news.saShort)}
                {item.comments_count > 0 ? (
                  <> {t(($) => $.news.commentCount, {
                    count: item.comments_count,
                  })}</>
                ) : null}
                {item.url ? <> {t(($) => $.news.originalArticle)}</> : null}
              </span>
            </div>
            {/* snippet is server-cleaned plain text (src/text_snippet.py) — render as
                text only; do NOT add a markdown/HTML renderer here. */}
            {item.snippet && <div className="news-desc muted tiny">{item.snippet}</div>}
          </li>
        ))}
      </ul>

      {loading && <p className="muted tiny">{t(($) => $.news.loadingLower)}</p>}
      {feed && items.length < feed.total && !loading && (
        <button className="btn-ghost" style={{ marginTop: 10 }} onClick={onMore}>
          {t(($) => $.news.loadMoreProgress, {
            visible: items.length,
            total: feed.total.toLocaleString(),
          })}
        </button>
      )}
      {feed && feed.available && feed.total === 0 && !loading && (
        <p className="muted">{t(($) => $.news.emptySeekingAlpha)}</p>
      )}
    </>
  );
}

function saFilterTypeLabel(type: (typeof SA_TYPE_OPTIONS)[number], t: ExploreT): string {
  if (type === "article") return t(($) => $.news.analysisArticle);
  if (type === "market_news") return t(($) => $.news.marketNewsType);
  return t(($) => $.news.allTypes);
}

function saRuntimeTypeLabel(type: string, t: ExploreT): string {
  if (type === "article") return t(($) => $.news.analysisArticleRuntime);
  return t(($) => $.news.marketNewsRuntime);
}
