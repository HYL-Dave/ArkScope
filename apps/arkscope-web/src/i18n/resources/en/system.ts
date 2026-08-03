// Translation authority: docs/design/ARKSCOPE_TERMINOLOGY.md
const system = {
  sidecar: {
    loading: "Connecting to the local Sidecar…",
    failure: "Could not connect to the local Sidecar",
    retry: "Retry",
    ready: "Local Sidecar connected.",
  },
  dataSourceSettings: "Data source settings",
  developer: {
    heading: "Developer Mode",
    showDiagnostics: "Show local diagnostic information",
  },
  runtime: {
    modelsInUse: "Models in use",
    cardSynthesis: "card synthesis",
    cardTranslation: "card translation",
    anthropicDefaultAdvanced: "anthropic (default / advanced)",
    openAIDefaultAdvanced: "openai (default / advanced)",
    apiKeysPresent: "API keys present",
    keySet: "✓ set",
    keyMissing: "✗ missing",
  },
  status: {
    registryTools: "Registry tools",
    serverTime: "Server time",
    status: "Status",
    toolCategories: "Tool categories",
    dataSourcesTickers: "Data sources (tickers)",
    dataSourceLabels: {
      newsTickers: "News tickers",
      priceTickers: "Price tickers",
      storedSecFundamentals: "Stored SEC fundamentals",
      unknown: "Unknown data source ({{value}})",
    },
  },
} as const;

export default system;
