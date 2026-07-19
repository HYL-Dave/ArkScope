import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  getProvidersConfig,
  getProvidersHealth,
  getSAExtensionHealth,
  getSchedule,
  importProviderConfigField,
  putProviderConfig,
  putSchedule,
  runScheduleNow,
  testProvider,
  type ProviderConfigEntry,
  type ProviderConfigField,
  type ProviderConfigSetupState,
  type ProviderHealth,
  type ProvidersHealthResponse,
  type SAExtensionHealthResponse,
  type ScheduleSourceState,
} from "../api";
import {
  providerHealthStatusLabel,
  schedulerBodyBacklogPresentation,
  schedulerStateLabel,
} from "../marketDataDisplay";
import { displaySAExtensionSegments } from "../saExtensionHealthDisplay";
import { SourceRunProgress } from "../SourceRunProgress";
import {
  durableScheduleCommonState,
  providerCommonState,
  saSegmentCommonState,
  scheduleSkipCommonState,
} from "../dataSourcesPresentation";
import {
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
  type DataSourceScheduleMap,
} from "../dataSourceSchedulePolling";
import { formatSystemTimestamp } from "../timeDisplay";
import { ConfirmDialog, StatusBadge } from "../ui";
import { shortTs } from "./DataStorageSection";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";

function providerConfigSourceLabel(source: string): string {
  if (source === "app") return "App";
  if (source === "env") return "環境變數";
  if (source === "config/.env") return "config/.env";
  if (source === "missing") return "未設定";
  return source;
}

function compactMessage(value: string, max = 88): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function shortDate(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 10) : "—";
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-US")
    : "—";
}

type FredSnapshotSignal = {
  available: boolean;
  series_count: number | null;
  observation_count: number | null;
  release_dates_count: number | null;
  latest_fetched_at: string | null;
};

function fredSnapshotFromSignals(signals: ProviderHealth["signals"] | undefined): FredSnapshotSignal | null {
  const raw = signals?.local_snapshot;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  const numberField = (key: string): number | null =>
    typeof obj[key] === "number" && Number.isFinite(obj[key]) ? obj[key] as number : null;
  return {
    available: obj.available === true,
    series_count: numberField("series_count"),
    observation_count: numberField("observation_count"),
    release_dates_count: numberField("release_dates_count"),
    latest_fetched_at: typeof obj.latest_fetched_at === "string" ? obj.latest_fetched_at : null,
  };
}

function boolSignal(signals: ProviderHealth["signals"] | undefined, key: string): boolean | null {
  const value = signals?.[key];
  return typeof value === "boolean" ? value : null;
}

function fredProviderDetail(p: ProviderHealth): string | null {
  if (p.id !== "fred") return null;
  const snap = fredSnapshotFromSignals(p.signals);
  const auto = boolSignal(p.signals, "auto_refresh_enabled");
  const parts: string[] = [];
  if (snap?.available) {
    parts.push(
      `資料快照可用：${formatCount(snap.series_count)} 序列 · ${formatCount(snap.observation_count)} 觀測值`,
    );
  } else {
    parts.push("尚無資料");
  }
  if (snap?.latest_fetched_at) parts.push(`最後抓取 ${shortDate(snap.latest_fetched_at)}`);
  parts.push(auto === true
    ? "自動刷新已啟用"
    : auto === false
      ? "自動刷新未啟用"
      : "自動刷新狀態未知");
  return parts.join(" · ");
}

// Derived client-id chips for the IBKR base field. Offsets/labels come from the
// BACKEND (single authority: data_sources/ibkr_client_id.py via the config view) —
// adding a domain there shows up here with no frontend change. A valid numeric
// draft previews post-save ids; otherwise the backend's effective ids are shown
// (parseInt would mis-preview "1abc"; the backend rejects such bases on save).
function ibkrClientIdChips(
  domains: NonNullable<ProviderConfigField["client_id_domains"]>,
  draft: string,
): { preview: boolean; text: string } {
  const s = draft.trim();
  const base = /^\d+$/.test(s) ? Number(s) : null;
  const text = domains
    .map((d) => `${d.label}=${base !== null ? base + d.offset : d.effective_id ?? "？"}`)
    .join("、");
  return { preview: base !== null, text };
}

