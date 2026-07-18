import type { NavigationTarget } from "./shell/navigation";
import type { CommonUiState } from "./ui";

export interface ResearchErrorPresentation {
  code: string;
  state: CommonUiState;
  title: string;
  detail: string;
  actionLabel: string | null;
  target: NavigationTarget | null;
  preservePartial: boolean;
  developerDetail: string | null;
}

interface ErrorDefinition {
  state: CommonUiState;
  title: string;
  detail: string;
  actionLabel?: string;
  target?: NavigationTarget;
  preservePartial?: boolean;
}

const SETTINGS_PROVIDERS: NavigationTarget = {
  kind: "settings_section",
  section: "providers",
};
const SETTINGS_MODELS: NavigationTarget = {
  kind: "settings_section",
  section: "models",
};

const DEFINITIONS: Record<string, ErrorDefinition> = {
  reauth_required: {
    state: "blocked",
    title: "需要重新登入",
    detail: "目前登入已失效，完成重新登入後再執行研究。",
    actionLabel: "前往登入設定",
    target: SETTINGS_PROVIDERS,
  },
  missing_credential: {
    state: "blocked",
    title: "尚未設定登入",
    detail: "此 Provider 沒有可供 AI 研究使用的登入。",
    actionLabel: "設定 Provider",
    target: SETTINGS_PROVIDERS,
  },
  model_timeout: {
    state: "failed",
    title: "模型執行逾時",
    detail: "模型未在目前 AI 研究執行上界內完成。",
    actionLabel: "檢查 AI 研究執行限制",
    target: SETTINGS_MODELS,
  },
  model_refusal: {
    state: "failed",
    title: "模型拒絕回答",
    detail: "Provider 已回應，但模型拒絕完成這次要求。",
  },
  provider_call_failed: {
    state: "failed",
    title: "Provider 呼叫失敗",
    detail: "Provider 未能完成這次研究呼叫，請稍後重試。",
  },
  tool_limit_reached: {
    state: "failed",
    title: "已達工具呼叫上限",
    detail: "已保留目前取得的內容與工具紀錄；請簡化問題或調整限制後重試。",
    actionLabel: "簡化問題或重試",
    target: SETTINGS_MODELS,
    preservePartial: true,
  },
  cancelled: {
    state: "interrupted",
    title: "研究已取消",
    detail: "這次研究由使用者停止。",
  },
  interrupted: {
    state: "interrupted",
    title: "研究已中止",
    detail: "執行在完成前中止；已取得的內容仍會保留。",
    preservePartial: true,
  },
  run_cancelled: {
    state: "interrupted",
    title: "研究已取消",
    detail: "這次研究由使用者停止。",
  },
  run_interrupted: {
    state: "interrupted",
    title: "研究已中止",
    detail: "執行在完成前中止；已取得的內容仍會保留。",
    preservePartial: true,
  },
};

export function sanitizeResearchDiagnostic(detail: string, limit = 1_500): string {
  return detail
    .slice(0, limit)
    .replace(
      /["']?(?:credential_id|access_token|refresh_token)["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;}]+)/gi,
      "[REDACTED]",
    )
    .replace(/\bBearer\s+[^\s,;]+/gi, "[REDACTED]")
    .replace(/\blocal:\d+\b/gi, "[REDACTED]");
}

export function presentResearchError({
  code,
  detail = null,
  developerMode = false,
}: {
  code: string | null | undefined;
  detail?: string | null;
  developerMode?: boolean;
}): ResearchErrorPresentation {
  const normalizedCode = code && DEFINITIONS[code] ? code : "provider_call_failed";
  const definition = DEFINITIONS[normalizedCode];
  return {
    code: normalizedCode,
    state: definition.state,
    title: definition.title,
    detail: definition.detail,
    actionLabel: definition.actionLabel ?? null,
    target: definition.target ?? null,
    preservePartial: definition.preservePartial ?? false,
    developerDetail: developerMode && detail ? sanitizeResearchDiagnostic(detail) : null,
  };
}
