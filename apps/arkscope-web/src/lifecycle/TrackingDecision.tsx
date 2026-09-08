import { ExternalLink } from "lucide-react";
import type { TickerIdentityHistoryDecision } from "../api";
import en from "../i18n/resources/en/explore";
import zh from "../i18n/resources/zh-Hant/explore";
import type { LifecycleLocale } from "./lifecyclePresentation";
import { webCopy, webReason } from "./webPresentation";

export function TrackingDecision({ decision, locale }: { decision?: TickerIdentityHistoryDecision; locale: LifecycleLocale }) {
  const lifecycle = (locale === "en" ? en : zh).lifecycle;
  const activity = lifecycle.activity;
  const copy = activity.decision;
  if (!decision) return <p className="muted">{copy.notRecorded}</p>;
  const names = [...new Set(decision.sources.map((source) => source.name).filter(Boolean))];
  const model = decision.model;
  return <>
    <div className="lifecycle-decision-overview">
      <p className="lifecycle-history-summary">{decision.summary ?? copy.notRecorded}</p>
      <dl className="lifecycle-decision-meta">
        <dt>{copy.sources}</dt><dd>{names.length ? names.join(" / ") : copy.sourcesMissing}</dd>
        <dt>{copy.method}</dt><dd>{copy.methods[decision.method]}{
          model ? <> · {lifecycle.translation.providers[model.provider]} · <span className="mono">{model.model}</span> · {webCopy(locale).auth[model.auth_mode]}</>
          : ["provider_review", "manual_review", "rule_engine"].includes(decision.method)
            && !decision.gaps.includes("legacy_assessment_unsealed") ? <> · {copy.noLlm}</> : null
        }</dd>
        <dt>{copy.approval}</dt><dd>{decision.approval_authority === "attended_user" ? activity.authorities.attendedUser : activity.authorities.automationPolicy}</dd>
        <dt>{copy.eventDate}</dt><dd>{decision.event_date ?? copy.eventDateMissing}</dd>
        {decision.observed_at && <><dt>{copy.observedAt}</dt><dd>{decision.observed_at}</dd></>}
      </dl>
      {!!decision.limitations.length && <div className="lifecycle-decision-notes">
        <strong>{copy.limitations}</strong>
        {decision.limitations.map((note, i) => <p key={i}>{note}</p>)}
      </div>}
      {decision.gaps.map((gap) => <p className="muted" key={gap}>{copy.gaps[gap]}</p>)}
      {!!decision.source_gaps.length && <p className="muted">{copy.sourceGaps}</p>}
    </div>
    <details className="lifecycle-decision-details">
      <summary>{copy.details}</summary>
      {decision.summary && <p>{decision.summary}</p>}
      {decision.impact && decision.impact !== decision.summary && <p>{decision.impact}</p>}
      <ul className="lifecycle-decision-sources">{decision.sources.map((source, i) => <li key={i}>
        <div>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title ?? source.name ?? copy.source}<ExternalLink size={13} aria-hidden="true" /></a>
          : <span>{source.title ?? source.name ?? copy.source}</span>}</div>
        <p className="muted">{[source.name, copy.kinds[source.kind], source.ticker,
          source.market === "stocks" ? copy.stocks : source.market === "otc" ? "OTC" : source.market,
          source.listing_status ? copy.listing[source.listing_status] : null].filter(Boolean).join(" · ")}</p>
        {source.published_at && <p className="muted">{copy.publishedAt}: {source.published_at}</p>}
        {source.observed_at && <p className="muted">{copy.observedAt}: {source.observed_at}</p>}
      </li>)}</ul>
      {!!decision.source_gaps.length && <div><strong>{copy.sourceGaps}</strong><ul>{decision.source_gaps.map((gap, i) => <li key={i}>
        {gap.url && <a href={gap.url} target="_blank" rel="noopener noreferrer">{gap.url}<ExternalLink size={13} aria-hidden="true" /></a>}
        <p>{webReason(gap.reason, locale)}</p>
      </li>)}</ul></div>}
    </details>
  </>;
}
