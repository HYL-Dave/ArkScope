// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const shell = {
  saAcquisition: {
    title: "Seeking Alpha acquisition",
    unfinishedTitle: "Unfinished capture record",
    unfinished: "{{operation}}: started {{started}}, {{count}} navigation attempts. Browser activity is unconfirmed; check the collector extension.",
    login: "Sign-in expired. Acquisition is paused. Sign in to Seeking Alpha in the collector browser, then explicitly resume from the extension.",
    verification: "Verification required. Acquisition is paused until you complete verification and explicitly resume from the extension.",
    access: "Subscription access unavailable: {{capabilities}}. These updates are paused. Premium and Alpha Picks have separate access requirements; signing in alone does not verify either subscription.",
    cooldown: "Seeking Alpha cooldown active. Acquisition remains stopped until the recorded cooldown expires.",
    paused: "Acquisition paused. Check the collector extension before resuming.",
    unavailable: "Status unavailable. Acquisition health cannot be confirmed.",
    financials: "Financial statements",
    alphaPicks: "Alpha Picks",
    news: "News",
    otherContent: "Other content",
    openSettings: "Open source settings",
  },
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
