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
import { useTranslation } from "react-i18next";

import { getInvestorProfile, type AssistantStance, type InvestorProfileResponse, type PersonalizationTrace, type RuntimeConfig } from "./api";
import { stanceLabel, traceSummary } from "./personalizationDisplay";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
  type ExploreT,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";
import {
  generateCard,
  getCard,
  getCards,
  saveCard,
  translateCard,
  type CardSummary,
  type EvidenceItem,
  type EvidencePacket,
  type ResultCard,
} from "./api";

export function AICardTab({
  ticker,
  runtime,
  developerMode,
  onNavigateTarget,
}: {
  ticker: string;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const { t: commonT } = useTranslation("common");
  const [recent, setRecent] = useState<CardSummary[] | null>(null);
  const [card, setCard] = useState<ResultCard | null>(null);
  const [evidencePacket, setEvidencePacket] = useState<EvidencePacket | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [recentErr, setRecentErr] = useState<ExploreErrorState | null>(null);
  const [profileErr, setProfileErr] = useState<ExploreErrorState | null>(null);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [failedOpenRunId, setFailedOpenRunId] = useState<number | null>(null);
  // Track A: opt-in stance override for card synthesis + trace of the run shown.
  const [investorProfile, setInvestorProfile] = useState<InvestorProfileResponse | null>(null);
  const [cardStance, setCardStance] = useState<AssistantStance>("off");
  const [lastTrace, setLastTrace] = useState<PersonalizationTrace | null>(null);
  // Evidence news window (defaults match the backend: 21 days / 12 articles).
  const [showAdv, setShowAdv] = useState(false);
  const [newsDays, setNewsDays] = useState(21);
  const [maxNews, setMaxNews] = useState(12);

  // Request token for IN-INSTANCE supersession: generate() and openCard() bump
  // it, so if the user opens a recent card (or starts another generate) while a
  // 1-2 min generate is still running, the stale response is dropped instead of
  // clobbering the newer one. Cross-ticker isolation comes from the parent
  // remounting this component per ticker (Watchlist keys TickerDetail by
  // ticker), NOT from this token.
  const reqRef = useRef(0);
  const profileReqRef = useRef(0);

  const loadRecent = useCallback(async () => {
    const id = reqRef.current;
    try {
      const d = await getCards(ticker, 10);
      if (id === reqRef.current) {
        setRecent(d.cards);
        setRecentErr(null);
      }
    } catch (e) {
      if (id === reqRef.current) {
        setRecentErr(captureExploreError("card_load_recent", e));
      }
    }
  }, [ticker]);

  const loadInvestorProfile = useCallback(async () => {
    const id = ++profileReqRef.current;
    try {
      const response = await getInvestorProfile();
      if (id !== profileReqRef.current) return;
      setInvestorProfile(response);
      setProfileErr(null);
      if (response.profile.enabled) setCardStance(response.profile.default_stance);
    } catch (e) {
      if (id === profileReqRef.current) {
        setProfileErr(captureExploreError("card_load_investor_profile", e));
      }
    }
  }, []);

  useEffect(() => {
    void loadInvestorProfile();
    return () => {
      profileReqRef.current += 1;
    };
  }, [loadInvestorProfile]);

  useEffect(() => {
    reqRef.current++; // invalidate any in-flight response from a prior ticker
    setLastTrace(null);
    setCard(null);
    setEvidencePacket(null);
    setRunId(null);
    setSaved(false);
    setSaving(false);
    setBusy(false);
    setErr(null);
    setRecentErr(null);
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
        news_days: newsDays,
        max_news: maxNews,
        assistant_stance: investorProfile?.profile.enabled ? cardStance : undefined,
      }, runtime);
      if (id !== reqRef.current) return; // superseded (ticker switch / new action)
      setLastTrace(r.personalization ?? null);
      setCard(r.card);
      setEvidencePacket(r.evidence_packet);
      setRunId(r.run_id);
      void loadRecent();
    } catch (e) {
      if (id === reqRef.current) setErr(captureExploreError("card_generate", e));
    } finally {
      if (id === reqRef.current) setBusy(false);
    }
  }

  async function openCard(rid: number) {
    const id = ++reqRef.current;
    setErr(null);
    setFailedOpenRunId(rid);
    try {
      const d = await getCard(rid);
      if (id !== reqRef.current) return;
      setLastTrace(d.personalization ?? null);
      setCard(d.card);
      setEvidencePacket(d.evidence_packet);
      setRunId(d.run_id);
      setSaved(d.status === "saved");
    } catch (e) {
      if (id === reqRef.current) setErr(captureExploreError("card_open", e));
    }
  }

  async function save() {
    if (runId == null || saved || saving) return;
    setSaving(true);
    setErr(null);
    try {
      await saveCard(runId);
      setSaved(true);
      void loadRecent();
    } catch (e) {
      setErr(captureExploreError("card_save", e));
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

  function retryAction() {
    if (err?.operation === "card_open" && failedOpenRunId !== null) {
      void openCard(failedOpenRunId);
    } else if (err?.operation === "card_save") {
      void save();
    } else {
      void generate();
    }
  }

  return (
    <div className="aicard">
      <div className="aicard-actions">
        <input
          className="aicard-q"
          placeholder={t(($) => $.aiCard.questionPlaceholder, { ticker })}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter") void generate();
          }}
        />
        <button className="btn-ghost" onClick={() => void generate()} disabled={busy}>
          {busy ? t(($) => $.aiCard.generating) : t(($) => $.aiCard.generate)}
        </button>
        <button
          className="btn-ghost"
          onClick={() => setShowAdv((v) => !v)}
          disabled={busy}
          title={t(($) => $.aiCard.newsRange)}
        >
          {showAdv
            ? t(($) => $.aiCard.advancedExpanded)
            : t(($) => $.aiCard.advancedCollapsed)}
        </button>
      </div>
      {showAdv && (
        <div className="aicard-adv">
          <label>{t(($) => $.aiCard.newsLookback)}
            <input type="number" min={1} max={90} value={newsDays} disabled={busy}
              onChange={(e) => setNewsDays(clampInt(e.target.value, 1, 90, 21))} /> {t(($) => $.aiCard.daysSuffix)}
          </label>
          <label>{t(($) => $.aiCard.maximumUsed)}
            <input type="number" min={1} max={50} value={maxNews} disabled={busy}
              onChange={(e) => setMaxNews(clampInt(e.target.value, 1, 50, 12))} /> {t(($) => $.aiCard.recentArticlesSuffix)}
          </label>
          <span className="muted tiny">{t(($) => $.aiCard.defaultNewsRange)}</span>
          {investorProfile?.profile.enabled && (
            <label>{t(($) => $.aiCard.stance)}
              <select value={cardStance} disabled={busy}
                onChange={(e) => setCardStance(e.target.value as AssistantStance)}>
                {(["off", "neutral", "aligned", "complementary", "strict_risk_control", "valuation_rationalist", "growth_opportunity"] as AssistantStance[]).map((s) => (
                  <option key={s} value={s}>{stanceLabel(s, commonT)}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
      {busy && <p className="muted tiny">{t(($) => $.aiCard.generationProgress)}</p>}
      {recentErr && (
        <ExploreErrorNotice
          state={recentErr}
          developerMode={developerMode}
          retryLabel={t(($) => $.aiCard.retry)}
          onRetry={() => void loadRecent()}
          onNavigate={onNavigateTarget}
        />
      )}
      {profileErr && (
        <ExploreErrorNotice
          state={profileErr}
          developerMode={developerMode}
          retryLabel={t(($) => $.aiCard.retry)}
          onRetry={() => void loadInvestorProfile()}
          onNavigate={onNavigateTarget}
        />
      )}
      {err && (
        <ExploreErrorNotice
          state={err}
          developerMode={developerMode}
          retryLabel={t(($) => $.aiCard.retry)}
          onRetry={retryAction}
          onNavigate={onNavigateTarget}
        />
      )}

      {lastTrace && traceSummary(lastTrace, commonT) && (
        <p className="muted tiny">{traceSummary(lastTrace, commonT)}</p>
      )}
      {card ? (
        <CardView
          key={runId ?? "none"}
          card={card}
          runId={runId}
          evidencePacket={evidencePacket}
          saved={saved}
          saving={saving}
          runtime={runtime}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
          onSave={() => void save()}
          onBack={backToList}
        />
      ) : (
        !busy && (
          <>
            <h4 className="detail-section">{t(($) => $.aiCard.recentCards)}</h4>
            {recent === null ? (
              !recentErr ? <p className="muted tiny">{t(($) => $.aiCard.loadingLower)}</p> : null
            ) : recent.length === 0 ? (
              <p className="muted tiny">{t(($) => $.aiCard.emptyCards)}</p>
            ) : (
              <ul className="aicard-recent">
                {recent.map((c) => (
                  <li key={c.run_id} onClick={() => void openCard(c.run_id)}>
                    <span className={`conf conf-${c.confidence_level ?? "na"}`}>
                      {confidenceLabel(c.confidence_level, t)}
                    </span>
                    <span className="aicard-recent-concl">{c.conclusion ?? "—"}</span>
                    {c.status === "saved" && (
                      <span className="saved-star" title={t(($) => $.aiCard.savedAsReport)}>★</span>
                    )}
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
  runId,
  evidencePacket,
  saved,
  saving,
  runtime,
  developerMode,
  onNavigateTarget,
  onSave,
  onBack,
  backLabel,
}: {
  card: ResultCard;
  runId?: number | null;
  evidencePacket?: EvidencePacket | null;
  saved: boolean;
  saving?: boolean;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
  onSave: () => void;
  onBack?: () => void;
  backLabel?: string;
}) {
  const { t } = useTranslation("explore");
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

  // On-demand 繁中 translation (prose fields only; cached server-side). CardView
  // is keyed by runId at the call sites, so this state resets per card.
  const [lang, setLang] = useState<"en" | "zh">("en");
  const [zh, setZh] = useState<ResultCard | null>(null);
  const [translating, setTranslating] = useState(false);
  const [tErr, setTErr] = useState<ExploreErrorState | null>(null);
  const shown = lang === "zh" && zh ? zh : card;

  async function toZh() {
    if (zh) {
      setLang("zh");
      return;
    }
    if (runId == null) return;
    setTranslating(true);
    setTErr(null);
    try {
      const r = await translateCard(runId, "zh-Hant", runtime);
      setZh(r.card);
      setLang("zh");
    } catch (e) {
      setTErr(captureExploreError("card_translate", e));
    } finally {
      setTranslating(false);
    }
  }

  return (
    <div className="cardview">
      <div className="cardview-head">
        {onBack && (
          <button className="btn-ghost" onClick={onBack}>
            {backLabel ?? t(($) => $.aiCard.backToCards)}
          </button>
        )}
        {runId != null && (
          <span className="lang-toggle">
            <button
              className={`btn-ghost ${lang === "en" ? "on" : ""}`}
              onClick={() => setLang("en")}
              disabled={translating}
            >
              {t(($) => $.aiCard.english)}
            </button>
            <button
              className={`btn-ghost ${lang === "zh" ? "on" : ""}`}
              onClick={() => void toZh()}
              disabled={translating}
            >
              {translating
                ? t(($) => $.aiCard.translating)
                : t(($) => $.aiCard.traditionalChinese)}
            </button>
          </span>
        )}
        <span className="spacer" />
        <span className={`conf conf-${card.confidence_level}`}>
          {confidenceLabel(card.confidence_level, t)}
        </span>
        <button className="btn-ghost" onClick={onSave} disabled={saved || saving}>
          {saved
            ? t(($) => $.aiCard.savedReport)
            : saving
              ? t(($) => $.aiCard.saving)
              : t(($) => $.aiCard.saveAsReport)}
        </button>
      </div>
      {tErr && (
        <ExploreErrorNotice
          state={tErr}
          developerMode={developerMode}
          retryLabel={t(($) => $.aiCard.retry)}
          onRetry={() => void toZh()}
          onNavigate={onNavigateTarget}
        />
      )}

      {shown.question && (
        <p className="cardview-q muted tiny">
          {t(($) => $.aiCard.questionPrefix)}{shown.question}
        </p>
      )}
      <p className="cardview-concl">{shown.conclusion}</p>
      {shown.confidence_rationale && (
        <p className="muted tiny">
          {t(($) => $.aiCard.confidenceExplanation)} {shown.confidence_rationale}
        </p>
      )}

      <Section title={t(($) => $.aiCard.primaryReasons)} items={shown.primary_reasons} />
      <Section title={t(($) => $.aiCard.counterReasons)} items={shown.counter_thesis} counter />
      <Section title={t(($) => $.aiCard.invalidationConditions)} items={shown.invalidation_conditions} />
      <Section title={t(($) => $.aiCard.triggers)} items={shown.trigger_conditions} />
      <Section title={t(($) => $.aiCard.keyAssumptions)} items={shown.key_assumptions} />
      <Section title={t(($) => $.aiCard.risks)} items={shown.risks} />
      <Section title={t(($) => $.aiCard.watchlist)} items={shown.watch_list} />
      {shown.market_narrative && (
        <Para title={t(($) => $.aiCard.marketNarrative)} text={shown.market_narrative} />
      )}
      {shown.divergence && (
        <Para title={t(($) => $.aiCard.consensusDivergence)} text={shown.divergence} />
      )}

      <details className="cardview-trace">
        <summary>
          {t(($) => $.aiCard.traceabilityPrefix)}
          {tr.data_sources.length} {t(($) => $.aiCard.sourcesSeparator)} {tr.claims.length}
          {t(($) => $.aiCard.citationsSuffix)}
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
            <div className="muted tiny trace-claims-h">
              {t(($) => $.aiCard.claimCitations)}
            </div>
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
              {t(($) => $.aiCard.evidenceSummary, {
                shown: shownEvidence.length || evidencePacket.items.length,
                total: evidencePacket.items.length,
              })}
            </div>
            {shownEvidence.length === 0 ? (
              <p className="muted tiny">{t(($) => $.aiCard.noEvidenceItem)}</p>
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
                      {item.as_of
                        ? t(($) => $.aiCard.asOf, { value: item.as_of })
                        : t(($) => $.aiCard.asOfMissing)}
                      {item.freshness ? (
                        <span> {t(($) => $.aiCard.freshnessSuffix, { freshness: item.freshness })}</span>
                      ) : null}
                      {item.is_real_time ? <span> {t(($) => $.aiCard.realtime)}</span> : null}
                    </div>
                    {item.note && <div className="muted tiny">{item.note}</div>}
                    <div className="evidence-data tiny">{summarizeEvidenceData(item.data, t)}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="muted tiny">
          {t(($) => $.aiCard.newsCompleteness)} {yn(tr.completeness.news)} {" "}
          {t(($) => $.aiCard.fundamentalsSuffix)} {yn(tr.completeness.fundamentals)} {" "}
          {t(($) => $.aiCard.technicalsSuffix)} {yn(tr.completeness.technicals)}
          {tr.completeness.note ? (
            <span> {t(($) => $.aiCard.completenessNote, { note: tr.completeness.note })}</span>
          ) : null}
        </div>
        <div className="muted tiny">
          {t(($) => $.aiCard.singleModelInference)} {yn(tr.is_single_model_inference)}
        </div>
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
  runtime,
  developerMode,
  onNavigateTarget,
}: {
  runId: number;
  onClose: () => void;
  onChanged?: () => void;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [card, setCard] = useState<ResultCard | null>(null);
  const [evidencePacket, setEvidencePacket] = useState<EvidencePacket | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
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
        if (alive) setErr(captureExploreError("card_open", e));
      });
    return () => {
      alive = false;
    };
  }, [runId, reload]);

  async function save() {
    if (saving || saved) return;
    setSaving(true);
    setErr(null);
    try {
      await saveCard(runId);
      setSaved(true);
      onChanged?.();
    } catch (e) {
      setErr(captureExploreError("card_save", e));
    } finally {
      setSaving(false);
    }
  }

  function retry() {
    if (err?.operation === "card_save") {
      void save();
    } else {
      setReload((x) => x + 1);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={card
          ? t(($) => $.aiCard.tickerCardLabel, { ticker: card.ticker })
          : t(($) => $.aiCard.cardLabel)}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <span className="strong">
            {card
              ? t(($) => $.aiCard.cardTitle, { ticker: card.ticker })
              : t(($) => $.aiCard.cardTitleFallback)}
          </span>
          <span className="spacer" />
          <button ref={closeBtnRef} className="btn-ghost" onClick={onClose}>
            {t(($) => $.aiCard.close)}
          </button>
        </div>
        {err && (
          <ExploreErrorNotice
            state={err}
            developerMode={developerMode}
            retryLabel={t(($) => $.aiCard.retry)}
            onRetry={retry}
            onNavigate={onNavigateTarget}
          />
        )}
        {!card ? (
          !err ? <p className="muted">{t(($) => $.aiCard.loading)}</p> : null
        ) : (
          <CardView
            key={runId}
            card={card}
            runId={runId}
            evidencePacket={evidencePacket}
            saved={saved}
            saving={saving}
            runtime={runtime}
            developerMode={developerMode}
            onNavigateTarget={onNavigateTarget}
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

function clampInt(raw: string, lo: number, hi: number, fallback: number): number {
  const n = parseInt(raw, 10);
  if (Number.isNaN(n)) return fallback;
  return Math.max(lo, Math.min(hi, n));
}

function unique(xs: string[]): string[] {
  return Array.from(new Set(xs.filter(Boolean)));
}

function confidenceLabel(level: CardSummary["confidence_level"], t: ExploreT): string {
  switch (level) {
    case "high":
      return t(($) => $.aiCard.confidenceHigh);
    case "medium":
      return t(($) => $.aiCard.confidenceMedium);
    case "low":
      return t(($) => $.aiCard.confidenceLow);
    default:
      return level ?? "—";
  }
}

function summarizeEvidenceData(data: Record<string, unknown>, t: ExploreT): string {
  const entries = Object.entries(data).slice(0, 6);
  if (entries.length === 0) return t(($) => $.aiCard.noStructuredPayload);
  return entries.map(([key, value]) => `${key}: ${summarizeValue(value, t)}`).join(" · ");
}

function summarizeValue(value: unknown, t: ExploreT): string {
  if (value == null) return "—";
  if (typeof value === "string") return clip(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return t(($) => $.aiCard.itemCount, { count: value.length });
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return `{${keys.slice(0, 4).join(", ")}${keys.length > 4 ? ", …" : ""}}`;
  }
  return clip(String(value));
}

function clip(s: string): string {
  return s.length > 120 ? `${s.slice(0, 117)}…` : s;
}