function ProviderHealthState({ provider }: { provider: ProviderHealth }) {
  const state = providerCommonState(provider.status);
  return state === null
    ? <span className="muted tiny">{providerHealthStatusLabel(provider)}</span>
    : <StatusBadge state={state} label={providerHealthStatusLabel(provider)} />;
}

export function DataSourcesSection({
  onNavigationGuardChange,
}: {
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
}) {
  const [schedule, setSchedule] = useState<Record<string, ScheduleSourceState> | null>(null);
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(null);
  const [saExtensionHealth, setSaExtensionHealth] = useState<SAExtensionHealthResponse | null>(null);
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(null);
  const [cfgSetup, setCfgSetup] = useState<ProviderConfigSetupState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string>(""); // source id with an in-flight mutation
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const [pendingGuardedEdit, setPendingGuardedEdit] = useState<{
    provider: string;
    field: string;
    value: string;
    fieldMeta: ProviderConfigField;
  } | null>(null);
  const guardedEditTriggerRef = useRef<HTMLButtonElement>(null);
  const scheduleRef = useRef<DataSourceScheduleMap | null>(null);
  const scheduleRequestSequenceRef = useRef(0);
  const acceptedScheduleSequenceRef = useRef(0);
  const schedulePollInFlightRef = useRef<Promise<void> | null>(null);
  const dataSourcesMountedRef = useRef(true);
  const dirty = Object.values(drafts).some((value) => value !== "")
    || Object.values(keyDrafts).some((value) => value !== "")
    || pendingGuardedEdit !== null;
  const navigationBusy = busy !== "";

  useEffect(() => {
    onNavigationGuardChange?.({
      dirty,
      busy: navigationBusy,
      reason: navigationBusy
        ? "資料來源設定更新正在進行。"
        : dirty
          ? "資料來源與排程有未儲存的變更。"
          : null,
    });
  }, [dirty, navigationBusy, onNavigationGuardChange]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  useEffect(() => {
    dataSourcesMountedRef.current = true;
    return () => {
      dataSourcesMountedRef.current = false;
    };
  }, []);

  const acceptSchedule = useCallback((
    next: DataSourceScheduleMap,
    sequence: number,
  ): { accepted: boolean; lifecycleChanged: boolean } => {
    if (sequence < acceptedScheduleSequenceRef.current) {
      return { accepted: false, lifecycleChanged: false };
    }
    acceptedScheduleSequenceRef.current = sequence;
    const previous = scheduleRef.current;
    scheduleRef.current = next;
    setSchedule(next);
    return {
      accepted: true,
      lifecycleChanged: dataSourceScheduleLifecycleChanged(previous, next),
    };
  }, []);

  const load = useCallback(async () => {
    const scheduleSequence = ++scheduleRequestSequenceRef.current;
    const [rs, rh, rc] = await Promise.allSettled([
      getSchedule(), getProvidersHealth(), getProvidersConfig()]);
    if (!dataSourcesMountedRef.current) return;
    if (rs.status === "fulfilled") acceptSchedule(rs.value.sources, scheduleSequence);
    if (rh.status === "fulfilled") setHealth(rh.value);
    if (rc.status === "fulfilled") {
      setCfg(rc.value.providers);
      setCfgSetup(rc.value.setup);
    }
    const bad = [rs, rh, rc].filter((r): r is PromiseRejectedResult => r.status === "rejected");
    setErr(bad.length
      ? bad.map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason))).join("；")
      : null);
  }, [acceptSchedule]);

  const pollSchedule = useCallback((): Promise<void> => {
    if (schedulePollInFlightRef.current) return schedulePollInFlightRef.current;
    const sequence = ++scheduleRequestSequenceRef.current;
    const request = (async () => {
      try {
        const next = await getSchedule();
        if (!dataSourcesMountedRef.current) return;
        const accepted = acceptSchedule(next.sources, sequence);
        if (accepted.accepted && accepted.lifecycleChanged) {
          await load();
        }
      } catch {
        // Passive polling preserves the last accepted schedule truth.
      }
    })().finally(() => {
      if (schedulePollInFlightRef.current === request) {
        schedulePollInFlightRef.current = null;
      }
    });
    schedulePollInFlightRef.current = request;
    return request;
  }, [acceptSchedule, load]);

  useEffect(() => {
    void load();
  }, [load]);

  // Extension health spawns a native-host subprocess server-side — fetch once
  // on mount and via the manual 重新檢查 button only, NEVER on the 5s
  // scheduler-status poll.
  useEffect(() => {
    let cancelled = false;
    getSAExtensionHealth()
      .then((v) => {
        if (!cancelled) setSaExtensionHealth(v);
      })
      .catch(() => {
        if (!cancelled) setSaExtensionHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Discover background starts while idle, then observe active runs more closely.
  const anyRunning = !!schedule && Object.values(schedule).some((s) => s.running);
  const schedulePollIntervalMs = dataSourceSchedulePollMs(schedule);
  useEffect(() => {
    const timer = window.setInterval(
      () => { void pollSchedule(); },
      schedulePollIntervalMs,
    );
    const onFocus = () => { void pollSchedule(); };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [pollSchedule, schedulePollIntervalMs]);

  async function setEnabled(source: string, enabled: boolean) {
    if (busy) return;
    setBusy(source);
    try {
      await putSchedule(source, { enabled });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function applyInterval(source: string) {
    const raw = drafts[source];
    const n = Number(raw);
    if (!raw || !Number.isFinite(n)) return;
    if (busy) return;
    setBusy(source);
    try {
      await putSchedule(source, { interval_minutes: Math.round(n) });
      setDrafts((d) => ({ ...d, [source]: "" }));
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runNow(source: string) {
    if (busy) return;
    setBusy(source);
    try {
      const r = await runScheduleNow(source);
      if (r.status === "skipped") setErr(`${source}: ${r.reason ?? "已在執行"}`);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function importField(provider: string, field: string, sourceEnvVar: string | null) {
    if (busy) return;
    setBusy(`import.${provider}.${field}`);
    try {
      await importProviderConfigField(provider, field, sourceEnvVar);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function commitField(
    provider: string,
    field: string,
    value: string | null,
    fieldMeta?: ProviderConfigField,
  ): Promise<boolean> {
    if (busy) return false;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(
        provider,
        { [field]: value },
        fieldMeta?.guarded ? { [field]: true } : undefined,
      );
      setKeyDrafts((d) => ({ ...d, [`${provider}.${field}`]: "" }));
      await load();
      return true;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      setBusy("");
    }
  }

  async function saveField(
    provider: string,
    field: string,
    value: string | null,
    fieldMeta?: ProviderConfigField,
  ) {
    if (busy) return;
    if (fieldMeta?.guarded && value !== null) {
      setPendingGuardedEdit({ provider, field, value, fieldMeta });
      return;
    }
    await commitField(provider, field, value, fieldMeta);
  }

  async function confirmGuardedEdit() {
    if (!pendingGuardedEdit || busy) return;
    const saved = await commitField(
      pendingGuardedEdit.provider,
      pendingGuardedEdit.field,
      pendingGuardedEdit.value,
      pendingGuardedEdit.fieldMeta,
    );
    if (saved) setPendingGuardedEdit(null);
  }

  async function runTest(provider: string) {
    if (busy) return;
    setBusy(`test.${provider}`);
    setTestResults((t) => ({ ...t, [provider]: "測試中…" }));
    try {
      const r = await testProvider(provider);
      setTestResults((t) => ({
        ...t,
        [provider]:
          r.ok === true
            ? `✓ ${r.detail}${r.latency_ms != null ? ` · ${r.latency_ms}ms` : ""}`
            : r.ok === false
              ? `✗ ${r.detail}`
              : `— ${r.detail}`,
      }));
    } catch (e) {
      setTestResults((t) => ({ ...t, [provider]: `✗ ${e instanceof Error ? e.message : String(e)}` }));
    } finally {
      setBusy("");
    }
  }

  async function reloadSAExtensionHealth() {
    if (busy) return;
    setBusy("sa.extension-health");
    try {
      setSaExtensionHealth(await getSAExtensionHealth());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  function renderProviderConfigField(pid: string, f: ProviderConfigField) {
    const draftKey = `${pid}.${f.field}`;
    const draft = keyDrafts[draftKey] ?? "";
    const envControlled = f.env_var === "IBKR_CLIENT_ID" && f.effective_source === "env";
    const chips = f.env_var === "IBKR_CLIENT_ID" && (f.client_id_domains?.length ?? 0) > 0
      ? ibkrClientIdChips(f.client_id_domains!, envControlled ? "" : draft)
      : null;
    const caption = envControlled
      ? "各域用戶端 ID（環境變數控制中）："
      : chips?.preview
        ? "存檔後 ID："
        : "各域用戶端 ID：";

    return (
      <div className="provider-config-field" key={draftKey}>
        <div className="provider-config-field-label">{f.label}</div>
        <div className="provider-config-field-current">
          {f.effective_source === "missing"
            ? <span className="ds-chip ds-missing_key">未設定</span>
            : <>
                <span className="mono">{f.app_value_set ? f.app_value_masked : "（外部）"}</span>
                {f.defaulted && <span className="muted tiny"> · 預設</span>}
                <span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
                {f.needs_import && (
                  <button className="btn-ghost tiny"
                    disabled={busy === `import.${pid}.${f.field}`}
                    onClick={() => void importField(pid, f.field, f.import_source)}>
                    匯入
                  </button>
                )}
                {f.needs_import && <span className="muted tiny">建議匯入</span>}
              </>}
        </div>
        <div className="provider-config-field-edit">
          <input
            className="ds-interval ds-keyinput"
            type={f.secret ? "password" : "text"}
            placeholder={f.secret ? "貼上金鑰…" : f.label}
            value={draft}
            disabled={busy === draftKey}
            onChange={(e) => setKeyDrafts((d) => ({ ...d, [draftKey]: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft) void saveField(pid, f.field, draft, f);
            }}
          />
          {draft && (
            <button
              ref={f.guarded ? guardedEditTriggerRef : undefined}
              className="btn-ghost tiny"
              onClick={() => void saveField(pid, f.field, draft, f)}
            >
              儲存
            </button>
          )}
          {f.app_value_set && (
            <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, null, f)}>
              清除
            </button>
          )}
        </div>
        {chips && (
          <div className="provider-config-field-hint muted tiny">
            {caption}{chips.text}
          </div>
        )}
      </div>
    );
  }

  function jobOutcome(jobName: string): string {
    const row = health?.jobs?.[jobName] as
      | { status?: string; finished_at?: string; error?: string }
      | undefined;
    if (!row) return "—";
    const ts = shortTs(row.finished_at ?? null);
    if (row.status === "succeeded") return `✓ ${ts}`;
    if (row.status === "failed") return `✗ ${ts}${row.error ? `（${String(row.error).slice(0, 60)}）` : ""}`;
    if (row.status === "running") return "執行中…";
    return row.status ?? "—";
  }

  function renderLastRun(source: string, s: ScheduleSourceState) {
    const details: Array<{ label: string; value: string; tone?: "bad" | "warn" }> = [];
    const skippedReason = s.last_result?.status === "skipped" ? s.last_result.reason ?? "已在執行" : null;
    const alreadyRunningSkip = skippedReason?.includes("already running") ?? false;
    const skippedSummary = alreadyRunningSkip ? "已有執行中" : compactMessage(skippedReason ?? "");
    const skipState = scheduleSkipCommonState(skippedReason);
    const historyState = durableScheduleCommonState(s);
    const durableSkipped = s.durable_state?.last_status === "skipped";
    if (skippedReason) {
      details.push({
        label: alreadyRunningSkip ? "新觸發略過" : "跳過原因",
        value: skippedReason,
        tone: "warn",
      });
    }
    const ss = schedulerStateLabel(s.durable_state ?? null);
    const bodyBacklog = schedulerBodyBacklogPresentation(s.durable_state ?? null);
    const durableError = s.durable_state?.last_status === "failed" ? s.durable_state.last_error : null;
    if (durableError) details.push({ label: "失敗訊息", value: durableError, tone: "bad" });

    return (
      <div className="ds-last-run">
        <div className="ds-last-run-summary">
          <span>{jobOutcome(s.job_name)}</span>
          {skippedReason && (
            skipState === null ? (
              <span className="muted tiny" title={skippedReason}>
                已跳過：{skippedSummary}
              </span>
            ) : (
              <StatusBadge state={skipState} label="新觸發已略過" />
            )
          )}
          {historyState !== null ? (
            <StatusBadge
              state={historyState}
              label={`${ss.label}${durableError ? `：${compactMessage(durableError)}` : ""}`}
            />
          ) : durableSkipped && !skippedReason ? (
            <span className="muted tiny">{ss.label}</span>
          ) : null}
          {ss.needsContinue && (
            <button
              className="btn-ghost"
              disabled={!!busy || s.running}
              onClick={() => void runNow(source)}
              title="手動補抓上次部分完成剩餘的標的"
            >
              補抓
            </button>
          )}
        </div>
        {bodyBacklog && (
          <div className={`tiny ${bodyBacklog.tone === "warn" ? "refresh-err" : "muted"}`}>
            {bodyBacklog.label}
            {bodyBacklog.earliestNextRetryAt
              ? ` · 最早 ${formatSystemTimestamp(bodyBacklog.earliestNextRetryAt)}`
              : ""}
          </div>
        )}
        {details.length > 0 && (
          <details className="ds-last-run-details">
            <summary>完整訊息</summary>
            {details.map((d) => (
              <div className={`ds-last-run-detail ${d.tone === "bad" ? "refresh-err" : ""}`} key={d.label}>
                <span className="muted tiny">{d.label}</span>
                <pre>{d.value}</pre>
              </div>
            ))}
          </details>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>資料來源 · Data Sources</h2>
          <p className="muted tiny">
            集中檢視各資料來源的健康狀態、連線設定、排程與手動執行。
            每個來源可獨立設定；IBKR 工作會共用 Gateway 鎖以避免重疊。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()} disabled={!!busy}>
          ↻ 重新整理{anyRunning ? "（執行中，自動更新）" : ""}
        </button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      <div className="settings-panel">
        <h4 className="detail-section">Provider 健康</h4>
        {!health ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-health-scroll">
            <table className="data-table settings-provider-health-table">
              <thead>
                <tr><th>Provider</th><th>狀態</th><th>金鑰</th><th>最近成功</th><th>最近錯誤</th></tr>
              </thead>
              <tbody>
                {health.providers.map((p) => (
                  <tr key={p.id}>
                    <td className="settings-wrap-text">
                      {p.label}
                      {fredProviderDetail(p) && (
                        <div className="muted tiny">{fredProviderDetail(p)}</div>
                      )}
                    </td>
                    <td><ProviderHealthState provider={p} /></td>
                    <td>
                      {p.key_source === "not_required" ? "免金鑰" : p.key_source}
                      {p.key_import_suggested && <span className="muted tiny"> · 建議匯入</span>}
                    </td>
                    <td>{shortTs(p.last_success_at)}</td>
                    <td className="muted settings-wrap-text">{p.last_error ? p.last_error.slice(0, 60) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <div className="settings-panel-head">
          <div>
            <h4 className="detail-section">SA Extension 健康</h4>
            <p className="muted tiny">
              檢查瀏覽器 extension、native host、sidecar 回報與資料接收狀態。
            </p>
          </div>
          <button
            className="btn-ghost"
            disabled={busy === "sa.extension-health"}
            onClick={() => void reloadSAExtensionHealth()}
          >
            重新檢查
          </button>
        </div>
        {!saExtensionHealth ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <>
            <p className="muted tiny">
              {saExtensionHealth.ok ? "鏈路可用" : "鏈路有中斷"} · {shortTs(saExtensionHealth.generated_at)}
            </p>
            <div className="settings-table-scroll" data-testid="sa-health-scroll">
              <table className="data-table settings-sa-health-table">
                <thead>
                  <tr><th>段落</th><th>狀態</th><th>細節</th></tr>
                </thead>
                <tbody>
                  {displaySAExtensionSegments(saExtensionHealth.segments).map((row) => (
                    <tr key={row.key}>
                      <td>{row.label}</td>
                      <td>
                        <StatusBadge
                          state={saSegmentCommonState(row.tone)}
                          label={row.tone === "ok" ? "正常" : row.tone === "warn" ? "注意" : "失敗"}
                        />
                      </td>
                      <td className="muted settings-wrap-text">{row.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">連線與金鑰</h4>
        <p className="muted tiny">
          來源標示會說明每個值由 App、環境變數或 config/.env 管理。
          App 內儲存的設定會立即生效；敏感值只顯示遮罩內容。
        </p>
        {cfgSetup?.required && (
          <div className="errorbox">
            <p className="muted">
              Provider 設定需要修復：{cfgSetup.reason ?? cfgSetup.code ?? "profile DB unavailable"}
            </p>
          </div>
        )}
        {!cfg ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-config-scroll">
          <table className="data-table ds-config settings-provider-config-table">
            <thead>
              <tr><th>Provider</th><th>欄位</th><th>目前值（來源）</th><th>設定</th><th>連線測試</th></tr>
            </thead>
            <tbody>
              {Object.entries(cfg)
                .filter(([, c]) => c.fields.length > 0 || c.testable)
                .map(([pid, c]) => {
                  const label = health?.providers.find((p) => p.id === pid)?.label ?? pid;
                  if (pid === "ibkr" && c.fields.length > 0) {
                    return (
                      <tr key="ibkr.group">
                        <td>
                          {label}
                          {c.default_available && <div className="muted tiny">免金鑰 · 預設可用</div>}
                        </td>
                        <td colSpan={4}>
                          <div data-testid="ibkr-config-group" className="provider-config-group">
                            {c.fields.map((f) => renderProviderConfigField(pid, f))}
                            <div className="provider-config-actions">
                              {c.testable ? (
                                <>
                                  <button className="btn-ghost" disabled={!!busy}
                                    onClick={() => void runTest(pid)}>
                                    測試
                                  </button>
                                  {testResults[pid] && (
                                    <div className="muted tiny">{testResults[pid]}</div>
                                  )}
                                </>
                              ) : (
                                <span className="muted tiny">不提供（按次計費）</span>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  }
                  const rows = c.fields.length > 0 ? c.fields : [null];
                  return rows.map((f, i) => (
                    <Fragment key={`${pid}.${f?.field ?? "_"}`}>
                    <tr>
                      {i === 0 && (
                        <td rowSpan={rows.length}>
                          {label}
                          {c.default_available && <div className="muted tiny">免金鑰 · 預設可用</div>}
                        </td>
                      )}
                      <td>{f ? f.label : "—"}</td>
                      <td>
                        {f
                          ? f.effective_source === "missing"
                            ? <span className="ds-chip ds-missing_key">未設定</span>
                            : <>
                                <span className="mono">{f.app_value_set ? f.app_value_masked : "（外部）"}</span>
                                {f.defaulted && <span className="muted tiny"> · 預設</span>}
                                <span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
                                {f.needs_import && (
                                  <button className="btn-ghost tiny"
                                    disabled={busy === `import.${pid}.${f.field}`}
                                    onClick={() => void importField(pid, f.field, f.import_source)}>
                                    匯入
                                  </button>
                                )}
                                {f.needs_import && <span className="muted tiny">建議匯入</span>}
                              </>
                          : "—"}
                      </td>
                      <td>
                        {f && (
                          <>
                            <input
                              className="ds-interval ds-keyinput"
                              type={f.secret ? "password" : "text"}
                              placeholder={f.secret ? "貼上金鑰…" : f.label}
                              value={keyDrafts[`${pid}.${f.field}`] ?? ""}
                              disabled={busy === `${pid}.${f.field}`}
                              onChange={(e) =>
                                setKeyDrafts((d) => ({ ...d, [`${pid}.${f.field}`]: e.target.value }))}
                              onKeyDown={(e) => {
                                const v = keyDrafts[`${pid}.${f.field}`];
                                if (e.key === "Enter" && v) void saveField(pid, f.field, v, f);
                              }}
                            />
                            {keyDrafts[`${pid}.${f.field}`] && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, keyDrafts[`${pid}.${f.field}`], f)}>
                                儲存
                              </button>
                            )}
                            {f.app_value_set && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, null, f)}>
                                清除
                              </button>
                            )}
                          </>
                        )}
                      </td>
                      {i === 0 && (
                        <td rowSpan={rows.length}>
                          {c.testable ? (
                            <>
                              <button className="btn-ghost" disabled={!!busy}
                                onClick={() => void runTest(pid)}>
                                測試
                              </button>
                              {testResults[pid] && (
                                <div className="muted tiny">{testResults[pid]}</div>
                              )}
                            </>
                          ) : (
                            <span className="muted tiny">不提供（按次計費）</span>
                          )}
                        </td>
                      )}
                    </tr>
                    </Fragment>
                  ));
                })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">排程（每來源獨立）</h4>
        {!schedule ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="schedule-scroll">
          <table className="data-table settings-schedule-table">
            <thead>
              <tr>
                <th>來源</th><th>排程</th><th>間隔（分）</th><th>立即執行</th><th>最近一次</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(schedule).map(([id, s]) => (
                <tr key={id}>
                  <td>
                    {s.label}
                    {s.retired && <span className="ds-chip ds-disabled">已退役</span>}
                  </td>
                  <td>
                    <label className="ds-toggle">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        disabled={busy === id}
                        onChange={(e) => void setEnabled(id, e.target.checked)}
                      />
                      <span className={s.enabled ? "tiny" : "muted tiny ds-schedule-disabled"}>
                        {s.enabled ? "排程開啟" : "排程關閉"}
                      </span>
                    </label>
                  </td>
                  <td>
                    <input
                      className="ds-interval"
                      type="number"
                      min={5}
                      placeholder={String(s.interval_minutes)}
                      value={drafts[id] ?? ""}
                      disabled={busy === id}
                      onChange={(e) => setDrafts((d) => ({ ...d, [id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === "Enter") void applyInterval(id); }}
                    />
                    {drafts[id] && (
                      <button className="btn-ghost tiny" onClick={() => void applyInterval(id)}>
                        套用
                      </button>
                    )}
                  </td>
                  <td>
                    {s.running ? (
                      <SourceRunProgress
                        sourceLabel={s.label}
                        running={s.running}
                        progress={s.progress}
                      />
                    ) : (
                      <button
                        className="btn-ghost"
                        disabled={!!busy}
                        onClick={() => void runNow(id)}
                      >
                        ▶ Run
                      </button>
                    )}
                  </td>
                  <td className="muted tiny ds-last-run-cell settings-wrap-text">
                    {renderLastRun(id, s)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
        <p className="muted tiny ds-schedule-protection-note" style={{ marginTop: 8 }}>
          執行保護：同一資料來源與 IBKR 工作同時間只執行一次；若已有工作進行中，
          新觸發會顯示為已跳過，不會重複抓取。
        </p>
      </div>
      <ConfirmDialog
        open={pendingGuardedEdit !== null}
        title="套用受保護的設定？"
        consequence={
          pendingGuardedEdit?.fieldMeta.guard_reason
          ?? "此設定需要確認後才會變更。"
        }
        confirmLabel="套用變更"
        tone="primary"
        busy={pendingGuardedEdit !== null && busy === `${pendingGuardedEdit.provider}.${pendingGuardedEdit.field}`}
        onConfirm={() => void confirmGuardedEdit()}
        onCancel={() => setPendingGuardedEdit(null)}
        returnFocusRef={guardedEditTriggerRef}
      />
    </div>
  );
}
