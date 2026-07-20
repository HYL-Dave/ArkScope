// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const shell = {
  navigation: {
    primaryLabel: "主要導覽",
    drawerTitle: "導覽",
    openDrawer: "開啟導覽",
    groups: {
      explore: "探索",
      research: "研究",
      monitor: "追蹤",
      system: "系統",
    },
    views: {
      home: "工作台",
      watchlist: "自選股",
      universe: "全部標的",
      news: "新聞·事件",
      research: "AI 研究",
      holdings: "持倉",
      system: "System / Health",
      settings: "設定",
    },
  },
  topbar: {
    sidecar: {
      ready: "Sidecar 已連線",
      error: "Sidecar 無法連線",
      loading: "正在連線",
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
    triggerAria: "AI 研究背景工作：{{summary}}",
    activeCount: "執行中 {{count}}",
    attentionCount: "待查看 {{count}}",
    drawerTitle: "背景工作",
    sessionScope: "僅顯示此桌面工作階段觀察到的 AI 研究。",
    openConversation: "開啟對話",
    dismissAria: "忽略 {{runId}}",
    stages: {
      queued: "等待執行",
      running: "AI 研究執行中",
      succeeded: "研究完成",
      failed: "研究未完成",
      interrupted: "研究已中止",
    },
    resultDestination: "AI 研究對話",
    failureNextStep: "開啟原對話查看可採取的下一步。",
  },
} as const;

export default shell;
