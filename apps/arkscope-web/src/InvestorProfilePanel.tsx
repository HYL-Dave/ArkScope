import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  approveCalibrationProposal,
  draftInvestorProfile,
  getCalibrationState,
  getInvestorProfile,
  rejectCalibrationProposal,
  requestCalibrationProposal,
  retryCalibrationTurn,
  saveInvestorProfile,
  sendCalibrationMessage,
  startCalibrationSession,
  type CalibrationProposal,
  type CalibrationState,
  type InvestorProfile,
  type InvestorProfileResponse,
} from "./api";
import { DeveloperDiagnostics } from "./settings/DeveloperDiagnostics";
import { InvestorProfileCalibration } from "./settings/investor/InvestorProfileCalibration";
import { InvestorProfileEdit } from "./settings/investor/InvestorProfileEdit";
import { InvestorProfileProposalReview } from "./settings/investor/InvestorProfileProposalReview";
import { InvestorProfileSummary } from "./settings/investor/InvestorProfileSummary";
import {
  applyProposalPatch,
  hasNewAssistantCompletion,
  isNewDraftProposal,
  mergeCalibrationState,
  profileCorroboratesProposalPatch,
  type CalibrationStateMergeOptions,
} from "./settings/investor/calibrationStateMerge";
import { CALIBRATION_TOPIC_IDS } from "./settings/investor/investorProfileDisplay";
import { settingsErrorPresentation } from "./settings/settingsBackendCopy";
import type { SettingsT } from "./settings/settingsCopy";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settings/settingsNavigationGuard";
import { Button, ConfirmDialog, InlineAlert, StatusBadge } from "./ui";

export interface InvestorProfilePanelProps {
  developerMode?: boolean;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  onNavigateToProviders?: () => void;
  summaryRequestSequence?: number;
  onSummaryRequestHandled?: (sequence: number, committed: boolean) => void;
  turnIdFactory?: () => string;
}

type InvestorMode = "summary" | "edit" | "calibration" | "proposal";
type ReturnCommand = "edit" | "calibration" | "proposal";
type BusyAction =
  | "profile_load"
  | "draft"
  | "save"
  | "calibration_load"
  | "calibration_start"
  | "turn"
  | "retry"
  | "request_proposal"
  | "approve"
  | "reject";
type ErrorScope =
  | "profile_load"
  | "save"
  | "refresh"
  | "status_refresh"
  | "turn"
  | "proposal";

interface OperationError {
  scope: ErrorScope;
  error: unknown;
}

interface ProposalAuthority {
  kind: "terminal" | "conflict";
  proposal: CalibrationProposal;
}

interface CalibrationOperationBaseline {
  priorProposalId: string | null;
  priorAssistantMessageIds: ReadonlySet<string>;
}

const PROFILE_AUTHORITY_UNCORROBORATED = new Error("profile_authority_not_corroborated");

function cloneProfile(profile: InvestorProfile): InvestorProfile {
  return {
    ...profile,
    preferred_edge: [...profile.preferred_edge],
    avoidances: [...profile.avoidances],
    behavioral_flags: [...profile.behavioral_flags],
  };
}

function profilePayload(profile: InvestorProfile): Partial<InvestorProfile> {
  return {
    enabled: profile.enabled,
    primary_preset: profile.primary_preset,
    risk_appetite: profile.risk_appetite,
    risk_capacity: profile.risk_capacity,
    holding_horizon: profile.holding_horizon,
    drawdown_tolerance_pct: profile.drawdown_tolerance_pct,
    concentration_limit_pct: profile.concentration_limit_pct,
    preferred_edge: [...profile.preferred_edge],
    avoidances: [...profile.avoidances],
    behavioral_flags: [...profile.behavioral_flags],
    freeform_notes: profile.freeform_notes,
    default_stance: profile.default_stance,
  };
}

function sameEditableProfile(left: InvestorProfile | null, right: InvestorProfile | null): boolean {
  if (!left || !right) return true;
  return JSON.stringify(profilePayload(left)) === JSON.stringify(profilePayload(right));
}

function sameProfileSnapshot(left: InvestorProfile, right: InvestorProfile): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function observedProposalAuthority(proposal: CalibrationProposal): ProposalAuthority | null {
  if (proposal.status !== "draft") return { kind: "terminal", proposal };
  if (proposal.conflict_fields.length > 0) return { kind: "conflict", proposal };
  return null;
}

