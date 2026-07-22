import { ClipboardCheck, MessageSquareText, Pencil, RotateCw } from "lucide-react";
import type { RefObject } from "react";

import type { CalibrationState, InvestorProfileResponse } from "../../api";
import { Button, InlineAlert, StatusBadge } from "../../ui";
import {
  settingsInvestorHorizonLabel,
  settingsInvestorPresetLabel,
  settingsMismatchLabel,
  settingsStanceLabel,
  type SettingsT,
} from "../settingsCopy";
import {
  assistantStanceEffect,
  orderedCalibrationTopicDisplays,
} from "./investorProfileDisplay";

export interface InvestorProfileSummaryProps {
  response: InvestorProfileResponse;
  effectiveFactsCurrent: boolean;
  calibration: CalibrationState | null;
  calibrationStatus: "loading" | "ready" | "failed";
  busy: boolean;
  headingRef: RefObject<HTMLHeadingElement>;
  editCommandRef: RefObject<HTMLButtonElement>;
  calibrationCommandRef: RefObject<HTMLButtonElement>;
  proposalCommandRef: RefObject<HTMLButtonElement>;
  onEdit: () => void;
  onCalibration: () => void;
  onReviewProposal: () => void;
  onRetryCalibration: () => void;
  t: SettingsT;
}

