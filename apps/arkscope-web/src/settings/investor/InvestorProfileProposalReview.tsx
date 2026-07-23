import { ArrowLeft, Check, X } from "lucide-react";
import type { RefObject } from "react";
import { useTranslation } from "react-i18next";

import type { CalibrationProposal, InvestorProfile } from "../../api";
import { Button, InlineAlert } from "../../ui";
import type { SettingsT } from "../settingsCopy";
import {
  investorProfileFieldValue,
  orderedCalibrationTopicDisplays,
  orderedInvestorProfileFieldDisplays,
} from "./investorProfileDisplay";

export interface InvestorProfileProposalReviewProps {
  profile: InvestorProfile;
  proposal: CalibrationProposal;
  currentValuesCurrent: boolean;
  busy: boolean;
  conflict: boolean;
  headingRef: RefObject<HTMLHeadingElement>;
  backButtonRef: RefObject<HTMLButtonElement>;
  onApprove: () => void;
  onReject: () => void;
  onBack: () => void;
  t: SettingsT;
}

export function InvestorProfileProposalReview({
  profile,
  proposal,
  currentValuesCurrent,
  busy,
  conflict,
  headingRef,
  backButtonRef,
  onApprove,
  onReject,
  onBack,
  t,
}: InvestorProfileProposalReviewProps) {
  const { t: commonT } = useTranslation("common");
  const topics = orderedCalibrationTopicDisplays(proposal.covered_topics, t);
  const fields = orderedInvestorProfileFieldDisplays(proposal.proposed_fields, t);
  const hasConflict = conflict || proposal.conflict_fields.length > 0;

  return (
    <section data-testid="investor-profile-proposal-review">
      <div className="ip-actions">
        <Button
          ref={backButtonRef}
          icon={<ArrowLeft size={16} />}
          onClick={onBack}
        >
          {t(($) => $.investor.workspace.actions.backSummary)}
        </Button>
      </div>
      <h3 ref={headingRef} tabIndex={-1} data-investor-mode-heading="proposal">
        {t(($) => $.investor.workspace.mode.proposalReview)}
      </h3>

      {hasConflict ? (
        <InlineAlert
          state="blocked"
          title={t(($) => $.investor.workspace.proposal.conflictTitle)}
        >
          {t(($) => $.investor.workspace.proposal.conflictDescription)}
        </InlineAlert>
      ) : null}

      <section data-testid="proposal-coverage">
        <h4>{t(($) => $.investor.workspace.proposal.coverageTitle)}</h4>
        <div>
          {topics.map((topic, index) => (
            <span className="ip-chip" key={`${index}:${topic.id}`}>{topic.label}</span>
          ))}
        </div>
      </section>

      <section data-testid="proposal-changes">
        <h4>{t(($) => $.investor.workspace.proposal.changesTitle)}</h4>
        <div>
          {fields.map(({ field, label }) => (
            <article className="ip-guardrail" key={field}>
              <h5>{label}</h5>
              {currentValuesCurrent ? (
                <div data-testid="proposal-current-value">
                  <span>{t(($) => $.investor.workspace.proposal.currentValue)}</span>
                  <span>{investorProfileFieldValue(field, profile[field], t, commonT)}</span>
                </div>
              ) : null}
              <div>
                <span>{t(($) => $.investor.workspace.proposal.proposedValue)}</span>
                <span>{investorProfileFieldValue(
                  field,
                  proposal.profile_patch[field],
                  t,
                  commonT,
                )}</span>
              </div>
              {proposal.rationales[field] ? (
                <div>
                  <strong>{t(($) => $.investor.workspace.proposal.rationaleTitle)}</strong>
                  <p>{proposal.rationales[field]}</p>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <div className="ip-actions" data-testid="proposal-actions">
        <Button
          tone="primary"
          icon={<Check size={16} />}
          busy={busy}
          disabled={busy || hasConflict}
          onClick={onApprove}
        >
          {t(($) => $.investor.workspace.actions.approve)}
        </Button>
        <Button
          tone="danger"
          icon={<X size={16} />}
          disabled={busy}
          onClick={onReject}
        >
          {t(($) => $.investor.workspace.actions.reject)}
        </Button>
      </div>
    </section>
  );
}
