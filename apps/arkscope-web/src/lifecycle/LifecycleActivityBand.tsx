import { ArrowRightLeft, Check } from "lucide-react";
import type { TFunction } from "i18next";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import type {
  TickerIdentityTransitionActivity,
  TickerIdentityTransitionActivityChangeType,
  TickerIdentityTransitionActivityType,
  TickerIdentityTransitionBlockReason,
} from "../api";
import { Button } from "../ui/Button";
import {
  lifecycleTrackingSourceLabel,
  type LifecycleLocale,
} from "./lifecyclePresentation";
import {
  tickerTransitionActivityChangeLabel,
  tickerTransitionActivityTypeLabel,
  tickerTransitionBlockReasonLabel,
} from "./tickerIdentityPresentation";

export interface LifecycleActivityItem extends TickerIdentityTransitionActivity {
  reverse_readiness?: {
    reversible: boolean;
    block_reasons: TickerIdentityTransitionBlockReason[];
  } | null;
}

function localeValue(locale: string | undefined): LifecycleLocale {
  return locale === "en" ? "en" : "zh-Hant";
}

function activityTypeLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionActivityType, string> {
  return {
    applied: t(($) => $.lifecycle.activity.types.applied),
    reversed: t(($) => $.lifecycle.activity.types.reversed),
  };
}

function activityChangeLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionActivityChangeType, string> {
  return {
    editable_tag_copied: t(($) => $.lifecycle.activity.changes.editableTagCopied),
    legacy_membership_added: t(($) => $.lifecycle.activity.changes.legacyMembershipAdded),
    legacy_membership_archived: t(
      ($) => $.lifecycle.activity.changes.legacyMembershipArchived,
    ),
    legacy_membership_reactivated: t(
      ($) => $.lifecycle.activity.changes.legacyMembershipReactivated,
    ),
    priority_updated: t(($) => $.lifecycle.activity.changes.priorityUpdated),
    source_hidden: t(($) => $.lifecycle.activity.changes.sourceHidden),
    successor_unhidden: t(($) => $.lifecycle.activity.changes.successorUnhidden),
    watchlist_membership_added: t(
      ($) => $.lifecycle.activity.changes.watchlistMembershipAdded,
    ),
    watchlist_membership_archived: t(
      ($) => $.lifecycle.activity.changes.watchlistMembershipArchived,
    ),
    watchlist_membership_reactivated: t(
      ($) => $.lifecycle.activity.changes.watchlistMembershipReactivated,
    ),
  };
}

function transitionBlockLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionBlockReason, string> {
  return {
    successor_missing: t(($) => $.lifecycle.transition.blockers.successorMissing),
    successor_not_distinct: t(($) => $.lifecycle.transition.blockers.successorNotDistinct),
    outcome_not_executable: t(($) => $.lifecycle.transition.blockers.outcomeNotExecutable),
    assessment_case_mismatch: t(
      ($) => $.lifecycle.transition.blockers.assessmentCaseMismatch,
    ),
    assessment_not_accepted: t(
      ($) => $.lifecycle.transition.blockers.assessmentNotAccepted,
    ),
    assessment_not_direct: t(($) => $.lifecycle.transition.blockers.assessmentNotDirect),
    stale_assessment: t(($) => $.lifecycle.transition.blockers.staleAssessment),
    observation_citation_required: t(
      ($) => $.lifecycle.transition.blockers.observationCitationRequired,
    ),
    execution_date_required: t(($) => $.lifecycle.transition.blockers.executionDateRequired),
    execution_date_invalid: t(($) => $.lifecycle.transition.blockers.executionDateInvalid),
    source_context_unavailable: t(
      ($) => $.lifecycle.transition.blockers.sourceContextUnavailable,
    ),
    no_active_tracking_source: t(
      ($) => $.lifecycle.transition.blockers.noActiveTrackingSource,
    ),
    remap_proposal_missing: t(($) => $.lifecycle.transition.blockers.remapProposalMissing),
    proposal_missing: t(($) => $.lifecycle.transition.blockers.proposalMissing),
    priority_resolution_required: t(
      ($) => $.lifecycle.transition.blockers.priorityResolutionRequired,
    ),
    successor_hidden: t(($) => $.lifecycle.transition.blockers.successorHidden),
    portfolio_position_open: t(
      ($) => $.lifecycle.transition.blockers.portfolioPositionOpen,
    ),
    preview_changed: t(($) => $.lifecycle.transition.blockers.previewChanged),
    reverse_state_changed: t(($) => $.lifecycle.errors.transitionReverseChanged),
    successor_has_later_transition: t(
      ($) => $.lifecycle.errors.transitionLaterExists,
    ),
  };
}

