import { describe, expect, it } from "vitest";

import type {
  TickerIdentityTransitionBlockReason,
  TickerIdentityTransitionCaveat,
  TickerIdentityTransitionStatus,
} from "../api";
import {
  tickerTransitionBlockReasonLabel,
  tickerTransitionCaveatLabel,
  tickerTransitionStatusLabel,
} from "./tickerIdentityPresentation";

const STATUS_LABELS = {
  approved: "Scheduled; waiting for the effective date",
  needs_review: "Needs a new review",
  applied: "Applied",
  cancelled: "Cancelled",
  reversed: "Reversed",
} satisfies Record<TickerIdentityTransitionStatus, string>;

const BLOCK_LABELS = {
  successor_missing: "Successor missing",
  successor_not_distinct: "Successor is unchanged",
  outcome_not_executable: "Outcome is not executable",
  assessment_case_mismatch: "Assessment case mismatch",
  assessment_not_accepted: "Assessment is not accepted",
  assessment_not_direct: "Assessment is not direct",
  stale_assessment: "Assessment is stale",
  observation_citation_required: "Observation citation required",
  execution_date_required: "Execution date required",
  execution_date_invalid: "Execution date invalid",
  source_context_unavailable: "Tracking context unavailable",
  no_active_tracking_source: "No active tracking source",
  remap_proposal_missing: "Remap recommendation missing",
  proposal_missing: "Recommendation missing",
  priority_resolution_required: "Priority choice required",
  successor_hidden: "Successor is hidden",
  portfolio_position_open: "Broker position remains open",
  preview_changed: "Preview changed",
  reverse_state_changed: "Applied state changed",
  successor_has_later_transition: "A later transition exists",
} satisfies Record<TickerIdentityTransitionBlockReason, string>;

const CAVEAT_LABELS = {
  provider_owned_sources_retained: "Provider tracking is retained",
  portfolio_position_retained: "Tracking moves while the old broker position remains",
  successor_already_tracked: "Successor is already tracked",
} satisfies Record<TickerIdentityTransitionCaveat, string>;

describe("ticker identity presentation", () => {
  it("keeps activity authority and type labels exhaustive with an explicit unknown value", async () => {
    const presentation = await import("./tickerIdentityPresentation");
    const activityLabels = {
      applied: "Applied automatically",
      reversed: "Reversed",
    };
    const authorityLabels = {
      attended_user: "Approved by user",
      automation_policy: "Approved by automation policy",
    };

    expect(presentation.tickerTransitionActivityTypeLabel(
      "applied",
      activityLabels,
      "Unrecognized value",
    )).toBe("Applied automatically");
    expect(presentation.tickerTransitionActivityTypeLabel(
      "future_activity",
      activityLabels,
      "Unrecognized value",
    )).toBe("Unrecognized value");
    expect(presentation.tickerTransitionApprovalAuthorityLabel(
      "automation_policy",
      authorityLabels,
      "Unrecognized value",
    )).toBe("Approved by automation policy");
    expect(presentation.tickerTransitionApprovalAuthorityLabel(
      "future_authority",
      authorityLabels,
      "Unrecognized value",
    )).toBe("Unrecognized value");
  });

  it("keeps every durable status distinct and uses an explicit unknown value", () => {
    expect(tickerTransitionStatusLabel("approved", STATUS_LABELS, "Unknown")).toBe(
      "Scheduled; waiting for the effective date",
    );
    expect(tickerTransitionStatusLabel("needs_review", STATUS_LABELS, "Unknown")).toBe(
      "Needs a new review",
    );
    expect(tickerTransitionStatusLabel("applied", STATUS_LABELS, "Unknown")).toBe("Applied");
    expect(tickerTransitionStatusLabel("cancelled", STATUS_LABELS, "Unknown")).toBe("Cancelled");
    expect(tickerTransitionStatusLabel("reversed", STATUS_LABELS, "Unknown")).toBe("Reversed");
    expect(tickerTransitionStatusLabel("future_status", STATUS_LABELS, "Unknown")).toBe("Unknown");
  });

  it("does not collapse broker retention or blockers into a generic state", () => {
    expect(tickerTransitionCaveatLabel(
      "portfolio_position_retained",
      CAVEAT_LABELS,
      "Unknown",
    )).toBe("Tracking moves while the old broker position remains");
    expect(tickerTransitionBlockReasonLabel(
      "portfolio_position_open",
      BLOCK_LABELS,
      "Unknown",
    )).toBe("Broker position remains open");
    expect(tickerTransitionBlockReasonLabel(
      "future_blocker",
      BLOCK_LABELS,
      "Unknown",
    )).toBe("Unknown");
  });
});
