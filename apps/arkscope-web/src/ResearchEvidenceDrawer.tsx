import { useEffect, useMemo, useState, type RefObject } from "react";

import { getResearchRun, getResearchRunEvents, type ResearchRunDTO } from "./api";
import { MODEL_UX_LABELS } from "./modelRoutingUx";
import { stanceLabel } from "./personalizationDisplay";
import { ResearchPersonalizationContext } from "./ResearchPersonalizationContext";
import { sanitizeResearchDiagnostic } from "./researchErrors";
import type { Message, ToolTraceRow, TraceRow } from "./researchReducer";
import { formatSystemTimestamp } from "./timeDisplay";
import { Drawer, InlineAlert, StatusBadge } from "./ui";

interface EvidenceRow {
  name: string;
  input?: unknown;
  resultPreview?: string;
  completion: "complete" | "running" | "recorded";
}

export function researchEvidenceRows(
  message: Message | null,
  activeTrace: readonly TraceRow[],
): EvidenceRow[] {
  if (activeTrace.length > 0) {
    return activeTrace
      .filter((row): row is ToolTraceRow => row.kind === "tool")
      .map((row) => ({
        name: row.name,
        input: row.input,
        resultPreview: row.result_preview,
        completion: row.done ? "complete" : "running",
      }));
  }
  return (message?.tool_calls ?? []).map((call) => ({
    name: call.name,
    input: call.input,
    resultPreview: call.result_preview,
    completion: "recorded",
  }));
}

function authContext(run: ResearchRunDTO): string | null {
  const mode = run.auth_mode;
  if (!mode) return null;
  const label = MODEL_UX_LABELS.authModes[mode] ?? mode;
  const subscription = mode === "chatgpt_oauth" || mode === "claude_code_oauth";
  return `${label} · ${subscription ? "使用訂閱額度，非 API 帳單" : "使用 API 額度，會計入 API 帳單"}`;
}

function effortLabel(value: string | null | undefined, fallback: string): string {
  if (value === "default") return "Provider 預設";
  return value || fallback;
}

function boundedPreview(value: string | undefined): string | null {
  if (!value) return null;
  return value.length > 500 ? `${value.slice(0, 500)}…` : value;
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "[unserializable]";
  }
}

function tokenLabel(key: string): string {
  const normalized = key.toLowerCase();
  if (normalized.includes("cache_creation") || normalized.includes("cache_write")) return "快取寫入 tokens";
  if (normalized.includes("cache_read") || normalized.includes("cached")) return "快取讀取 tokens";
  if (normalized.includes("total_input")) return "總輸入 tokens";
  if (normalized.includes("total_output")) return "總輸出 tokens";
  if (normalized.includes("last_input")) return "最近一輪輸入 tokens";
  if (normalized === "total_tokens") return "總 tokens";
  if (normalized.includes("input") || normalized.includes("prompt")) return "輸入 tokens";
  if (normalized.includes("output") || normalized.includes("completion")) return "輸出 tokens";
  return key.replaceAll("_", " ");
}

function tokenRows(tokenUsage: Record<string, number> | null | undefined) {
  if (!tokenUsage) return [];
  return Object.entries(tokenUsage)
    .filter(([key, value]) => (
      Number.isFinite(value)
      && /(input|output|prompt|completion|cache|total).*token|token.*(input|output|prompt|completion|cache|total)/i.test(key)
    ))
    .map(([key, value]) => ({ key, label: tokenLabel(key), value }));
}

