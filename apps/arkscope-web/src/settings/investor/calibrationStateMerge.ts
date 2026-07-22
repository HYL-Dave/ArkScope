import type {
  CalibrationMessage,
  CalibrationProposal,
  CalibrationSession,
  CalibrationState,
  CalibrationTurn,
  InvestorProfile,
} from "../../api";

export interface CalibrationStateMergeOptions {
  acceptIncomingTurnId?: string;
  acceptIncomingProposalId?: string;
}

function selectedSessionId(state: CalibrationState): string | null {
  return state.active_session?.id
    ?? state.pending_turn?.session_id
    ?? state.latest_proposal?.session_id
    ?? state.messages[0]?.session_id
    ?? state.sessions[0]?.id
    ?? null;
}

function appendUnique(values: readonly string[], incoming: readonly string[]): string[] {
  const seen = new Set(values);
  const merged = [...values];
  for (const value of incoming) {
    if (seen.has(value)) continue;
    seen.add(value);
    merged.push(value);
  }
  return merged;
}

function mergeSession(
  previous: CalibrationSession,
  incoming: CalibrationSession,
): CalibrationSession {
  const previousTerminal = previous.status === "closed" || previous.status === "superseded";
  const next = previousTerminal && incoming.status === "active" ? previous : incoming;
  return {
    ...next,
    covered_topics: appendUnique(previous.covered_topics, incoming.covered_topics),
  };
}

function mergeSessions(
  previous: readonly CalibrationSession[],
  incoming: readonly CalibrationSession[],
): CalibrationSession[] {
  const previousById = new Map(previous.map((item) => [item.id, item]));
  const merged = incoming.map((item) => {
    const existing = previousById.get(item.id);
    previousById.delete(item.id);
    return existing ? mergeSession(existing, item) : item;
  });
  for (const item of previous) {
    if (previousById.has(item.id)) merged.push(item);
  }
  return merged;
}

function mergeMessages(
  previous: readonly CalibrationMessage[],
  incoming: readonly CalibrationMessage[],
): CalibrationMessage[] {
  const seen = new Set(previous.map((item) => item.id));
  return [
    ...previous,
    ...incoming.filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    }),
  ];
}

function hasAssistantCompletion(messages: readonly CalibrationMessage[], turnId: string): boolean {
  return messages.some((item) => item.role === "assistant" && item.turn_id === turnId);
}

function mergePendingTurn(
  previous: CalibrationTurn | null,
  incoming: CalibrationTurn | null,
  messages: readonly CalibrationMessage[],
  acceptIncomingTurnId: string | undefined,
): CalibrationTurn | null {
  if (incoming && hasAssistantCompletion(messages, incoming.id)) return null;
  if (previous && hasAssistantCompletion(messages, previous.id)) return null;
  if (!previous) return incoming;
  if (!incoming) return previous;
  if (previous.id !== incoming.id) {
    return incoming.id === acceptIncomingTurnId ? incoming : previous;
  }
  if (previous.status !== "pending" && incoming.status === "pending") return previous;
  return incoming;
}

function proposalHasConflict(proposal: CalibrationProposal): boolean {
  return proposal.status === "draft" && proposal.conflict_fields.length > 0;
}

function proposalIsTerminal(proposal: CalibrationProposal): boolean {
  return proposal.status !== "draft";
}

function mergeProposal(
  previous: CalibrationProposal | null,
  incoming: CalibrationProposal | null,
  acceptIncomingProposalId: string | undefined,
): CalibrationProposal | null {
  if (!previous) return incoming;
  if (!incoming) return previous;
  if (previous.id !== incoming.id) {
    return incoming.id === acceptIncomingProposalId ? incoming : previous;
  }
  if (proposalIsTerminal(previous) && !proposalIsTerminal(incoming)) return previous;
  if (
    proposalHasConflict(previous)
    && incoming.status === "draft"
    && !proposalHasConflict(incoming)
  ) return previous;
  return incoming;
}

export function mergeCalibrationState(
  previous: CalibrationState | null,
  incoming: CalibrationState,
  options: CalibrationStateMergeOptions = {},
): CalibrationState {
  if (!previous) return incoming;
  const previousSessionId = selectedSessionId(previous);
  const incomingSessionId = selectedSessionId(incoming);
  if (
    (previousSessionId === null && incomingSessionId !== null)
    || (
      previousSessionId !== null
      && incomingSessionId !== null
      && previousSessionId !== incomingSessionId
    )
  ) return incoming;

  const messages = mergeMessages(previous.messages, incoming.messages);
  const activeSession = previous.active_session && incoming.active_session
    && previous.active_session.id === incoming.active_session.id
    ? mergeSession(previous.active_session, incoming.active_session)
    : incoming.active_session;
  return {
    ...incoming,
    active_session: activeSession,
    sessions: mergeSessions(previous.sessions, incoming.sessions),
    messages,
    pending_turn: mergePendingTurn(
      previous.pending_turn,
      incoming.pending_turn,
      messages,
      options.acceptIncomingTurnId,
    ),
    latest_proposal: mergeProposal(
      previous.latest_proposal,
      incoming.latest_proposal,
      options.acceptIncomingProposalId,
    ),
  };
}

export function hasNewAssistantCompletion(
  state: CalibrationState,
  turnId: string,
  priorAssistantMessageIds: ReadonlySet<string>,
): boolean {
  return state.messages.some((item) => (
    item.role === "assistant"
    && item.turn_id === turnId
    && !priorAssistantMessageIds.has(item.id)
  ));
}

export function isNewDraftProposal(
  state: CalibrationState,
  priorProposalId: string | null,
): boolean {
  return state.latest_proposal?.status === "draft"
    && state.latest_proposal.id !== priorProposalId;
}

function cloneProfileValue(value: unknown): unknown {
  return Array.isArray(value) ? [...value] : value;
}

export function applyProposalPatch(
  current: InvestorProfile,
  proposal: CalibrationProposal,
): InvestorProfile {
  const next = {
    ...current,
    preferred_edge: [...current.preferred_edge],
    avoidances: [...current.avoidances],
    behavioral_flags: [...current.behavioral_flags],
  };
  const target = next as unknown as Record<string, unknown>;
  const patch = proposal.profile_patch as Record<string, unknown>;
  for (const field of proposal.proposed_fields) {
    if (!Object.prototype.hasOwnProperty.call(patch, field)) continue;
    target[field] = cloneProfileValue(patch[field]);
  }
  return next;
}

function sameProposalValue(left: unknown, right: unknown): boolean {
  if (!Array.isArray(left) || !Array.isArray(right)) return Object.is(left, right);
  if (left.length !== right.length) return false;
  const rightValues = new Set(right.map((item) => JSON.stringify(item)));
  return left.every((item) => rightValues.has(JSON.stringify(item)));
}

export function profileCorroboratesProposalPatch(
  profile: InvestorProfile,
  proposal: CalibrationProposal,
): boolean {
  const candidate = profile as unknown as Record<string, unknown>;
  const patch = proposal.profile_patch as Record<string, unknown>;
  return proposal.proposed_fields.every((field) => (
    Object.prototype.hasOwnProperty.call(patch, field)
    && sameProposalValue(candidate[field], patch[field])
  ));
}
