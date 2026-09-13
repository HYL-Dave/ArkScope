import type { NavigationTarget } from "./shell/navigation";
import type { CommonUiState } from "./ui";
import type { ResearchT } from "./i18n/researchPresentation";

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
  copy: "reauth" | "missingCredential" | "timeout" | "refusal" | "providerCallFailed"
    | "toolLimit" | "cancelled" | "interrupted" | "maintenance"
    | "protectionPlatform" | "protectionPath" | "protectionConfiguration" | "protectionSpace" | "protectionUnavailable";
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
    copy: "reauth",
    target: SETTINGS_PROVIDERS,
  },
  missing_credential: {
    state: "blocked",
    copy: "missingCredential",
    target: SETTINGS_PROVIDERS,
  },
  model_timeout: {
    state: "failed",
    copy: "timeout",
    target: SETTINGS_MODELS,
  },
  model_refusal: {
    state: "failed",
    copy: "refusal",
  },
  provider_call_failed: {
    state: "failed",
    copy: "providerCallFailed",
  },
  sec_research_operation_busy: {
    state: "blocked",
    copy: "maintenance",
  },
  capture_platform_unsupported: {
    state: "blocked",
    copy: "protectionPlatform",
  },
  capture_path_unsafe: {
    state: "blocked",
    copy: "protectionPath",
  },
  sec_research_operation_invalid: {
    state: "blocked",
    copy: "protectionConfiguration",
  },
  storage_space_insufficient: {
    state: "blocked",
    copy: "protectionSpace",
  },
  capture_store_write_failed: {
    state: "blocked",
    copy: "protectionUnavailable",
  },
  tool_limit_reached: {
    state: "failed",
    copy: "toolLimit",
    target: SETTINGS_MODELS,
    preservePartial: true,
  },
  cancelled: {
    state: "interrupted",
    copy: "cancelled",
  },
  interrupted: {
    state: "interrupted",
    copy: "interrupted",
    preservePartial: true,
  },
  run_cancelled: {
    state: "interrupted",
    copy: "cancelled",
  },
  run_interrupted: {
    state: "interrupted",
    copy: "interrupted",
    preservePartial: true,
  },
};

function errorCopy(
  id: ErrorDefinition["copy"],
  t: ResearchT,
): { title: string; detail: string; actionLabel: string | null } {
  switch (id) {
    case "reauth":
      return {
        title: t(($) => $.errors.reauthTitle),
        detail: t(($) => $.errors.reauthDetail),
        actionLabel: t(($) => $.errors.reauthAction),
      };
    case "missingCredential":
      return {
        title: t(($) => $.errors.missingCredentialTitle),
        detail: t(($) => $.errors.missingCredentialDetail),
        actionLabel: t(($) => $.errors.providerSettingsAction),
      };
    case "timeout":
      return {
        title: t(($) => $.errors.timeoutTitle),
        detail: t(($) => $.errors.timeoutDetail),
        actionLabel: t(($) => $.errors.runtimeSettingsAction),
      };
    case "refusal":
      return {
        title: t(($) => $.errors.refusalTitle),
        detail: t(($) => $.errors.refusalDetail),
        actionLabel: null,
      };
    case "providerCallFailed":
      return {
        title: t(($) => $.errors.providerCallFailedTitle),
        detail: t(($) => $.errors.providerCallFailedDetail),
        actionLabel: null,
      };
    case "maintenance":
      return {
        title: t(($) => $.errors.maintenanceTitle),
        detail: t(($) => $.errors.maintenanceDetail),
        actionLabel: null,
      };
    case "protectionPlatform":
      return {
        title: t(($) => $.errors.protectionPlatformTitle),
        detail: t(($) => $.errors.protectionPlatformDetail),
        actionLabel: null,
      };
    case "protectionPath":
      return {
        title: t(($) => $.errors.protectionPathTitle),
        detail: t(($) => $.errors.protectionPathDetail),
        actionLabel: null,
      };
    case "protectionConfiguration":
      return {
        title: t(($) => $.errors.protectionConfigurationTitle),
        detail: t(($) => $.errors.protectionConfigurationDetail),
        actionLabel: null,
      };
    case "protectionSpace":
      return {
        title: t(($) => $.errors.protectionSpaceTitle),
        detail: t(($) => $.errors.protectionSpaceDetail),
        actionLabel: null,
      };
    case "protectionUnavailable":
      return {
        title: t(($) => $.errors.protectionUnavailableTitle),
        detail: t(($) => $.errors.protectionUnavailableDetail),
        actionLabel: null,
      };
    case "toolLimit":
      return {
        title: t(($) => $.errors.maxTurnsTitle),
        detail: t(($) => $.errors.maxTurnsDetail),
        actionLabel: t(($) => $.errors.retryAction),
      };
    case "cancelled":
      return {
        title: t(($) => $.errors.cancelledTitle),
        detail: t(($) => $.errors.cancelledDetail),
        actionLabel: null,
      };
    case "interrupted":
      return {
        title: t(($) => $.errors.interruptedTitle),
        detail: t(($) => $.errors.interruptedDetail),
        actionLabel: null,
      };
  }
}

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
}, t: ResearchT): ResearchErrorPresentation {
  const normalizedCode = code && DEFINITIONS[code] ? code : "provider_call_failed";
  const definition = DEFINITIONS[normalizedCode];
  const copy = errorCopy(definition.copy, t);
  return {
    code: normalizedCode,
    state: definition.state,
    title: copy.title,
    detail: copy.detail,
    actionLabel: copy.actionLabel,
    target: definition.target ?? null,
    preservePartial: definition.preservePartial ?? false,
    developerDetail: developerMode && detail ? sanitizeResearchDiagnostic(detail) : null,
  };
}
