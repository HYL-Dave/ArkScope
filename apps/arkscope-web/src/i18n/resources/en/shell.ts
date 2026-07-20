// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const shell = {
  navigation: {
    primaryLabel: "Primary navigation",
    drawerTitle: "Navigation",
    openDrawer: "Open navigation",
    groups: {
      explore: "Explore",
      research: "Research",
      monitor: "Monitor",
      system: "System",
    },
    views: {
      home: "Home",
      watchlist: "Watchlist",
      universe: "Universe",
      news: "News",
      research: "AI Research",
      holdings: "Holdings",
      system: "System / Health",
      settings: "Settings",
    },
  },
  topbar: {
    sidecar: {
      ready: "Sidecar connected",
      error: "Sidecar unavailable",
      loading: "Connecting",
    },
    developerDiagnostics: "Developer diagnostics",
    diagnostics: {
      apiValue: "API {{value}}",
      toolsValue: "Tools {{value}}",
      lastStatusValue: "Last status {{value}}",
      cardModelValue: "Card model {{value}}",
    },
  },
  backgroundWork: {
    triggerAria: "AI Research background work: {{summary}}",
    activeCount: "Running {{count}}",
    attentionCount: "To review {{count}}",
    drawerTitle: "Background work",
    sessionScope: "Only AI Research observed in this desktop session is shown.",
    openConversation: "Open conversation",
    dismissAria: "Dismiss {{runId}}",
    stages: {
      queued: "Waiting to run",
      running: "AI Research running",
      succeeded: "Research complete",
      failed: "Research incomplete",
      interrupted: "Research interrupted",
    },
    resultDestination: "AI Research conversation",
    failureNextStep: "Open the original conversation to see the available next step.",
  },
} as const;

export default shell;
