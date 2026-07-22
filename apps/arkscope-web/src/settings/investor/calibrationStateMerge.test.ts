import { describe, expect, it } from "vitest";

import type {
  CalibrationMessage,
  CalibrationProposal,
  CalibrationSession,
  CalibrationState,
  CalibrationTurn,
  InvestorProfile,
} from "../../api";
import {
  applyProposalPatch,
  hasNewAssistantCompletion,
  isNewDraftProposal,
  mergeCalibrationState,
  profileCorroboratesProposalPatch,
} from "./calibrationStateMerge";

function session(overrides: Partial<CalibrationSession> = {}): CalibrationSession {
  return {
    id: "session-1",
    status: "active",
    interview_version: 1,
    covered_topics: [],
    current_topic_id: "loss_response",
    current_question_message_id: "question-1",
    superseded_reason: null,
    created_at: "2026-07-21T01:00:00Z",
    updated_at: "2026-07-21T01:00:00Z",
    closed_at: null,
    ...overrides,
  };
}

function message(overrides: Partial<CalibrationMessage> = {}): CalibrationMessage {
  return {
    id: "question-1",
    session_id: "session-1",
    role: "assistant",
    content: "QUESTION_ONE",
    turn_id: null,
    topic_id: "loss_response",
    prompt_id: "loss_response.opening.v1",
    created_at: "2026-07-21T01:00:00Z",
    ...overrides,
  };
}

function turn(overrides: Partial<CalibrationTurn> = {}): CalibrationTurn {
  return {
    id: "turn-1",
    session_id: "session-1",
    kind: "answer",
    status: "pending",
    question_message_id: "question-1",
    addressed_topic_id: "loss_response",
    next_topic_id: null,
    error_code: null,
    diagnostic: null,
    attempt_count: 1,
    created_at: "2026-07-21T01:01:00Z",
    updated_at: "2026-07-21T01:01:00Z",
    completed_at: null,
    ...overrides,
  };
}

function proposal(overrides: Partial<CalibrationProposal> = {}): CalibrationProposal {
  return {
    id: "proposal-1",
    session_id: "session-1",
    status: "draft",
    profile_patch: { risk_capacity: 6 },
    proposed_fields: ["risk_capacity"],
    covered_topics: ["financial_capacity"],
    rationales: { risk_capacity: "RATIONALE" },
    conflict_fields: [],
    created_at: "2026-07-21T01:02:00Z",
    approved_at: null,
    rejected_at: null,
    conflicted_at: null,
    superseded_at: null,
    superseded_reason: null,
    ...overrides,
  };
}

function state(overrides: Partial<CalibrationState> = {}): CalibrationState {
  const active = session();
  return {
    active_session: active,
    sessions: [active],
    messages: [message()],
    pending_turn: null,
    latest_proposal: null,
    topic_catalog: ["loss_response", "financial_capacity", "time_horizon"],
    ...overrides,
  };
}

function profile(overrides: Partial<InvestorProfile> = {}): InvestorProfile {
  return {
    enabled: true,
    primary_preset: "event_driven",
    risk_appetite: 8,
    risk_capacity: 4,
    risk_mismatch: "appetite_above_capacity",
    holding_horizon: "multi_year",
    drawdown_tolerance_pct: 12,
    concentration_limit_pct: 25,
    preferred_edge: ["growth"],
    avoidances: ["leverage"],
    behavioral_flags: ["FOMO"],
    freeform_notes: "NOTES",
    default_stance: "complementary",
    skill_mode: "off",
    last_reviewed_at: null,
    updated_at: null,
    ...overrides,
  };
}

