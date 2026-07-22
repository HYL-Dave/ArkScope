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
  type CalibrationState,
  type InvestorProfile,
  type InvestorProfileResponse,
} from "./api";
import { DeveloperDiagnostics } from "./settings/DeveloperDiagnostics";
import { InvestorProfileCalibration } from "./settings/investor/InvestorProfileCalibration";
import { InvestorProfileEdit } from "./settings/investor/InvestorProfileEdit";
import { InvestorProfileProposalReview } from "./settings/investor/InvestorProfileProposalReview";
import { InvestorProfileSummary } from "./settings/investor/InvestorProfileSummary";
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
  turnIdFactory?: () => string;
}

type InvestorMode = "summary" | "edit" | "calibration" | "proposal";
type ReturnCommand = "edit" | "calibration" | "proposal";
type BusyAction =
  | "draft"
  | "save"
  | "calibration_load"
  | "calibration_start"
  | "turn"
  | "retry"
  | "request_proposal"
  | "approve"
  | "reject";
type ErrorScope = "save" | "refresh" | "turn" | "proposal";

interface OperationError {
  scope: ErrorScope;
  error: unknown;
}

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

function defaultTurnId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID();
  return `calibration-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function boundedDiagnostic(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.slice(0, 512);
}

function operationErrorTitle(scope: ErrorScope, t: SettingsT): string {
  switch (scope) {
    case "save":
      return t(($) => $.investor.workspace.errors.save);
    case "refresh":
      return t(($) => $.investor.workspace.errors.refresh);
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
  turnIdFactory = defaultTurnId,
}: InvestorProfilePanelProps) {
  const { t } = useTranslation("settings");
  const mountedRef = useRef(false);
  const calibrationGenerationRef = useRef(0);
  const lastTurnIdRef = useRef<string | null>(null);

  const [profileStatus, setProfileStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [profileResponse, setProfileResponse] = useState<InvestorProfileResponse | null>(null);
  const [profileError, setProfileError] = useState<unknown>(null);
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

  const applyCalibrationState = useCallback((state: CalibrationState, generation: number) => {
    if (!mountedRef.current || calibrationGenerationRef.current !== generation) return false;
    setCalibration(state);
    setCalibrationStatus("ready");
    setCalibrationError(null);
    if (state.pending_turn) lastTurnIdRef.current = state.pending_turn.id;
    return true;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const generation = calibrationGenerationRef.current;
    const profileRequest = getInvestorProfile().then((response) => {
      if (!mountedRef.current) return;
      setProfileResponse(response);
      setDraft(cloneProfile(response.profile));
      setBaseline(cloneProfile(response.profile));
      setProfileStatus("ready");
      setProfileError(null);
    }).catch((error: unknown) => {
      if (!mountedRef.current) return;
      setProfileStatus("failed");
      setProfileError(error);
    });
    const calibrationRequest = getCalibrationState().then((state) => {
      applyCalibrationState(state, generation);
    }).catch((error: unknown) => {
      if (!mountedRef.current || calibrationGenerationRef.current !== generation) return;
      setCalibrationStatus("failed");
      setCalibrationError(error);
    });
    void Promise.allSettled([profileRequest, calibrationRequest]);
    return () => {
      mountedRef.current = false;
    };
  }, [applyCalibrationState]);

  const dirty = mode === "edit" && !sameEditableProfile(draft, baseline);
  const busy = busyAction !== null;

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
      const target = returnCommand === "edit"
        ? editCommandRef.current
        : returnCommand === "calibration"
          ? calibrationCommandRef.current
          : proposalCommandRef.current;
      (target ?? summaryHeadingRef.current)?.focus();
    }
  }, [mode, returnCommand]);

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
    if (busy) {
      setBlockedNotice(true);
      return false;
    }
    setBusyAction(action);
    setOperationError(null);
    setBlockedNotice(false);
    setOutcome(null);
    return true;
  };

  const finishToSummary = (command: ReturnCommand) => {
    setReturnCommand(command);
    setMode("summary");
    setBlockedNotice(false);
  };

  const requestSummary = (command: ReturnCommand) => {
    if (busy) {
      setBlockedNotice(true);
      return;
    }
    if (mode === "edit" && dirty) {
      dialogReturnFocusRef.current = editBackRef.current;
      setConfirmDiscard(true);
      return;
    }
    finishToSummary(command);
  };

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
    try {
      const state = await getCalibrationState();
      applyCalibrationState(state, generation);
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setCalibrationStatus("failed");
        setCalibrationError(error);
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
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
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
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
      if (mountedRef.current) setBusyAction(null);
    }
  };

  const saveProfile = async () => {
    if (!draft || !beginAction("save")) return;
    try {
      const saved = await saveInvestorProfile(profilePayload(draft));
      if (!mountedRef.current) return;
      setDraft(cloneProfile(saved.profile));
      setBaseline(cloneProfile(saved.profile));
      let refreshed: InvestorProfileResponse;
      try {
        refreshed = await getInvestorProfile();
      } catch (error) {
        if (mountedRef.current) setOperationError({ scope: "refresh", error });
        return;
      }
      if (!mountedRef.current) return;
      setProfileResponse(refreshed);
      setDraft(cloneProfile(refreshed.profile));
      setBaseline(cloneProfile(refreshed.profile));
      setOutcome("saved");
      finishToSummary("edit");
    } catch (error) {
      if (mountedRef.current) setOperationError({ scope: "save", error });
    } finally {
      if (mountedRef.current) setBusyAction(null);
    }
  };

  const sendAnswer = async () => {
    const session = calibration?.active_session;
    if (!session || !answer.trim() || !beginAction("turn")) return;
    const generation = ++calibrationGenerationRef.current;
    const turnId = turnIdFactory();
    lastTurnIdRef.current = turnId;
    try {
      const state = await sendCalibrationMessage({
        turn_id: turnId,
        session_id: session.id,
        content: answer,
      });
      if (!applyCalibrationState(state, generation)) return;
      setAnswer("");
      if (state.latest_proposal?.status === "draft") {
        setReturnCommand("proposal");
        setMode("proposal");
      }
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setOperationError({ scope: "turn", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
    }
  };

  const retryTurn = async () => {
    const turnId = calibration?.pending_turn?.id ?? lastTurnIdRef.current;
    if (!turnId || !beginAction("retry")) return;
    const generation = ++calibrationGenerationRef.current;
    try {
      const state = await retryCalibrationTurn(turnId);
      applyCalibrationState(state, generation);
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setOperationError({ scope: "turn", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
    }
  };

  const requestProposal = async () => {
    const session = calibration?.active_session;
    if (!session || !beginAction("request_proposal")) return;
    const generation = ++calibrationGenerationRef.current;
    const turnId = turnIdFactory();
    lastTurnIdRef.current = turnId;
    try {
      const state = await requestCalibrationProposal({
        turn_id: turnId,
        session_id: session.id,
      });
      if (applyCalibrationState(state, generation) && state.latest_proposal?.status === "draft") {
        setReturnCommand("proposal");
        setMode("proposal");
      }
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setOperationError({ scope: "proposal", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
    }
  };

  const approveProposal = async () => {
    if (!pendingProposal || !beginAction("approve")) return;
    const generation = ++calibrationGenerationRef.current;
    setProposalConflict(false);
    try {
      const approved = await approveCalibrationProposal(pendingProposal.id);
      if (!mountedRef.current || calibrationGenerationRef.current !== generation) return;
      setCalibration((current) => current
        ? { ...current, latest_proposal: approved.proposal }
        : current);
      const refreshedProfile = await getInvestorProfile();
      if (!mountedRef.current || calibrationGenerationRef.current !== generation) return;
      setProfileResponse(refreshedProfile);
      setDraft(cloneProfile(refreshedProfile.profile));
      setBaseline(cloneProfile(refreshedProfile.profile));
      try {
        const refreshedCalibration = await getCalibrationState();
        applyCalibrationState(refreshedCalibration, generation);
      } catch (error) {
        if (mountedRef.current && calibrationGenerationRef.current === generation) {
          setCalibrationStatus("failed");
          setCalibrationError(error);
        }
      }
      setOutcome("approved");
      finishToSummary("proposal");
    } catch (error) {
      if (!mountedRef.current || calibrationGenerationRef.current !== generation) return;
      const presentation = settingsErrorPresentation(error, t);
      if (presentation.code === "proposal_conflict") {
        setProposalConflict(true);
        setOperationError({ scope: "proposal", error });
        try {
          const refreshed = await getCalibrationState();
          applyCalibrationState(refreshed, generation);
        } catch {
          // The typed conflict is still actionable without replacing it with a load error.
        }
      } else {
        setOperationError({ scope: "refresh", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
    }
  };

  const rejectProposal = async () => {
    if (!pendingProposal || !beginAction("reject")) return;
    const generation = ++calibrationGenerationRef.current;
    try {
      await rejectCalibrationProposal(pendingProposal.id);
      const refreshed = await getCalibrationState();
      if (!applyCalibrationState(refreshed, generation)) return;
      setProposalConflict(false);
      setOutcome("rejected");
      finishToSummary("proposal");
    } catch (error) {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setOperationError({ scope: "proposal", error });
      }
    } finally {
      if (mountedRef.current && calibrationGenerationRef.current === generation) {
        setBusyAction(null);
      }
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
          <InlineAlert state="failed" title={t(($) => $.investor.workspace.errors.profileLoad)} />
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
          calibration={calibration}
          calibrationStatus={calibrationStatus}
          busy={busy}
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
          headingRef={calibrationHeadingRef}
          backButtonRef={calibrationBackRef}
          onAnswerChange={setAnswer}
          onSend={() => void sendAnswer()}
          onRetry={() => void retryTurn()}
          onRequestProposal={() => void requestProposal()}
          onBack={() => requestSummary("calibration")}
          t={t}
        />
      ) : null}

      {mode === "proposal" && pendingProposal ? (
        <InvestorProfileProposalReview
          profile={profileResponse.profile}
          proposal={pendingProposal}
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
        onCancel={() => setConfirmDiscard(false)}
        onConfirm={() => {
          setConfirmDiscard(false);
          setDraft(cloneProfile(baseline ?? profileResponse.profile));
          finishToSummary("edit");
        }}
      />
    </div>
  );
}