function defaultTurnId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID();
  return `calibration-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function boundedDiagnostic(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.slice(0, 512);
}

function calibrationOperationBaseline(
  state: CalibrationState | null,
): CalibrationOperationBaseline {
  return {
    priorProposalId: state?.latest_proposal?.id ?? null,
    priorAssistantMessageIds: new Set(
      state?.messages
        .filter((message) => message.role === "assistant")
        .map((message) => message.id) ?? [],
    ),
  };
}

function operationErrorTitle(scope: ErrorScope, t: SettingsT): string {
  switch (scope) {
    case "profile_load":
      return t(($) => $.investor.workspace.errors.profileLoad);
    case "save":
      return t(($) => $.investor.workspace.errors.save);
    case "refresh":
      return t(($) => $.investor.workspace.errors.refresh);
    case "status_refresh":
      return t(($) => $.errors.refreshFailed);
    case "turn":
      return t(($) => $.investor.workspace.errors.turn);
    case "proposal":
      return t(($) => $.investor.workspace.errors.proposal);
  }
}

export function InvestorProfilePanel({
  developerMode = false,
  onNavigationGuardChange,
  onNavigateToProviders,
  summaryRequestSequence = 0,
  onSummaryRequestHandled,
  turnIdFactory = defaultTurnId,
}: InvestorProfilePanelProps) {
  const { t } = useTranslation("settings");
  const mountedRef = useRef(false);
  const profileGenerationRef = useRef(0);
  const calibrationGenerationRef = useRef(0);
  const actionInFlightRef = useRef(false);
  const profileAuthorityRef = useRef<InvestorProfile | null>(null);
  const profileAuthorityProposalRef = useRef<CalibrationProposal | null>(null);
  const proposalAuthorityRef = useRef<ProposalAuthority | null>(null);
  const calibrationRef = useRef<CalibrationState | null>(null);
  const consumedSummaryRequestSequenceRef = useRef(0);
  const pendingSummaryAckRef = useRef<number | null>(null);

  const [profileStatus, setProfileStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [profileResponse, setProfileResponse] = useState<InvestorProfileResponse | null>(null);
  const [profileError, setProfileError] = useState<unknown>(null);
  const [profileValuesCurrent, setProfileValuesCurrent] = useState(false);
  const [effectiveFactsCurrent, setEffectiveFactsCurrent] = useState(false);
  const [calibrationStatus, setCalibrationStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [calibration, setCalibration] = useState<CalibrationState | null>(null);
  const [calibrationError, setCalibrationError] = useState<unknown>(null);
  const [mode, setMode] = useState<InvestorMode>("summary");
  const [draft, setDraft] = useState<InvestorProfile | null>(null);
  const [baseline, setBaseline] = useState<InvestorProfile | null>(null);
  const [answer, setAnswer] = useState("");
  const [busyAction, setBusyAction] = useState<BusyAction | null>(null);
  const [operationError, setOperationError] = useState<OperationError | null>(null);
  const [proposalConflict, setProposalConflict] = useState(false);
  const [outcome, setOutcome] = useState<"draft" | "saved" | "approved" | "rejected" | null>(null);
  const [blockedNotice, setBlockedNotice] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [returnCommand, setReturnCommand] = useState<ReturnCommand>("edit");
  const [summaryCommitSequence, setSummaryCommitSequence] = useState<number | null>(null);

  const summaryHeadingRef = useRef<HTMLHeadingElement>(null);
  const editHeadingRef = useRef<HTMLHeadingElement>(null);
  const calibrationHeadingRef = useRef<HTMLHeadingElement>(null);
  const proposalHeadingRef = useRef<HTMLHeadingElement>(null);
  const editCommandRef = useRef<HTMLButtonElement>(null);
  const calibrationCommandRef = useRef<HTMLButtonElement>(null);
  const proposalCommandRef = useRef<HTMLButtonElement>(null);
  const editBackRef = useRef<HTMLButtonElement>(null);
  const calibrationBackRef = useRef<HTMLButtonElement>(null);
  const proposalBackRef = useRef<HTMLButtonElement>(null);
  const dialogReturnFocusRef = useRef<HTMLElement | null>(null);
  const modeFocusReadyRef = useRef(false);

  const applyProfileResponse = useCallback((response: InvestorProfileResponse, generation: number) => {
    if (!mountedRef.current || profileGenerationRef.current !== generation) return false;
    const authority = profileAuthorityRef.current;
    const authorityProposal = profileAuthorityProposalRef.current;
    const authorityCorroborated = authority && (
      sameProfileSnapshot(response.profile, authority)
      || Boolean(
        authorityProposal
        && profileCorroboratesProposalPatch(response.profile, authorityProposal),
      )
    );
    if (authority && !authorityCorroborated) {
      setProfileStatus("ready");
      setProfileError(null);
      setProfileValuesCurrent(true);
      setEffectiveFactsCurrent(false);
      return true;
    }
    profileAuthorityRef.current = null;
    profileAuthorityProposalRef.current = null;
    setProfileResponse(response);
    setDraft(cloneProfile(response.profile));
    setBaseline(cloneProfile(response.profile));
    setProfileStatus("ready");
    setProfileError(null);
    setProfileValuesCurrent(true);
    setEffectiveFactsCurrent(true);
    return true;
  }, []);

  const installProfileAuthority = useCallback((
    profile: InvestorProfile,
    proposal: CalibrationProposal | null = null,
  ) => {
    const authority = cloneProfile(profile);
    profileAuthorityRef.current = authority;
    profileAuthorityProposalRef.current = proposal;
    setProfileResponse((current) => current
      ? { ...current, profile: cloneProfile(authority) }
      : current);
    setDraft(cloneProfile(authority));
    setBaseline(cloneProfile(authority));
    setProfileStatus("ready");
    setProfileError(null);
    setProfileValuesCurrent(true);
    setEffectiveFactsCurrent(false);
  }, []);

  const installProposalAuthority = useCallback((
    proposal: CalibrationProposal,
    kind: ProposalAuthority["kind"],
  ) => {
    proposalAuthorityRef.current = { kind, proposal };
    const current = calibrationRef.current;
    if (current) {
      const next = { ...current, latest_proposal: proposal };
      calibrationRef.current = next;
      setCalibration(next);
    }
  }, []);

  const applyCalibrationState = useCallback((
    state: CalibrationState,
    generation: number,
    options: CalibrationStateMergeOptions = {},
  ) => {
    if (!mountedRef.current || calibrationGenerationRef.current !== generation) return null;
    const mergedState = mergeCalibrationState(calibrationRef.current, state, options);
    let latestProposal = mergedState.latest_proposal;
    let authority = proposalAuthorityRef.current;
    if (
      authority
      && mergedState.active_session
      && mergedState.active_session.id !== authority.proposal.session_id
    ) {
      authority = null;
    }
    if (authority) {
      if (!latestProposal) {
        latestProposal = authority.proposal;
      } else if (latestProposal.id !== authority.proposal.id) {
        authority = observedProposalAuthority(latestProposal);
      } else if (latestProposal.status !== "draft") {
        authority = { kind: "terminal", proposal: latestProposal };
      } else if (authority.kind === "terminal") {
        latestProposal = authority.proposal;
      } else if (latestProposal.conflict_fields.length > 0) {
        authority = { kind: "conflict", proposal: latestProposal };
      } else {
        latestProposal = authority.proposal;
      }
    } else if (latestProposal) {
      authority = observedProposalAuthority(latestProposal);
    }
    proposalAuthorityRef.current = authority;
    const nextState = latestProposal === mergedState.latest_proposal
      ? mergedState
      : { ...mergedState, latest_proposal: latestProposal };
    calibrationRef.current = nextState;
    setProposalConflict(Boolean(
      latestProposal?.status === "draft"
      && (
        latestProposal.conflict_fields.length > 0
        || (authority?.kind === "conflict" && authority.proposal.id === latestProposal.id)
      )
    ));
    setCalibration(nextState);
    setCalibrationStatus("ready");
    setCalibrationError(null);
    return nextState;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const profileGeneration = ++profileGenerationRef.current;
    const calibrationGeneration = ++calibrationGenerationRef.current;
    const profileRequest = getInvestorProfile().then((response) => {
      applyProfileResponse(response, profileGeneration);
    }).catch((error: unknown) => {
      if (!mountedRef.current || profileGenerationRef.current !== profileGeneration) return;
      setProfileStatus("failed");
      setProfileError(error);
    });
    const calibrationRequest = getCalibrationState().then((state) => {
      applyCalibrationState(state, calibrationGeneration);
    }).catch((error: unknown) => {
      if (!mountedRef.current || calibrationGenerationRef.current !== calibrationGeneration) return;
      setCalibrationStatus("failed");
      setCalibrationError(error);
    });
    void Promise.allSettled([profileRequest, calibrationRequest]);
    return () => {
      mountedRef.current = false;
      actionInFlightRef.current = false;
    };
  }, [applyCalibrationState, applyProfileResponse]);

  const dirty = mode === "edit" && !sameEditableProfile(draft, baseline);
  const persistedTurnRunning = calibration?.pending_turn?.status === "pending";
  const busy = busyAction !== null || persistedTurnRunning;

  useEffect(() => {
    onNavigationGuardChange?.({
      dirty,
      busy,
      reason: busy
        ? t(($) => $.investor.workspace.guard.busy)
        : dirty
          ? t(($) => $.investor.workspace.guard.dirtyDescription)
          : null,
    });
  }, [busy, dirty, onNavigationGuardChange, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  useEffect(() => {
    if (!modeFocusReadyRef.current) {
      modeFocusReadyRef.current = true;
      return;
    }
    if (mode === "edit") editHeadingRef.current?.focus();
    if (mode === "calibration") calibrationHeadingRef.current?.focus();
    if (mode === "proposal") proposalHeadingRef.current?.focus();
    if (mode === "summary") {
      if (pendingSummaryAckRef.current !== null) return;
      const target = returnCommand === "edit"
        ? editCommandRef.current
        : returnCommand === "calibration"
          ? calibrationCommandRef.current
          : proposalCommandRef.current;
      (target ?? summaryHeadingRef.current)?.focus();
    }
  }, [mode, returnCommand]);

  useEffect(() => {
    if (mode !== "summary" || summaryCommitSequence === null) return;
    if (pendingSummaryAckRef.current !== summaryCommitSequence) return;
    pendingSummaryAckRef.current = null;
    setSummaryCommitSequence(null);
    onSummaryRequestHandled?.(summaryCommitSequence, true);
  }, [mode, onSummaryRequestHandled, summaryCommitSequence]);

  const pendingProposal = calibration?.latest_proposal?.status === "draft"
    ? calibration.latest_proposal
    : null;

  useEffect(() => {
    if (mode === "proposal" && !pendingProposal && !busy) {
      setReturnCommand("proposal");
      setMode("summary");
    }
  }, [busy, mode, pendingProposal]);

  const beginAction = (action: BusyAction) => {
    const pendingTurnBlocksAction = persistedTurnRunning
      && action !== "profile_load"
      && action !== "calibration_load";
    if (actionInFlightRef.current || pendingTurnBlocksAction) {
      setBlockedNotice(true);
      return false;
    }
    actionInFlightRef.current = true;
    setBusyAction(action);
    setOperationError(null);
    setBlockedNotice(false);
    setOutcome(null);
    return true;
  };

  const finishAction = () => {
    actionInFlightRef.current = false;
    setBusyAction(null);
  };

  const reloadCalibrationAfterFailure = async (
    generation: number,
    scope: Extract<ErrorScope, "turn" | "proposal">,
    error: unknown,
    turnId: string,
    priorProposalId: string | null,
    priorAssistantMessageIds: ReadonlySet<string>,
    clearAnswerWhenCompleted = false,
  ) => {
    if (!mountedRef.current || calibrationGenerationRef.current !== generation) return;
    setOperationError({ scope, error });
    try {
      const state = await getCalibrationState();
      const newDraft = isNewDraftProposal(state, priorProposalId);
      const appliedState = applyCalibrationState(state, generation, {
        acceptIncomingTurnId: state.pending_turn?.id === turnId ? turnId : undefined,
        acceptIncomingProposalId: newDraft ? state.latest_proposal?.id : undefined,
      });
      if (!appliedState) return;
      const sameTurnCompleted = appliedState.pending_turn === null
        && hasNewAssistantCompletion(appliedState, turnId, priorAssistantMessageIds);
      if (sameTurnCompleted) {
        setOperationError(null);
        if (clearAnswerWhenCompleted) setAnswer("");
      }
      if (
        sameTurnCompleted
        && newDraft
        && appliedState.latest_proposal?.status === "draft"
        && appliedState.latest_proposal.id !== priorProposalId
      ) {
        setOperationError(null);
        finishToSummary("proposal");
      }
    } catch (loadError) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setCalibrationStatus("failed");
        setCalibrationError(loadError);
      }
    }
  };

  const retryProfileLoad = async () => {
    const retainedRefreshError = operationError
      && (operationError.scope === "refresh" || operationError.scope === "status_refresh")
      ? operationError
      : null;
    if (!beginAction("profile_load")) return;
    const generation = ++profileGenerationRef.current;
    const hasAuthority = profileAuthorityRef.current !== null && profileResponse !== null;
    if (!hasAuthority) setProfileStatus("loading");
    setProfileError(null);
    try {
      const response = await getInvestorProfile();
      if (!applyProfileResponse(response, generation)) return;
      if (profileAuthorityRef.current && retainedRefreshError) {
        setOperationError(retainedRefreshError);
      }
    } catch (error) {
      if (mountedRef.current && profileGenerationRef.current === generation) {
        if (profileAuthorityRef.current && profileResponse) {
          setProfileStatus("ready");
          setProfileError(null);
          setProfileValuesCurrent(true);
          setEffectiveFactsCurrent(false);
          setOperationError({ scope: retainedRefreshError?.scope ?? "refresh", error });
        } else {
          setProfileStatus("failed");
          setProfileError(error);
        }
      }
    } finally {
      if (mountedRef.current && profileGenerationRef.current === generation) finishAction();
    }
  };

  const finishToSummary = (command: ReturnCommand) => {
    setReturnCommand(command);
    setMode("summary");
    setBlockedNotice(false);
  };

  const requestSummary = (command: ReturnCommand): "blocked" | "confirming" | "committed" => {
    if (busy) {
      setBlockedNotice(true);
      return "blocked";
    }
    if (mode === "edit" && dirty) {
      dialogReturnFocusRef.current = editBackRef.current;
      setConfirmDiscard(true);
      return "confirming";
    }
    finishToSummary(command);
    return "committed";
  };

  const settleProposalAuthority = (
    state: CalibrationState,
    proposalId: string | undefined,
  ) => {
    const latest = state.latest_proposal;
    if (latest && latest.id === proposalId && latest.status === "draft") {
      setMode("proposal");
      return;
    }
    if (latest && latest.id === proposalId && latest.status === "approved") {
      setOutcome("approved");
      setOperationError(null);
    } else if (latest && latest.id === proposalId && latest.status === "rejected") {
      setOutcome("rejected");
      setOperationError(null);
    }
    finishToSummary("proposal");
  };

  useEffect(() => {
    if (summaryRequestSequence <= consumedSummaryRequestSequenceRef.current) return;
    consumedSummaryRequestSequenceRef.current = summaryRequestSequence;
    pendingSummaryAckRef.current = summaryRequestSequence;
    const command = mode === "edit"
      ? "edit"
      : mode === "proposal"
        ? "proposal"
        : "calibration";
    const result = requestSummary(command);
    if (result === "committed") {
      setSummaryCommitSequence(summaryRequestSequence);
    } else if (result === "blocked") {
      pendingSummaryAckRef.current = null;
      onSummaryRequestHandled?.(summaryRequestSequence, false);
    }
  }, [onSummaryRequestHandled, summaryRequestSequence]);

  const enterEdit = () => {
    if (!profileResponse || busy) return;
    setDraft(cloneProfile(profileResponse.profile));
    setBaseline(cloneProfile(profileResponse.profile));
    setReturnCommand("edit");
    setMode("edit");
    setOperationError(null);
    setOutcome(null);
  };

  const continueCalibration = () => {
    if (busy || !calibration?.active_session) return;
    setReturnCommand("calibration");
    setMode("calibration");
    setOperationError(null);
    setOutcome(null);
  };

  const retryCalibrationLoad = async () => {
    if (!beginAction("calibration_load")) return;
    const generation = ++calibrationGenerationRef.current;
    setCalibrationStatus("loading");
    setCalibrationError(null);
    try {
      const state = await getCalibrationState();
      const appliedState = applyCalibrationState(state, generation);
      if (appliedState && mode === "proposal") {
        settleProposalAuthority(appliedState, pendingProposal?.id);
      }
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setCalibrationStatus("failed");
        setCalibrationError(error);
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) finishAction();
    }
  };

  const startCalibration = async () => {
    if (!beginAction("calibration_start")) return;
    const generation = ++calibrationGenerationRef.current;
    try {
      const state = await startCalibrationSession(false);
      if (applyCalibrationState(state, generation)) {
        setReturnCommand("calibration");
        setMode("calibration");
      }
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setOperationError({ scope: "turn", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) finishAction();
    }
  };

  const runDraft = async () => {
    if (!draft || !beginAction("draft")) return;
    try {
      const response = await draftInvestorProfile(profilePayload(draft));
      if (!mountedRef.current) return;
      setDraft(cloneProfile(response.profile));
      setOutcome("draft");
    } catch (error) {
      if (mountedRef.current) setOperationError({ scope: "save", error });
    } finally {
      if (mountedRef.current) finishAction();
    }
  };

  const saveProfile = async () => {
    if (!draft || !beginAction("save")) return;
    const generation = ++profileGenerationRef.current;
    try {
      const saved = await saveInvestorProfile(profilePayload(draft));
      if (!mountedRef.current || profileGenerationRef.current !== generation) return;
      const savedProfile = cloneProfile(saved.profile);
      profileAuthorityRef.current = savedProfile;
      profileAuthorityProposalRef.current = null;
      setProfileResponse((current) => ({
        ...(current ?? saved),
        profile: cloneProfile(savedProfile),
      }));
      setDraft(cloneProfile(savedProfile));
      setBaseline(cloneProfile(savedProfile));
      setProfileValuesCurrent(true);
      setEffectiveFactsCurrent(false);
      let refreshed: InvestorProfileResponse;
      try {
        refreshed = await getInvestorProfile();
      } catch (error) {
        if (mountedRef.current && profileGenerationRef.current === generation) {
          setOperationError({ scope: "refresh", error });
        }
        return;
      }
      if (!applyProfileResponse(refreshed, generation)) return;
      setOutcome("saved");
      finishToSummary("edit");
    } catch (error) {
      if (mountedRef.current && profileGenerationRef.current === generation) {
        setOperationError({ scope: "save", error });
      }
    } finally {
      if (mountedRef.current && profileGenerationRef.current === generation) finishAction();
    }
  };

  const sendAnswer = async () => {
    const session = calibration?.active_session;
    if (!session || calibration?.pending_turn || !answer.trim() || !beginAction("turn")) return;
    const generation = ++calibrationGenerationRef.current;
    const turnId = turnIdFactory();
    const baselineEvidence = calibrationOperationBaseline(calibrationRef.current);
    try {
      const state = await sendCalibrationMessage({
        turn_id: turnId,
        session_id: session.id,
        content: answer,
      });
      const newDraft = isNewDraftProposal(state, baselineEvidence.priorProposalId);
      const appliedState = applyCalibrationState(state, generation, {
        acceptIncomingTurnId: turnId,
        acceptIncomingProposalId: newDraft ? state.latest_proposal?.id : undefined,
      });
      if (!appliedState) return;
      setAnswer("");
      if (newDraft && appliedState.latest_proposal?.status === "draft") {
        finishToSummary("proposal");
      }
    } catch (error) {
      await reloadCalibrationAfterFailure(
        generation,
        "turn",
        error,
        turnId,
        baselineEvidence.priorProposalId,
        baselineEvidence.priorAssistantMessageIds,
        true,
      );
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) finishAction();
    }
  };

  const retryTurn = async () => {
    const turnId = calibration?.pending_turn?.id;
    if (!turnId || !beginAction("retry")) return;
    const generation = ++calibrationGenerationRef.current;
    const baselineEvidence = calibrationOperationBaseline(calibrationRef.current);
    try {
      const state = await retryCalibrationTurn(turnId);
      const newDraft = isNewDraftProposal(state, baselineEvidence.priorProposalId);
      const appliedState = applyCalibrationState(state, generation, {
        acceptIncomingTurnId: turnId,
        acceptIncomingProposalId: newDraft ? state.latest_proposal?.id : undefined,
      });
      if (newDraft && appliedState?.latest_proposal?.status === "draft") {
        finishToSummary("proposal");
      }
    } catch (error) {
      await reloadCalibrationAfterFailure(
        generation,
        "turn",
        error,
        turnId,
        baselineEvidence.priorProposalId,
        baselineEvidence.priorAssistantMessageIds,
      );
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) finishAction();
    }
  };

  const requestProposal = async () => {
    const session = calibration?.active_session;
    if (!session || calibration?.pending_turn || !beginAction("request_proposal")) return;
    const generation = ++calibrationGenerationRef.current;
    const turnId = turnIdFactory();
    const baselineEvidence = calibrationOperationBaseline(calibrationRef.current);
    try {
      const state = await requestCalibrationProposal({
        turn_id: turnId,
        session_id: session.id,
      });
      const newDraft = isNewDraftProposal(state, baselineEvidence.priorProposalId);
      const appliedState = applyCalibrationState(state, generation, {
        acceptIncomingTurnId: turnId,
        acceptIncomingProposalId: newDraft ? state.latest_proposal?.id : undefined,
      });
      if (newDraft && appliedState?.latest_proposal?.status === "draft") {
        finishToSummary("proposal");
      }
    } catch (error) {
      await reloadCalibrationAfterFailure(
        generation,
        "proposal",
        error,
        turnId,
        baselineEvidence.priorProposalId,
        baselineEvidence.priorAssistantMessageIds,
      );
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) finishAction();
    }
  };

  const reconcileProposalMutationFailure = async (
    profileGeneration: number,
    calibrationGeneration: number,
    proposal: CalibrationProposal,
    preActionProfile: InvestorProfile,
    error: unknown,
    conflict: boolean,
  ) => {
    if (
      !mountedRef.current
      || profileGenerationRef.current !== profileGeneration
      || calibrationGenerationRef.current !== calibrationGeneration
    ) return;
    setOperationError({ scope: "proposal", error });
    if (conflict) {
      installProposalAuthority(proposal, "conflict");
      setProposalConflict(true);
    }
    setProfileStatus("loading");
    setProfileError(null);
    setProfileValuesCurrent(false);
    setEffectiveFactsCurrent(false);
    setCalibrationStatus("loading");
    setCalibrationError(null);
    const [profileResult, calibrationResult] = await Promise.allSettled([
      getInvestorProfile(),
      getCalibrationState(),
    ]);
    if (
      !mountedRef.current
      || profileGenerationRef.current !== profileGeneration
      || calibrationGenerationRef.current !== calibrationGeneration
    ) return;
    let appliedState: CalibrationState | null = null;
    if (calibrationResult.status === "fulfilled") {
      appliedState = applyCalibrationState(calibrationResult.value, calibrationGeneration);
    } else {
      setCalibrationStatus("failed");
      setCalibrationError(calibrationResult.reason);
    }

    const observedProposal = appliedState?.latest_proposal;
    const matchingTerminal = observedProposal?.id === proposal.id
      && observedProposal.status !== "draft"
      ? observedProposal
      : null;
    if (matchingTerminal?.status === "approved") {
      const expectedProfile = applyProposalPatch(preActionProfile, proposal);
      installProfileAuthority(expectedProfile, proposal);
      if (
        profileResult.status === "fulfilled"
        && profileCorroboratesProposalPatch(profileResult.value.profile, proposal)
      ) {
        applyProfileResponse(profileResult.value, profileGeneration);
      } else if (profileResult.status === "rejected") {
        setOperationError({ scope: "refresh", error: profileResult.reason });
      } else {
        setOperationError({
          scope: "refresh",
          error: PROFILE_AUTHORITY_UNCORROBORATED,
        });
      }
      setProposalConflict(false);
      setOutcome("approved");
      finishToSummary("proposal");
      return;
    }
    if (matchingTerminal?.status === "rejected") {
      installProfileAuthority(preActionProfile);
      if (profileResult.status === "fulfilled") {
        applyProfileResponse(profileResult.value, profileGeneration);
        setOperationError(profileAuthorityRef.current
          ? { scope: "status_refresh", error: PROFILE_AUTHORITY_UNCORROBORATED }
          : null);
        setProposalConflict(false);
        setOutcome("rejected");
        finishToSummary("proposal");
      } else {
        setProfileStatus("ready");
        setProfileError(null);
        setProfileValuesCurrent(true);
        setEffectiveFactsCurrent(false);
        setOperationError({ scope: "status_refresh", error: profileResult.reason });
        setProposalConflict(false);
        setOutcome("rejected");
        finishToSummary("proposal");
      }
      return;
    }

    if (profileResult.status === "fulfilled") {
      applyProfileResponse(profileResult.value, profileGeneration);
    } else {
      setProfileStatus("failed");
      setProfileError(profileResult.reason);
    }
    if (observedProposal?.id === proposal.id && observedProposal.status === "draft") {
      setMode("proposal");
    }
  };

  const approveProposal = async () => {
    if (
      !pendingProposal
      || !profileResponse
      || proposalConflict
      || pendingProposal.conflict_fields.length > 0
      || !beginAction("approve")
    ) return;
    const proposal = pendingProposal;
    const preActionProfile = cloneProfile(profileResponse.profile);
    const profileGeneration = ++profileGenerationRef.current;
    const calibrationGeneration = ++calibrationGenerationRef.current;
    setProposalConflict(false);
    try {
      const approved = await approveCalibrationProposal(proposal.id);
      if (
        !mountedRef.current
        || profileGenerationRef.current !== profileGeneration
        || calibrationGenerationRef.current !== calibrationGeneration
      ) return;
      installProfileAuthority(approved.profile);
      installProposalAuthority(approved.proposal, "terminal");
      setOutcome("approved");
      finishToSummary("proposal");
      const [profileResult, calibrationResult] = await Promise.allSettled([
        getInvestorProfile(),
        getCalibrationState(),
      ]);
      if (
        !mountedRef.current
        || profileGenerationRef.current !== profileGeneration
        || calibrationGenerationRef.current !== calibrationGeneration
      ) return;
      if (profileResult.status === "fulfilled") {
        applyProfileResponse(profileResult.value, profileGeneration);
        if (profileAuthorityRef.current) {
          setOperationError({
            scope: "refresh",
            error: PROFILE_AUTHORITY_UNCORROBORATED,
          });
        }
      } else if (mountedRef.current && profileGenerationRef.current === profileGeneration) {
        setOperationError({ scope: "refresh", error: profileResult.reason });
      }
      if (calibrationResult.status === "fulfilled") {
        applyCalibrationState(calibrationResult.value, calibrationGeneration);
      } else if (
        mountedRef.current
        && calibrationGenerationRef.current === calibrationGeneration
      ) {
        setCalibrationStatus("failed");
        setCalibrationError(calibrationResult.reason);
      }
    } catch (error) {
      if (
        !mountedRef.current
        || profileGenerationRef.current !== profileGeneration
        || calibrationGenerationRef.current !== calibrationGeneration
      ) return;
      const presentation = settingsErrorPresentation(error, t);
      await reconcileProposalMutationFailure(
        profileGeneration,
        calibrationGeneration,
        proposal,
        preActionProfile,
        error,
        presentation.code === "proposal_conflict",
      );
    } finally {
      if (
        mountedRef.current
        && profileGenerationRef.current === profileGeneration
        && calibrationGenerationRef.current === calibrationGeneration
      ) finishAction();
    }
  };

  const rejectProposal = async () => {
    if (!pendingProposal || !profileResponse || !beginAction("reject")) return;
    const proposal = pendingProposal;
    const preActionProfile = cloneProfile(profileResponse.profile);
    const profileGeneration = ++profileGenerationRef.current;
    const calibrationGeneration = ++calibrationGenerationRef.current;
    try {
      const rejected = await rejectCalibrationProposal(proposal.id);
      if (
        !mountedRef.current
        || profileGenerationRef.current !== profileGeneration
        || calibrationGenerationRef.current !== calibrationGeneration
      ) return;
      installProfileAuthority(preActionProfile);
      installProposalAuthority(rejected.proposal, "terminal");
      setProfileStatus("ready");
      setProfileError(null);
      setProfileValuesCurrent(true);
      setEffectiveFactsCurrent(false);
      const [profileResult, calibrationResult] = await Promise.allSettled([
        getInvestorProfile(),
        getCalibrationState(),
      ]);
      if (
        !mountedRef.current
        || profileGenerationRef.current !== profileGeneration
        || calibrationGenerationRef.current !== calibrationGeneration
      ) return;
      if (profileResult.status === "fulfilled") {
        applyProfileResponse(profileResult.value, profileGeneration);
        if (profileAuthorityRef.current) {
          setOperationError({
            scope: "status_refresh",
            error: PROFILE_AUTHORITY_UNCORROBORATED,
          });
        }
      } else if (mountedRef.current && profileGenerationRef.current === profileGeneration) {
        setProfileStatus("ready");
        setProfileError(null);
        setProfileValuesCurrent(true);
        setEffectiveFactsCurrent(false);
        setOperationError({ scope: "status_refresh", error: profileResult.reason });
      }
      if (calibrationResult.status === "fulfilled") {
        applyCalibrationState(calibrationResult.value, calibrationGeneration);
      } else if (
        mountedRef.current
        && calibrationGenerationRef.current === calibrationGeneration
      ) {
        setCalibrationStatus("failed");
        setCalibrationError(calibrationResult.reason);
      }
      setProposalConflict(false);
      setOutcome("rejected");
      finishToSummary("proposal");
    } catch (error) {
      if (
        mountedRef.current
        && profileGenerationRef.current === profileGeneration
        && calibrationGenerationRef.current === calibrationGeneration
      ) {
        await reconcileProposalMutationFailure(
          profileGeneration,
          calibrationGeneration,
          proposal,
          preActionProfile,
          error,
          false,
        );
      }
    } finally {
      if (
        mountedRef.current
        && profileGenerationRef.current === profileGeneration
        && calibrationGenerationRef.current === calibrationGeneration
      ) finishAction();
    }
  };

  const setDraftField = <K extends keyof InvestorProfile>(key: K, value: InvestorProfile[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  };

  const profileErrorPresentation = profileError
    ? settingsErrorPresentation(profileError, t)
    : null;
  const calibrationErrorPresentation = calibrationError
    ? settingsErrorPresentation(calibrationError, t)
    : null;
  const operationErrorPresentation = operationError
    ? settingsErrorPresentation(operationError.error, t)
    : null;
  const providerMissing = operationErrorPresentation?.code === "provider_config_missing";
  const conflictError = operationErrorPresentation?.code === "proposal_conflict";

  const unknownTopicDiagnostics = useMemo(() => {
    if (!calibration) return [];
    const known = new Set<string>(CALIBRATION_TOPIC_IDS);
    const ids = [
      ...calibration.topic_catalog,
      ...(calibration.active_session?.covered_topics ?? []),
      calibration.active_session?.current_topic_id,
      ...(calibration.latest_proposal?.covered_topics ?? []),
    ];
    return [...new Set(ids.filter((id): id is string => Boolean(id) && !known.has(id as string)))];
  }, [calibration]);

  const diagnostics = [
    profileErrorPresentation?.diagnostic,
    calibrationErrorPresentation?.diagnostic,
    operationErrorPresentation?.diagnostic,
    calibration?.pending_turn?.diagnostic,
    ...unknownTopicDiagnostics,
  ].map(boundedDiagnostic);

  const outcomeLabel = outcome === "draft"
    ? t(($) => $.investor.draft.success)
    : outcome === "saved"
      ? t(($) => $.investor.saveSuccess)
      : outcome === "approved"
        ? t(($) => $.investor.workspace.proposal.approved)
        : outcome === "rejected"
          ? t(($) => $.investor.workspace.proposal.rejected)
          : null;

  if (profileStatus !== "ready" || !profileResponse || !draft) {
    return (
      <div className="investor-profile-panel">
        <h3>{t(($) => $.registry.sections.investorProfile.title)}</h3>
        {profileStatus === "failed" ? (
          <InlineAlert
            state="failed"
            title={t(($) => $.investor.workspace.errors.profileLoad)}
            action={(
              <Button size="compact" onClick={() => void retryProfileLoad()}>
                {t(($) => $.actions.retry)}
              </Button>
            )}
          />
        ) : (
          <StatusBadge state="loading" label={t(($) => $.investor.panel.loading)} />
        )}
        {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}
      </div>
    );
  }

  return (
    <div className="investor-profile-panel" aria-busy={busy || undefined}>
      {busy ? (
        <StatusBadge state="running" label={t(($) => $.investor.panel.updating)} />
      ) : null}

      {mode === "summary" ? (
        <InvestorProfileSummary
          response={profileResponse}
          effectiveFactsCurrent={effectiveFactsCurrent}
          calibration={calibration}
          calibrationStatus={calibrationStatus}
          busy={busy}
          refreshing={busyAction === "calibration_load"}
          headingRef={summaryHeadingRef}
          editCommandRef={editCommandRef}
          calibrationCommandRef={calibrationCommandRef}
          proposalCommandRef={proposalCommandRef}
          onEdit={enterEdit}
          onCalibration={() => {
            if (calibration?.active_session) continueCalibration();
            else void startCalibration();
          }}
          onReviewProposal={() => {
            if (!pendingProposal || busy) return;
            setReturnCommand("proposal");
            setMode("proposal");
            setOperationError(null);
            setOutcome(null);
          }}
          onRetryCalibration={() => void retryCalibrationLoad()}
          t={t}
        />
      ) : null}

      {mode === "edit" ? (
        <InvestorProfileEdit
          profile={draft}
          busy={busy}
          headingRef={editHeadingRef}
          backButtonRef={editBackRef}
          onChange={setDraftField}
          onDraft={() => void runDraft()}
          onSave={() => void saveProfile()}
          onBack={() => requestSummary("edit")}
          t={t}
        />
      ) : null}

      {mode === "calibration" && calibration ? (
        <InvestorProfileCalibration
          state={calibration}
          answer={answer}
          busy={busy}
          authorityConfirmed={calibrationStatus === "ready"}
          refreshing={busyAction === "calibration_load"}
          headingRef={calibrationHeadingRef}
          backButtonRef={calibrationBackRef}
          onAnswerChange={setAnswer}
          onSend={() => void sendAnswer()}
          onRetry={() => void retryTurn()}
          onRefreshStatus={() => void retryCalibrationLoad()}
          onRequestProposal={() => void requestProposal()}
          onBack={() => requestSummary("calibration")}
          t={t}
        />
      ) : null}

      {mode === "proposal" && calibrationStatus === "ready" && pendingProposal ? (
        <InvestorProfileProposalReview
          profile={profileResponse.profile}
          proposal={pendingProposal}
          currentValuesCurrent={profileValuesCurrent}
          busy={busy}
          conflict={proposalConflict}
          headingRef={proposalHeadingRef}
          backButtonRef={proposalBackRef}
          onApprove={() => void approveProposal()}
          onReject={() => void rejectProposal()}
          onBack={() => requestSummary("proposal")}
          t={t}
        />
      ) : null}

      {mode !== "summary" && calibrationStatus === "failed" ? (
        <InlineAlert
          state="partial"
          title={t(($) => $.investor.workspace.errors.calibrationLoad)}
          action={(
            <Button
              size="compact"
              disabled={busyAction === "calibration_load"}
              onClick={() => void retryCalibrationLoad()}
            >
              {t(($) => $.actions.retry)}
            </Button>
          )}
        />
      ) : null}

      {blockedNotice ? (
        <InlineAlert state="blocked" title={t(($) => $.investor.workspace.guard.busy)} />
      ) : null}
      {outcomeLabel ? <InlineAlert state="ready" title={outcomeLabel} /> : null}
      {operationError && !conflictError ? (
        <InlineAlert
          state="failed"
          title={providerMissing
            ? t(($) => $.investor.workspace.calibration.noCredential)
            : operationErrorTitle(operationError.scope, t)}
          action={providerMissing && onNavigateToProviders ? (
            <Button size="compact" onClick={onNavigateToProviders}>
              {t(($) => $.registry.sections.providers.title)}
            </Button>
          ) : operationError.scope === "refresh" || operationError.scope === "status_refresh" ? (
            <Button size="compact" onClick={() => void retryProfileLoad()}>
              {t(($) => $.actions.retry)}
            </Button>
          ) : undefined}
        />
      ) : null}
      {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}

      <ConfirmDialog
        open={confirmDiscard}
        title={t(($) => $.investor.workspace.guard.dirtyTitle)}
        consequence={t(($) => $.investor.workspace.guard.dirtyDescription)}
        confirmLabel={t(($) => $.investor.workspace.guard.discard)}
        cancelLabel={t(($) => $.investor.workspace.guard.stay)}
        returnFocusRef={dialogReturnFocusRef}
        fallbackFocusRef={editCommandRef}
        onCancel={() => {
          setConfirmDiscard(false);
          if (pendingSummaryAckRef.current !== null) {
            const sequence = pendingSummaryAckRef.current;
            pendingSummaryAckRef.current = null;
            onSummaryRequestHandled?.(sequence, false);
          }
        }}
        onConfirm={() => {
          setConfirmDiscard(false);
          setDraft(cloneProfile(baseline ?? profileResponse.profile));
          finishToSummary("edit");
          if (pendingSummaryAckRef.current !== null) {
            setSummaryCommitSequence(pendingSummaryAckRef.current);
          }
        }}
      />
    </div>
  );
}
