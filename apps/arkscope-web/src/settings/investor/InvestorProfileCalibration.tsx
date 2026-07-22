import { ArrowLeft, RotateCw, Send, Sparkles } from "lucide-react";
import type { RefObject } from "react";

import type { CalibrationMessage, CalibrationState } from "../../api";
import { Button, InlineAlert, StatusBadge } from "../../ui";
import type { SettingsT } from "../settingsCopy";
import {
  calibrationPromptText,
  calibrationTopicDisplay,
  orderedCalibrationTopicDisplays,
} from "./investorProfileDisplay";

function messageSource(message: CalibrationMessage, t: SettingsT): string {
  return message.role === "assistant"
    ? calibrationPromptText(message.prompt_id, message.content, t)
    : message.content;
}

export interface InvestorProfileCalibrationProps {
  state: CalibrationState;
  answer: string;
  busy: boolean;
  headingRef: RefObject<HTMLHeadingElement>;
  backButtonRef: RefObject<HTMLButtonElement>;
  onAnswerChange: (value: string) => void;
  onSend: () => void;
  onRetry: () => void;
  onRequestProposal: () => void;
  onBack: () => void;
  t: SettingsT;
}

export function InvestorProfileCalibration({
  state,
  answer,
  busy,
  headingRef,
  backButtonRef,
  onAnswerChange,
  onSend,
  onRetry,
  onRequestProposal,
  onBack,
  t,
}: InvestorProfileCalibrationProps) {
  const session = state.active_session;
  const currentQuestion = state.messages.find(
    (message) => message.id === session?.current_question_message_id,
  ) ?? [...state.messages].reverse().find((message) => message.role === "assistant") ?? null;
  const covered = orderedCalibrationTopicDisplays(session?.covered_topics ?? [], t);
  const currentTopic = session?.current_topic_id
    ? calibrationTopicDisplay(session.current_topic_id, t)
    : null;
  const interrupted = state.pending_turn?.status === "interrupted"
    || state.pending_turn?.status === "failed";
  const unresolvedTurn = state.pending_turn !== null;

  return (
    <section className="ip-calibration">
      <div className="ip-actions">
        <Button
          ref={backButtonRef}
          icon={<ArrowLeft size={16} />}
          onClick={onBack}
        >
          {t(($) => $.investor.workspace.actions.backSummary)}
        </Button>
      </div>
      <h3 ref={headingRef} tabIndex={-1} data-investor-mode-heading="calibration">
        {t(($) => $.investor.workspace.mode.calibration)}
      </h3>
      <p className="muted">{t(($) => $.investor.workspace.calibration.description)}</p>

      <StatusBadge
        state={busy ? "running" : interrupted ? "interrupted" : "ready"}
        label={t(($) => $.investor.workspace.calibration.progress, {
          covered: session?.covered_topics.length ?? 0,
          total: state.topic_catalog.length,
        })}
      />

      <section>
        <h4>{t(($) => $.investor.workspace.calibration.current)}</h4>
        {currentTopic ? (
          <div>
            <strong>{currentTopic.label}</strong>
            {currentTopic.description ? <p className="muted">{currentTopic.description}</p> : null}
          </div>
        ) : null}
        {currentQuestion ? <blockquote>{messageSource(currentQuestion, t)}</blockquote> : null}
      </section>

      <section>
        <h4>{t(($) => $.investor.workspace.calibration.covered)}</h4>
        <div data-testid="calibration-covered-topics">
          {covered.map((topic, index) => (
            <span className="ip-chip" key={`${index}:${topic.id}`}>{topic.label}</span>
          ))}
        </div>
        <details data-testid="calibration-topics-disclosure">
          <summary>{t(($) => $.investor.workspace.disclosures.topicsTitle)}</summary>
          <p>{t(($) => $.investor.workspace.disclosures.topicsBody)}</p>
        </details>
      </section>

      {state.messages.length ? (
        <ol className="ip-calibration-log" data-testid="calibration-journal">
          {state.messages.map((message) => (
            <li key={message.id}>
              <strong>
                {message.role === "user"
                  ? t(($) => $.investor.calibration.user)
                  : t(($) => $.investor.calibration.assistant)}
              </strong>
              <div>{messageSource(message, t)}</div>
            </li>
          ))}
        </ol>
      ) : null}

      {interrupted ? (
        <InlineAlert
          state="interrupted"
          title={t(($) => $.investor.workspace.calibration.interrupted)}
        >
          <Button
            size="compact"
            icon={<RotateCw size={15} />}
            disabled={busy}
            onClick={onRetry}
          >
            {t(($) => $.investor.workspace.calibration.retry)}
          </Button>
        </InlineAlert>
      ) : null}

      <label>
        {t(($) => $.investor.workspace.calibration.answerLabel)}
        <textarea
          name="calibration_answer"
          aria-label={t(($) => $.investor.workspace.calibration.answerLabel)}
          placeholder={t(($) => $.investor.workspace.calibration.answerPlaceholder)}
          value={answer}
          disabled={busy || unresolvedTurn || !session}
          onChange={(event) => onAnswerChange(event.target.value)}
        />
      </label>
      <div className="ip-actions">
        <Button
          tone="primary"
          icon={<Send size={16} />}
          disabled={busy || unresolvedTurn || !session || !answer.trim()}
          onClick={onSend}
        >
          {busy
            ? t(($) => $.investor.workspace.calibration.sending)
            : t(($) => $.investor.workspace.calibration.send)}
        </Button>
        <Button
          icon={<Sparkles size={16} />}
          disabled={busy || unresolvedTurn || !session}
          onClick={onRequestProposal}
        >
          {t(($) => $.investor.workspace.actions.requestProposal)}
        </Button>
      </div>
      <p className="muted">{t(($) => $.investor.workspace.calibration.requestNow)}</p>
    </section>
  );
}