export function ResearchEvidenceDrawer({
  open,
  pinned,
  onClose,
  onPinnedChange,
  returnFocusRef,
  message,
  activeTrace,
  activeRun,
  developerMode,
}: {
  open: boolean;
  pinned: boolean;
  onClose: () => void;
  onPinnedChange: (pinned: boolean) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  message: Message | null;
  activeTrace: readonly TraceRow[];
  activeRun: ResearchRunDTO | null;
  developerMode: boolean;
}) {
  const evidence = useMemo(
    () => researchEvidenceRows(message, activeTrace),
    [activeTrace, message],
  );
  const hasEvidence = evidence.length > 0;
  // A selected transcript turn owns its exact linkage. Never borrow a newer
  // active/latest run for a legacy message that has no persisted run_id.
  const runId = message ? (message.runId ?? null) : (activeRun?.id ?? null);
  const [runDetail, setRunDetail] = useState<ResearchRunDTO | null>(null);
  const [detailState, setDetailState] = useState<"idle" | "loading" | "ready" | "partial">("idle");
  const [diagnostic, setDiagnostic] = useState<string | null>(null);
  const [diagnosticLoading, setDiagnosticLoading] = useState(false);

  useEffect(() => {
    if (!open || !runId) {
      setRunDetail(null);
      setDetailState("idle");
      setDiagnostic(null);
      return;
    }
    let alive = true;
    setRunDetail(null);
    setDetailState("loading");
    void getResearchRun(runId)
      .then(({ run }) => {
        if (!alive) return;
        setRunDetail(run);
        setDetailState("ready");
      })
      .catch(() => {
        if (!alive) return;
        setDetailState("partial");
      });
    return () => { alive = false; };
  }, [open, runId]);

  useEffect(() => {
    if (!open || !runId || activeRun?.id !== runId) return;
    setRunDetail(activeRun);
  }, [activeRun, open, runId]);

  const loadDiagnostics = () => {
    if (!developerMode || !runId || diagnostic != null || diagnosticLoading) return;
    setDiagnosticLoading(true);
    void getResearchRunEvents(runId, 0)
      .then((response) => {
        const safe = response.events.map((event) => ({
          seq: event.seq,
          type: event.type,
          created_at: event.created_at,
          data: event.data,
        }));
        setDiagnostic(sanitizeResearchDiagnostic(safeJson(safe), 8_000));
      })
      .catch(() => setDiagnostic("無法載入診斷事件。"))
      .finally(() => setDiagnosticLoading(false));
  };

  const details = runDetail ?? (activeRun?.id === runId ? activeRun : null);
  const usage = details?.token_usage ?? message?.token_usage ?? null;
  const personalization = message?.personalization ?? null;
  const personalizationContext = message?.personalization ?? details?.personalization ?? null;
  const hasTranscriptDetails = Boolean(details || message);

  return (
    <Drawer
      open={open}
      title="證據與執行詳情"
      onClose={onClose}
      returnFocusRef={returnFocusRef}
      pinnable={hasEvidence}
      pinned={pinned && hasEvidence}
      onPinnedChange={onPinnedChange}
    >
      <div className="research-evidence" data-has-evidence={String(hasEvidence)}>
        <section>
          <h3 className="surface-title tiny">工具證據</h3>
          {hasEvidence ? (
            <ul className="research-evidence-list">
              {evidence.map((row, index) => (
                <li key={`${row.name}-${index}`} className="research-evidence-tool">
                  <div className="research-evidence-tool-head">
                    <span className="mono">{row.name}</span>
                    <StatusBadge
                      state={row.completion === "running" ? "running" : "ready"}
                      label={row.completion === "running" ? "執行中" : row.completion === "complete" ? "完成" : "已記錄"}
                    />
                  </div>
                  {row.input !== undefined ? (
                    <pre className="research-evidence-input mono tiny muted">{safeJson(row.input)}</pre>
                  ) : null}
                  {boundedPreview(row.resultPreview) ? (
                    <div className="research-evidence-preview tiny muted">{boundedPreview(row.resultPreview)}</div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted tiny">此回合沒有可用的工具證據紀錄</p>
          )}
        </section>

        <section className="research-run-details">
          <h3 className="surface-title tiny">執行詳情</h3>
          {!runId ? <p className="muted tiny">此舊回合沒有精確 run 連結</p> : null}
          {detailState === "loading" && !details ? <p className="muted tiny">載入執行詳情…</p> : null}
          {detailState === "partial" ? (
            <InlineAlert state="partial" title="執行詳情只載入了一部分">
              對話內容與已保存的工具紀錄仍然可用。
            </InlineAlert>
          ) : null}
          {hasTranscriptDetails ? (
            <dl className="research-run-detail-list">
              {details ? (
                <div><dt>路線</dt><dd>{details.provider} · {details.model} · {effortLabel(details.effort, "Provider 預設")}</dd></div>
              ) : message?.provider || message?.model || message?.effort ? (
                <div><dt>路線</dt><dd>{message.provider ?? "未知"} · {message.model ?? "未知"} · {effortLabel(message.effort, "未知")}</dd></div>
              ) : null}
              {details && authContext(details) ? <div><dt>登入與額度</dt><dd>{authContext(details)}</dd></div> : null}
              {details ? <div><dt>建立</dt><dd>{formatSystemTimestamp(details.created_at)}</dd></div> : null}
              {details ? <div><dt>開始</dt><dd>{formatSystemTimestamp(details.started_at)}</dd></div> : null}
              {details ? <div><dt>完成</dt><dd>{formatSystemTimestamp(details.completed_at)}</dd></div> : null}
              {!details && message?.created_at ? <div><dt>回合保存</dt><dd>{formatSystemTimestamp(message.created_at)}</dd></div> : null}
              {message?.elapsed_seconds != null ? <div><dt>模型耗時</dt><dd>{message.elapsed_seconds.toFixed(1)}s</dd></div> : null}
              {personalization?.profile_active && personalization.assistant_stance !== "off" ? (
                <div><dt>立場</dt><dd>{stanceLabel(personalization.assistant_stance)}</dd></div>
              ) : null}
              {personalization?.applied_skills?.length ? (
                <div><dt>套用技能</dt><dd>{personalization.applied_skills.join("、")}</dd></div>
              ) : null}
              {(message?.tools_used?.length ?? 0) > 0 ? (
                <div><dt>工具</dt><dd>{message!.tools_used.join("、")}</dd></div>
              ) : null}
              {tokenRows(usage).map((row) => (
                <div key={row.key}><dt>{row.label}</dt><dd>{row.value.toLocaleString()}</dd></div>
              ))}
            </dl>
          ) : null}
          <ResearchPersonalizationContext trace={personalizationContext} />
          {developerMode && runId ? (
            <details
              className="research-diagnostic"
              onToggle={(event) => { if (event.currentTarget.open) loadDiagnostics(); }}
            >
              <summary>診斷事件</summary>
              {diagnosticLoading ? <p className="muted tiny">載入中…</p> : null}
              {diagnostic ? <pre>{diagnostic}</pre> : null}
            </details>
          ) : null}
        </section>
      </div>
    </Drawer>
  );
}
