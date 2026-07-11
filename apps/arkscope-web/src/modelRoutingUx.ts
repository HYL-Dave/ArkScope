import type {
  EffectiveProviderSummary,
  ModelCatalog,
  ModelProvider,
  ModelTask,
  ProviderCredential,
  TaskRoute,
} from "./api";

export const MODEL_UX_LABELS: {
  groups: readonly string[];
  reasons: Record<string, string>;
  authModes: Record<string, string>;
  thinking: Record<string, string>;
} = {
  groups: ["可供此任務使用", "此登入可見", "進階／未驗證", "目前路由"],
  reasons: {
    missing_active_credential: "尚未設定此 provider 的登入",
    task_auth_mode_unsupported: "此登入方式不支援這個任務",
    task_test_unsupported: "此登入方式尚不支援實際測試",
    task_capability_missing: "缺少任務能力",
    model_not_visible: "此登入的探索清單未顯示此模型",
    model_not_in_registry: "自訂／未知模型，尚未驗證能力",
    discovery_unavailable: "暫時無法讀取模型探索狀態",
    provider_call_failed: "provider 實際呼叫失敗",
    reauth_required: "登入已失效，請重新登入",
  },
  authModes: {
    api_key: "API key",
    api_key_pool: "API key pool",
    chatgpt_oauth: "ChatGPT 訂閱登入",
    claude_code_oauth: "Claude 訂閱登入",
  },
  thinking: {
    none: "無特殊 thinking 行為",
    manual_budget: "使用手動 thinking budget",
    adaptive_opt_in: "可選擇 adaptive thinking",
    adaptive_default_on: "預設開啟 adaptive thinking",
    adaptive_always_on: "固定開啟 adaptive thinking",
  },
};

export interface DraftRouteValue {
  provider: ModelProvider;
  model: string;
  effort: string;
  custom: boolean;
}

export interface TaskTestSnapshot {
  task: ModelTask;
  provider: ModelProvider;
  model: string;
  effort: string;
  credential_id: string;
}

export type ProviderContextMap = Record<ModelProvider, EffectiveProviderSummary | null>;

export function providerContexts(
  effective: Partial<Record<ModelProvider, EffectiveProviderSummary | null>> | undefined,
  credentials: Record<ModelProvider, ProviderCredential[]>,
): ProviderContextMap {
  if (effective) {
    return {
      openai: effective.openai ?? null,
      anthropic: effective.anthropic ?? null,
    };
  }
  const fromInventory = (provider: ModelProvider): EffectiveProviderSummary | null => {
    const active = (credentials[provider] ?? []).find((row) => row.active && row.available);
    if (!active) return null;
    return {
      credential_id: active.id,
      auth_mode: active.auth_type,
      label: active.label,
    };
  };
  return { openai: fromInventory("openai"), anthropic: fromInventory("anthropic") };
}

export function routesSemanticallyEqual(
  draft: Pick<DraftRouteValue, "provider" | "model" | "effort"> | undefined,
  baseline: Pick<TaskRoute, "provider" | "model" | "effort"> | undefined,
): boolean {
  if (!draft || !baseline) return draft === baseline;
  return (
    draft.provider === baseline.provider
    && draft.model.trim() === baseline.model.trim()
    && (draft.effort || "default") === (baseline.effort || "default")
  );
}

export function blockedRouteSaves(
  draft: Partial<Record<ModelTask, DraftRouteValue>>,
  baseline: ModelCatalog["routes"],
  contexts: ProviderContextMap,
): Array<{ task: ModelTask; reason: "missing_active_credential" }> {
  const blocked: Array<{ task: ModelTask; reason: "missing_active_credential" }> = [];
  for (const task of Object.keys(draft) as ModelTask[]) {
    const row = draft[task];
    if (!row || routesSemanticallyEqual(row, baseline[task])) continue;
    if (!contexts[row.provider]) blocked.push({ task, reason: "missing_active_credential" });
  }
  return blocked;
}

export function isTaskTestSnapshotCurrent(
  snapshot: TaskTestSnapshot,
  current: {
    task: ModelTask;
    route: DraftRouteValue;
    credentialId: string | null;
    stale: boolean;
  },
): boolean {
  return !current.stale
    && snapshot.task === current.task
    && snapshot.provider === current.route.provider
    && snapshot.model === current.route.model
    && snapshot.effort === (current.route.effort || "default")
    && snapshot.credential_id === current.credentialId;
}