function ActivityRow({
  item,
  busyAction,
  onAcknowledge,
  onReverse,
}: {
  item: LifecycleActivityItem;
  busyAction: string | null;
  onAcknowledge: (activityId: string) => void;
  onReverse: (transitionId: string) => void;
}) {
  const { t, i18n } = useTranslation("explore");
  const locale = localeValue(i18n.resolvedLanguage);
  const unknown = t(($) => $.lifecycle.states.unknownValue);
  const typeLabels = activityTypeLabels(t);
  const changeLabels = activityChangeLabels(t);
  const blockLabels = transitionBlockLabels(t);
  const route = item.successor_ticker
    ? t(($) => $.lifecycle.transition.route, {
      source: item.source_ticker,
      successor: item.successor_ticker,
    })
    : t(($) => $.lifecycle.transition.terminalRoute, { source: item.source_ticker });

  return (
    <article
      className={`lifecycle-activity-row${item.acknowledged_at ? " is-acknowledged" : ""}`}
      data-activity-type={item.activity_type}
    >
      <div className="lifecycle-assessment-heading">
        <strong>{item.rule_id
          ? t(($) => $.lifecycle.activity.automaticChange)
          : tickerTransitionActivityTypeLabel(item.activity_type, typeLabels, unknown)}</strong>
        <span className="lifecycle-state">{item.acknowledged_at
          ? t(($) => $.lifecycle.states.acknowledged)
          : t(($) => $.lifecycle.states.unacknowledged)}</span>
      </div>
      <p className="mono strong">{route}</p>
      <p>{tickerTransitionActivityTypeLabel(item.activity_type, typeLabels, unknown)}</p>
      <p>{t(($) => $.lifecycle.activity.effectiveDate, { date: item.effective_date })}</p>
      <p>{t(($) => $.lifecycle.activity.occurredAt, { time: item.occurred_at })}</p>
      {item.user_owned_changes.map((change) => (
        <p key={change.change_type}>{change.count} {tickerTransitionActivityChangeLabel(
          change.change_type,
          changeLabels,
          unknown,
        )}</p>
      ))}
      {item.provider_owned_retained.map((source) => (
        <p key={source}>{lifecycleTrackingSourceLabel(source, locale)} {
          t(($) => $.lifecycle.activity.retainedSuffix)
        }</p>
      ))}
      {item.rule_id && item.rule_version ? (
        <p className="tiny mono">{t(($) => $.lifecycle.activity.ruleVersion, {
          rule: item.rule_id,
          version: item.rule_version,
        })}</p>
      ) : null}
      {item.activity_type === "applied" ? (
        <div className="lifecycle-commands">
          {item.reverse_readiness?.reversible ? (
            <Button
              size="compact"
              tone="ghost"
              icon={<ArrowRightLeft size={15} />}
              disabled={Boolean(busyAction)}
              onClick={() => onReverse(item.transition_id)}
            >
              {t(($) => $.lifecycle.actions.reverseActivity)}
            </Button>
          ) : item.reverse_readiness ? (
            item.reverse_readiness.block_reasons.map((reason) => (
              <p key={reason}>{tickerTransitionBlockReasonLabel(
                reason,
                blockLabels,
                unknown,
              )}</p>
            ))
          ) : <p>{t(($) => $.lifecycle.activity.reverseUnavailable)}</p>}
        </div>
      ) : null}
      {!item.acknowledged_at ? (
        <Button
          size="compact"
          tone="ghost"
          icon={<Check size={15} />}
          disabled={Boolean(busyAction)}
          onClick={() => onAcknowledge(item.activity_id)}
        >
          {t(($) => $.lifecycle.actions.acknowledgeActivity)}
        </Button>
      ) : null}
    </article>
  );
}

export function LifecycleActivityBand({
  items,
  busyAction,
  onAcknowledge,
  onReverse,
}: {
  items: LifecycleActivityItem[];
  busyAction: string | null;
  onAcknowledge: (activityId: string) => void;
  onReverse: (transitionId: string) => void;
}) {
  const { t } = useTranslation("explore");
  const titleId = useId();
  if (items.length === 0) return null;
  const pending = items.filter((item) => !item.acknowledged_at);
  const history = items.filter((item) => Boolean(item.acknowledged_at));
  const render = (item: LifecycleActivityItem) => (
    <ActivityRow
      item={item}
      busyAction={busyAction}
      onAcknowledge={onAcknowledge}
      onReverse={onReverse}
      key={item.activity_id}
    />
  );

  return (
    <section className="lifecycle-activity-band" aria-labelledby={titleId}>
      {pending.length > 0 ? (
        <div>
          <h3 id={titleId}>{t(($) => $.lifecycle.activity.title)}</h3>
          <div className="lifecycle-activity-list">{pending.map(render)}</div>
        </div>
      ) : null}
      {history.length > 0 ? (
        <div>
          <h3 id={pending.length > 0 ? undefined : titleId}>
            {t(($) => $.lifecycle.activity.recentHistory)}
          </h3>
          <div className="lifecycle-activity-list">{history.map(render)}</div>
        </div>
      ) : null}
    </section>
  );
}
