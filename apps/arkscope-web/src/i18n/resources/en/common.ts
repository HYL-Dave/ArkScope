// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const common = {
  i18n: {
    missingTranslation: "This text is temporarily unavailable.",
  },
  actions: {
    close: "Close",
    pin: "Pin",
    unpin: "Unpin",
    stop: "Stop",
  },
  labels: {
    ticker: "Ticker",
  },
  dataTable: {
    actionHeading: "Actions",
    rowActions: "Actions for {{label}}",
  },
  confirmDialog: {
    defaultCancel: "Cancel",
  },
  markdown: {
    blockedImageFallback: "[blocked image]",
  },
  boundedProgress: {
    failureTitle: "Work failed",
    failureDetail: "The work did not complete. Follow the error guidance to continue.",
    awaitingConfirmation: "Bound reached; waiting for server confirmation",
    completedAnnouncement: "Work completed",
    interruptedAnnouncement: "Work interrupted",
    overallElapsed: "Overall elapsed {{duration}}",
    stageElapsed: "Stage elapsed {{duration}}",
    stageBound: "Stage bound {{duration}}",
    continuesAfterNavigation: "Continues after leaving this page",
    trackingNotGuaranteed: "Tracking is not guaranteed after leaving this page",
    cancellationAvailable: "Can be cancelled here",
    cancellationUnavailable: "Cannot be cancelled here",
    result: "Result: {{destination}}",
  },
  models: {
    groups: {
      available: "Available for this task",
      visibleDisabled: "Visible to this sign-in",
      advanced: "Advanced / unverified",
      current: "Current route",
    },
    reasons: {
      missingActiveCredential: "No sign-in is configured for this provider",
      taskAuthModeUnsupported: "This sign-in method does not support the task",
      taskTestUnsupported: "This sign-in method does not yet support live testing",
      modelAuthUnverified: "This model has not been live-verified for this sign-in. Use an API key or choose another model",
      taskCapabilityMissing: "Task capability is missing",
      modelNotVisible: "This model does not appear in the discovery list for this sign-in",
      modelNotInRegistry: "Custom or unknown model; capabilities are unverified",
      discoveryUnavailable: "Model discovery status is temporarily unavailable",
      providerCallFailed: "The live provider call failed",
      reauthRequired: "The sign-in has expired. Sign in again",
      subscriptionPlanRequired: "Requires a ChatGPT Pro plan",
      modelTaskUnsupported: "This model does not support this task",
      modelOutputLimitUnknown: "This model's output limit is unknown for this route",
      protocolIncompatible: "The bundled model adapter is incompatible",
      protocolResourceExhausted: "The model adapter exceeded its bounded resources",
      contextWindowExceeded: "The content exceeds this model's context window",
      versionIncompatible: "The bundled model runtime version is incompatible",
      subscriptionUsageUnavailable: "ChatGPT subscription usage is currently unavailable",
      adapterUnavailable: "The bundled model adapter is unavailable",
      timeout: "The model request timed out",
      modelRetired: "This model is retired for new runs",
    },
    authModes: {
      apiKey: "API key",
      apiKeyPool: "API key pool",
      chatgptOauth: "ChatGPT subscription sign-in",
      claudeCodeOauth: "Claude subscription sign-in",
    },
    thinkingModes: {
      none: "No special thinking behavior",
      manualBudget: "Uses a manual thinking budget",
      adaptiveOptIn: "Adaptive thinking available",
      adaptiveDefaultOn: "Adaptive thinking on by default",
      adaptiveAlwaysOn: "Adaptive thinking always on",
    },
    compatibility: {
      decoratedSuffix: "Unverified (legacy sidecar compatibility mode)",
      settingsNotice: "Unverified (legacy sidecar compatibility mode).",
    },
  },
  personalization: {
    stances: {
      off: "Off",
      neutral: "Neutral",
      aligned: "Investor-aligned",
      complementary: "Complementary",
      strictRiskControl: "Strict risk control",
      valuationRationalist: "Valuation rationalist",
      growthOpportunity: "Growth opportunity",
    },
    mismatch: {
      none: "Aligned",
      appetiteAboveCapacity: "Risk appetite above capacity",
      capacityAboveAppetite: "Risk capacity above appetite",
      unclear: "Not assessed",
    },
    trace: {
      stance: "Stance: {{stance}}",
      appliedSkills: "Applied skills: {{skills}}",
      suggestedSkills: "Suggested skills: {{skills}}",
    },
  },
} as const;

export default common;
