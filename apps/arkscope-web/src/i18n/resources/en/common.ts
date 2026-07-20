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
} as const;

export default common;