export function InvestorProfileSummary({
  response,
  effectiveFactsCurrent,
  calibration,
  calibrationStatus,
  busy,
  headingRef,
  editCommandRef,
  calibrationCommandRef,
  proposalCommandRef,
  onEdit,
  onCalibration,
  onReviewProposal,
  onRetryCalibration,
  t,
}: InvestorProfileSummaryProps) {
  const { profile } = response;
  const activeSession = calibration?.active_session ?? null;
  const pendingProposal = calibration?.latest_proposal?.status === "draft"
    ? calibration.latest_proposal
    : null;
  const coveredTopics = orderedCalibrationTopicDisplays(
    pendingProposal?.covered_topics ?? [],
    t,
  );
  const pendingTurnStatus = calibration?.pending_turn?.status ?? null;
  const calibrationState = pendingTurnStatus === "pending"
    ? "running"
    : pendingTurnStatus === "failed" || pendingTurnStatus === "interrupted"
      ? "interrupted"
      : activeSession
        ? "ready"
        : "empty";
  const calibrationLabel = pendingTurnStatus === "pending"
    ? t(($) => $.investor.workspace.calibration.sending)
    : pendingTurnStatus === "failed" || pendingTurnStatus === "interrupted"
      ? t(($) => $.investor.workspace.calibration.interrupted)
      : activeSession
        ? t(($) => $.investor.workspace.summary.calibrationActive)
        : t(($) => $.investor.workspace.summary.calibrationIdle);

  return (
    <section data-testid="investor-profile-summary">
      <h3 ref={headingRef} tabIndex={-1} data-investor-mode-heading="summary">
        {t(($) => $.investor.workspace.summary.title)}
      </h3>
      <p className="muted">{t(($) => $.investor.workspace.summary.description)}</p>

      <div className="ip-guardrail">
        <StatusBadge
          state={profile.enabled ? "ready" : "blocked"}
          label={profile.enabled
            ? t(($) => $.investor.workspace.summary.personalizationEnabled)
            : t(($) => $.investor.workspace.summary.personalizationDisabled)}
        />
        {effectiveFactsCurrent ? (
          <div>
            <strong>{t(($) => $.investor.workspace.summary.effectiveStance)}</strong>
            <div>{settingsStanceLabel(response.effective_stance, t)}</div>
            <p className="muted">{assistantStanceEffect(response.effective_stance, t)}</p>
          </div>
        ) : null}
        <div>
          <strong>{t(($) => $.investor.fields.preset)}</strong>
          <div>{settingsInvestorPresetLabel(profile.primary_preset, t)}</div>
        </div>
        <div>
          <strong>{t(($) => $.investor.fields.horizon)}</strong>
          <div>{settingsInvestorHorizonLabel(profile.holding_horizon, t)}</div>
        </div>
        <div>
          <strong>{t(($) => $.investor.fields.riskAppetite)}</strong>
          <div>{profile.risk_appetite ?? t(($) => $.investor.fields.unset)}</div>
        </div>
        <div>
          <strong>{t(($) => $.investor.fields.riskCapacity)}</strong>
          <div>{profile.risk_capacity ?? t(($) => $.investor.fields.unset)}</div>
        </div>
        <div>
          <strong>{t(($) => $.investor.workspace.summary.riskComparison)}</strong>
          <StatusBadge
            state={profile.risk_mismatch === "none" ? "ready" : "partial"}
            label={settingsMismatchLabel(profile.risk_mismatch, t)}
          />
        </div>
      </div>

      <div className="ip-actions">
        <Button
          ref={editCommandRef}
          icon={<Pencil size={16} />}
          disabled={busy}
          onClick={onEdit}
        >
          {t(($) => $.investor.workspace.actions.edit)}
        </Button>
        {calibrationStatus === "ready" ? (
          <Button
            ref={calibrationCommandRef}
            icon={<MessageSquareText size={16} />}
            disabled={busy}
            onClick={onCalibration}
          >
            {activeSession
              ? t(($) => $.investor.workspace.actions.continueCalibration)
              : t(($) => $.investor.workspace.actions.startCalibration)}
          </Button>
        ) : null}
      </div>

      {calibrationStatus === "loading" ? (
        <StatusBadge state="loading" label={t(($) => $.investor.panel.loading)} />
      ) : null}
      {calibrationStatus === "failed" ? (
        <InlineAlert state="partial" title={t(($) => $.investor.workspace.errors.calibrationLoad)}>
          <Button
            size="compact"
            icon={<RotateCw size={15} />}
            disabled={busy}
            onClick={onRetryCalibration}
          >
            {t(($) => $.investor.workspace.calibration.retry)}
          </Button>
        </InlineAlert>
      ) : null}
      {calibrationStatus === "ready" ? (
        <StatusBadge state={calibrationState} label={calibrationLabel} />
      ) : null}

      {pendingProposal ? (
        <section className="ip-guardrail" data-testid="summary-pending-proposal">
          <strong>{t(($) => $.investor.workspace.summary.proposalPending)}</strong>
          {coveredTopics.length ? (
            <div>
              {coveredTopics.map((topic, index) => (
                <span className="ip-chip" key={`${index}:${topic.id}`}>{topic.label}</span>
              ))}
            </div>
          ) : null}
          <div className="ip-actions">
            <Button
              ref={proposalCommandRef}
              icon={<ClipboardCheck size={16} />}
              disabled={busy}
              onClick={onReviewProposal}
            >
              {t(($) => $.investor.workspace.actions.reviewProposal)}
            </Button>
          </div>
        </section>
      ) : null}

      <section>
        <h4>{t(($) => $.investor.workspace.summary.contextTitle)}</h4>
        <p className="muted">{t(($) => $.investor.workspace.summary.contextCurrentNotice)}</p>
        <details data-testid="current-context-disclosure">
          <summary>{t(($) => $.investor.workspace.context.disclosureTitle)}</summary>
          <p>{t(($) => $.investor.workspace.context.explanation)}</p>
          {!effectiveFactsCurrent ? (
            <p>{t(($) => $.investor.workspace.summary.contextUnavailable)}</p>
          ) : !profile.enabled ? (
            <p>{t(($) => $.investor.workspace.summary.contextDisabled)}</p>
          ) : response.context_preview ? (
            <>
              <strong>{t(($) => $.investor.workspace.context.exactTitle)}</strong>
              <pre>{response.context_preview}</pre>
            </>
          ) : (
            <p>{t(($) => $.investor.workspace.summary.contextUnavailable)}</p>
          )}
          <p className="muted">{t(($) => $.investor.workspace.context.notesNonCausal)}</p>
        </details>
      </section>
    </section>
  );
}