describe("calibrationStateMerge", () => {
  it("merges same-session messages by stable ID and keeps coverage monotonic", () => {
    const previousSession = session({ covered_topics: ["loss_response", "time_horizon"] });
    const previous = state({
      active_session: previousSession,
      sessions: [previousSession],
      messages: [message(), message({ id: "answer-1", role: "user", content: "ANSWER" })],
    });
    const incomingSession = session({ covered_topics: ["financial_capacity"] });
    const incoming = state({
      active_session: incomingSession,
      sessions: [incomingSession],
      messages: [
        message({ content: "STALE_REWRITE" }),
        message({ id: "question-2", content: "QUESTION_TWO", turn_id: "turn-1" }),
      ],
    });

    const merged = mergeCalibrationState(previous, incoming);

    expect(merged.messages.map((item) => [item.id, item.content])).toEqual([
      ["question-1", "QUESTION_ONE"],
      ["answer-1", "ANSWER"],
      ["question-2", "QUESTION_TWO"],
    ]);
    expect(merged.active_session?.covered_topics).toEqual([
      "loss_response",
      "time_horizon",
      "financial_capacity",
    ]);
    expect(merged.sessions[0]?.covered_topics).toEqual(merged.active_session?.covered_topics);
  });

  it("keeps session pointers when an older same-session snapshot arrives", () => {
    const previousSession = session({
      covered_topics: ["loss_response"],
      current_topic_id: "time_horizon",
      current_question_message_id: "question-current",
      updated_at: "2026-07-21T01:03:00Z",
    });
    const incomingSession = session({
      covered_topics: ["financial_capacity"],
      current_topic_id: "financial_capacity",
      current_question_message_id: "question-stale",
      updated_at: "2026-07-21T01:02:00Z",
    });

    const merged = mergeCalibrationState(
      state({ active_session: previousSession, sessions: [previousSession] }),
      state({ active_session: incomingSession, sessions: [incomingSession] }),
    );

    expect(merged.active_session).toMatchObject({
      current_topic_id: "time_horizon",
      current_question_message_id: "question-current",
      updated_at: "2026-07-21T01:03:00Z",
      covered_topics: ["loss_response", "financial_capacity"],
    });
    expect(merged.sessions[0]).toMatchObject({
      current_topic_id: "time_horizon",
      current_question_message_id: "question-current",
    });
  });

  it("advances same-second session pointers only with semantic forward evidence", () => {
    const previousSession = session({
      covered_topics: ["loss_response"],
      current_topic_id: "loss_response",
      current_question_message_id: "question-1",
      updated_at: "2026-07-21T01:03:00Z",
    });
    const incomingSession = session({
      covered_topics: ["loss_response"],
      current_topic_id: "financial_capacity",
      current_question_message_id: "question-2",
      updated_at: "2026-07-21T01:03:00Z",
    });
    const incoming = state({
      active_session: incomingSession,
      sessions: [incomingSession],
      messages: [
        message(),
        message({ id: "question-2", turn_id: "turn-2", topic_id: "financial_capacity" }),
      ],
    });

    const unaccepted = mergeCalibrationState(
      state({ active_session: previousSession, sessions: [previousSession] }),
      incoming,
    );
    expect(unaccepted.active_session).toMatchObject({
      current_topic_id: "loss_response",
      current_question_message_id: "question-1",
    });

    const accepted = mergeCalibrationState(
      state({ active_session: previousSession, sessions: [previousSession] }),
      incoming,
      { acceptIncomingTurnId: "turn-2" },
    );
    expect(accepted.active_session).toMatchObject({
      current_topic_id: "financial_capacity",
      current_question_message_id: "question-2",
    });

    const expandedSession = session({
      covered_topics: ["loss_response", "financial_capacity"],
      current_topic_id: "time_horizon",
      current_question_message_id: "question-3",
      updated_at: "2026-07-21T01:03:00Z",
    });
    const expanded = mergeCalibrationState(
      state({ active_session: previousSession, sessions: [previousSession] }),
      state({ active_session: expandedSession, sessions: [expandedSession] }),
    );
    expect(expanded.active_session).toMatchObject({
      current_topic_id: "time_horizon",
      current_question_message_id: "question-3",
    });
  });

  it("does not regress pending-turn terminal evidence across mixed snapshots", () => {
    const cases = [
      { previous: turn({ status: "failed" }), incoming: turn(), expected: "failed" },
      { previous: turn({ status: "interrupted" }), incoming: turn(), expected: "interrupted" },
    ] as const;
    for (const item of cases) {
      const merged = mergeCalibrationState(
        state({ pending_turn: item.previous }),
        state({ pending_turn: item.incoming }),
      );
      expect(merged.pending_turn?.status).toBe(item.expected);
    }

    const missingWithoutEvidence = mergeCalibrationState(
      state({ pending_turn: turn() }),
      state({ pending_turn: null }),
    );
    expect(missingWithoutEvidence.pending_turn?.status).toBe("pending");

    const completed = mergeCalibrationState(
      state({ pending_turn: turn() }),
      state({
        pending_turn: null,
        messages: [message(), message({ id: "question-2", turn_id: "turn-1" })],
      }),
    );
    expect(completed.pending_turn).toBeNull();
  });

  it("preserves clean conflict and terminal proposal authority", () => {
    const clean = proposal();
    expect(mergeCalibrationState(
      state({ latest_proposal: clean }),
      state({ latest_proposal: null }),
    ).latest_proposal).toEqual(clean);

    const conflict = proposal({ conflict_fields: ["risk_capacity"] });
    expect(mergeCalibrationState(
      state({ latest_proposal: conflict }),
      state({ latest_proposal: clean }),
    ).latest_proposal).toEqual(conflict);

    const approved = proposal({ status: "approved", approved_at: "2026-07-21T01:03:00Z" });
    expect(mergeCalibrationState(
      state({ latest_proposal: conflict }),
      state({ latest_proposal: approved }),
    ).latest_proposal).toEqual(approved);
    expect(mergeCalibrationState(
      state({ latest_proposal: approved }),
      state({ latest_proposal: clean }),
    ).latest_proposal).toEqual(approved);

    const other = proposal({ id: "proposal-other" });
    expect(mergeCalibrationState(
      state({ latest_proposal: approved }),
      state({ latest_proposal: other }),
    ).latest_proposal).toEqual(approved);
  });

  it("resets on session replacement and accepts explicitly observed new authorities", () => {
    const prior = state({ latest_proposal: proposal() });
    const identityMissing = state({
      active_session: null,
      sessions: [],
      messages: [],
      pending_turn: null,
      latest_proposal: null,
    });
    expect(mergeCalibrationState(prior, identityMissing).latest_proposal).toEqual(
      prior.latest_proposal,
    );

    const replacementSession = session({ id: "session-2" });
    const replacement = state({
      active_session: replacementSession,
      sessions: [replacementSession],
      messages: [message({ id: "session-2-question", session_id: "session-2" })],
      latest_proposal: proposal({ id: "session-2-proposal", session_id: "session-2" }),
    });
    expect(mergeCalibrationState(state({ latest_proposal: proposal() }), replacement))
      .toBe(replacement);

    const incoming = state({
      pending_turn: turn({ id: "turn-2" }),
      latest_proposal: proposal({ id: "proposal-2" }),
    });
    const merged = mergeCalibrationState(
      state({ pending_turn: turn({ status: "failed" }), latest_proposal: proposal() }),
      incoming,
      { acceptIncomingTurnId: "turn-2", acceptIncomingProposalId: "proposal-2" },
    );
    expect(merged.pending_turn?.id).toBe("turn-2");
    expect(merged.latest_proposal?.id).toBe("proposal-2");
  });

  it("recognizes only new matching assistant completion and genuinely new drafts", () => {
    const priorAssistantIds = new Set(["old-assistant"]);
    const completed = state({
      messages: [
        message({ id: "old-assistant", turn_id: "turn-1" }),
        message({ id: "new-assistant", turn_id: "turn-1" }),
      ],
      latest_proposal: proposal({ id: "proposal-2" }),
    });

    expect(hasNewAssistantCompletion(completed, "turn-1", priorAssistantIds)).toBe(true);
    expect(hasNewAssistantCompletion(
      state({ messages: [message({ id: "old-assistant", turn_id: "turn-1" })] }),
      "turn-1",
      priorAssistantIds,
    )).toBe(false);
    expect(isNewDraftProposal(completed, "proposal-1")).toBe(true);
    expect(isNewDraftProposal(completed, "proposal-2")).toBe(false);
  });

  it("applies proposal fields and corroborates them without freezing unrelated values", () => {
    const current = profile();
    const patch = proposal({
      profile_patch: { risk_capacity: 6, preferred_edge: ["quality", "growth"] },
      proposed_fields: ["risk_capacity", "preferred_edge"],
    });
    const expected = applyProposalPatch(current, patch);

    expect(expected.risk_capacity).toBe(6);
    expect(expected.preferred_edge).toEqual(["quality", "growth"]);
    expect(expected.primary_preset).toBe("event_driven");
    expect(expected.risk_mismatch).toBe("unclear");
    expect(profileCorroboratesProposalPatch(
      profile({
        primary_preset: "income",
        risk_capacity: 6,
        preferred_edge: ["growth", "quality"],
      }),
      patch,
    )).toBe(true);
    expect(profileCorroboratesProposalPatch(
      profile({ risk_capacity: 4, preferred_edge: ["growth", "quality"] }),
      patch,
    )).toBe(false);
  });
});
