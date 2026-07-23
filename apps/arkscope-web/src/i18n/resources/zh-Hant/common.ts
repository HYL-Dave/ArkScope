// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const common = {
  i18n: {
    missingTranslation: "此文字暫時無法顯示。",
  },
  actions: {
    close: "關閉",
    pin: "釘選",
    unpin: "取消釘選",
    stop: "停止",
  },
  boundedProgress: {
    failureTitle: "工作失敗",
    failureDetail: "工作未完成，請依錯誤指示處理。",
    awaitingConfirmation: "已達上界，等待伺服器確認",
    completedAnnouncement: "工作完成",
    interruptedAnnouncement: "工作已中止",
    overallElapsed: "總耗時 {{duration}}",
    stageElapsed: "階段耗時 {{duration}}",
    stageBound: "本階段上界 {{duration}}",
    continuesAfterNavigation: "離開頁面後繼續",
    trackingNotGuaranteed: "離開頁面後不保證追蹤",
    cancellationAvailable: "可從此處取消",
    cancellationUnavailable: "無法從此處取消",
    result: "結果：{{destination}}",
  },
  personalization: {
    stances: {
      off: "關閉",
      neutral: "中性",
      aligned: "對齊投資人",
      complementary: "互補投資人",
      strictRiskControl: "嚴格風控",
      valuationRationalist: "估值理性派",
      growthOpportunity: "成長機會派",
    },
    mismatch: {
      none: "一致",
      appetiteAboveCapacity: "風險意願高於承受能力",
      capacityAboveAppetite: "承受能力高於風險意願",
      unclear: "未評估",
    },
    trace: {
      stance: "立場：{{stance}}",
      appliedSkills: "套用技能：{{skills}}",
      suggestedSkills: "建議技能：{{skills}}",
    },
  },
} as const;

export default common;
