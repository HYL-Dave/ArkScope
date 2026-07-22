import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { SETTINGS_GROUPS } from "../settings/settingsRegistry";

const projectRoot = resolve(import.meta.dirname, "../..");

const I18N_1_MIGRATED_SCOPES = [
  "src/i18n/**",
  "src/main.tsx",
  "src/App.tsx",
  "src/shell/**",
  "src/ui/BoundedProgress.tsx",
  "src/ui/Drawer.tsx",
];

const I18N_2_SETTINGS_SCOPES = [
  "src/InvestorProfilePanel.tsx",
  "src/Settings.tsx",
  "src/SourceRunProgress.tsx",
  "src/chatgptOAuth.ts",
  "src/credentialDisplay.ts",
  "src/marketDataDisplay.ts",
  "src/modelRouteDisplay.ts",
  "src/saExtensionHealthDisplay.ts",
  "src/settings/DataSourcesSection.tsx",
  "src/settings/DataStorageSection.tsx",
  "src/settings/MacroStorageSection.tsx",
  "src/settings/ModelRoutingSection.tsx",
  "src/settings/NewsStorageSection.tsx",
  "src/settings/ProviderSection.tsx",
  "src/settings/RuntimeLimitSections.tsx",
  "src/settings/SettingsDirectory.tsx",
  "src/settings/SettingsSectionAnchor.tsx",
  "src/settings/settingsBackendCopy.ts",
  "src/settings/settingsCopy.ts",
  "src/settings/settingsNavigationGuard.ts",
  "src/settings/settingsPreferences.ts",
  "src/settings/settingsRegistry.ts",
];

const SLICE_5_MIGRATED_SCOPES = [
  "src/settings/investor/**",
  "src/ResearchPersonalizationContext.tsx",
];

const ARKSCOPE_ALLOWLIST_ENTRY = {
  file: "src/shell/ShellTopBar.tsx",
  kind: "jsx_text",
  literal: "ArkScope",
  count: 1,
  classification: "stable_identifier",
  reason: "ArkScope is the product name and is identical in every locale.",
};

const SETTINGS_ALLOWLIST_REASON =
  "non-visible tone, enum, form value, or identifier format required by the existing typed domain contract";

const I18N_2_SETTINGS_ALLOWLIST_ENTRIES = [
  ["src/credentialDisplay.ts", "presenter_return", "anthropic", 1],
  ["src/credentialDisplay.ts", "presenter_return", "claude_code_oauth", 2],
  ["src/settings/settingsCopy.ts", "presenter_return", "GPT-5.6", 1],
  ["src/marketDataDisplay.ts", "object_property", "weekend", 1],
  ["src/marketDataDisplay.ts", "presenter_return", "muted", 6],
  ["src/marketDataDisplay.ts", "presenter_return", "bad", 2],
  ["src/marketDataDisplay.ts", "presenter_return", "warn", 9],
  ["src/marketDataDisplay.ts", "presenter_return", "ok", 2],
  ["src/settings/DataSourcesSection.tsx", "jsx_attribute", "ok", 1],
  ["src/settings/DataSourcesSection.tsx", "jsx_attribute", "warn", 1],
  ["src/settings/ModelRoutingSection.tsx", "jsx_attribute", "default", 1],
  ["src/settings/ModelRoutingSection.tsx", "jsx_attribute", "anthropic", 1],
  ["src/settings/ModelRoutingSection.tsx", "jsx_attribute", "claude-…", 1],
  ["src/settings/ModelRoutingSection.tsx", "jsx_attribute", "gpt-…", 1],
  ["src/settings/ProviderSection.tsx", "jsx_attribute", "openai", 1],
  ["src/settings/ProviderSection.tsx", "jsx_attribute", "sk-…", 1],
  ["src/settings/ProviderSection.tsx", "jsx_attribute", "sk-ant-…", 1],
  ["src/settings/ProviderSection.tsx", "jsx_attribute", "claude_code_oauth", 1],
  ["src/settings/ProviderSection.tsx", "jsx_attribute", "chatgpt_oauth", 1],
].map(([file, kind, literal, count]) => ({
  file,
  kind,
  literal,
  count,
  classification: "stable_identifier",
  reason: SETTINGS_ALLOWLIST_REASON,
}));

const I18N_2_OWNED_DEBT_FILES = new Set([
  "src/InvestorProfilePanel.tsx",
  "src/Settings.tsx",
  "src/SourceRunProgress.tsx",
  "src/chatgptOAuth.ts",
  "src/credentialDisplay.ts",
  "src/marketDataDisplay.ts",
  "src/modelRouteDisplay.ts",
  "src/saExtensionHealthDisplay.ts",
  "src/settings/DataSourcesSection.tsx",
  "src/settings/DataStorageSection.tsx",
  "src/settings/MacroStorageSection.tsx",
  "src/settings/ModelRoutingSection.tsx",
  "src/settings/NewsStorageSection.tsx",
  "src/settings/ProviderSection.tsx",
  "src/settings/RuntimeLimitSections.tsx",
  "src/settings/SettingsDirectory.tsx",
  "src/settings/settingsRegistry.ts",
]);

function read(relativePath: string): string {
  const path = resolve(projectRoot, relativePath);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

function productionFiles(relativePath: string): string[] {
  const path = resolve(projectRoot, relativePath);
  if (!existsSync(path)) return [];
  if (!statSync(path).isDirectory()) return [path];
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const child = resolve(path, entry.name);
    if (entry.isDirectory()) return productionFiles(child.slice(projectRoot.length + 1));
    if (!entry.name.match(/\.tsx?$/) || entry.name.includes(".test.")) return [];
    return [child];
  });
}

function productionScopeFiles(scope: string): string[] {
  if (!scope.endsWith("/**")) return [scope];
  return productionFiles(scope.slice(0, -3))
    .map((path) => path.slice(projectRoot.length + 1));
}

const migratedSettingsFiles = [
  ...I18N_2_SETTINGS_SCOPES,
  ...SLICE_5_MIGRATED_SCOPES,
].flatMap(productionScopeFiles);

function ownsSettingsDebt(file: string): boolean {
  return I18N_2_OWNED_DEBT_FILES.has(file)
    || file === "src/ResearchPersonalizationContext.tsx"
    || file.startsWith("src/settings/investor/");
}

describe("I18N-0 foundation boundaries", () => {
  it("bootstraps locale before createRoot and mounts both providers", () => {
    const source = read("src/main.tsx");
    const order = [
      "installUiTokens(document.documentElement);",
      "bootstrapUiLocale({",
      'document.getElementById("root")',
      "createUiLocaleController({",
      "createRoot(rootEl)",
      "root.render(",
    ].map((needle) => source.indexOf(needle));

    expect(order.every((index) => index >= 0)).toBe(true);
    expect(order).toEqual([...order].sort((left, right) => left - right));
    expect(source).toMatch(
      /<I18nextProvider[^>]*>[\s\S]*<LocaleProvider[^>]*>[\s\S]*<App\s*\/>[\s\S]*<\/LocaleProvider>[\s\S]*<\/I18nextProvider>/,
    );
  });

  it("uses zh-Hant as the static document fallback", () => {
    expect(read("index.html")).toContain('<html lang="zh-Hant">');
  });

  it("fixes the Vitest default locale to zh-Hant", () => {
    const config = read("vitest.config.ts");
    const setup = read("src/test/setupI18n.ts");
    expect(config).toContain('setupFiles: ["src/test/setupI18n.ts"]');
    expect(setup).toContain('"zh-Hant"');
    expect(setup).toContain("beforeEach");
  });

  it("uses no detector loader Suspense or dynamic resource import", () => {
    const manifest = JSON.parse(read("package.json")) as {
      dependencies?: Record<string, string>;
    };
    expect(Object.keys(manifest.dependencies ?? {})).not.toEqual(
      expect.arrayContaining([
        "i18next-browser-languagedetector",
        "i18next-http-backend",
        "i18next-icu",
      ]),
    );

    const source = productionFiles("src/i18n")
      .filter((path) => !path.includes("/resources/"))
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");
    expect(source).not.toContain("<Suspense");
    expect(source).not.toMatch(/\bimport\s*\(/);
  });

  it("renders no language selector autonym or planned locale affordance", () => {
    const paths = [
      "src/App.tsx",
      "src/Settings.tsx",
      "src/main.tsx",
      ...productionFiles("src/shell").map((path) => path.slice(projectRoot.length + 1)),
      ...productionFiles("src/settings").map((path) => path.slice(projectRoot.length + 1)),
      "src/i18n/LocaleProvider.tsx",
    ];
    const source = paths.map(read).join("\n");

    expect(source).not.toMatch(/繁體中文|介面語言|>\s*English\s*</);
    expect(SETTINGS_GROUPS.map((group) => group.id)).toEqual([
      "ai_models",
      "personalization",
      "data_sync",
    ]);
  });

  it("keeps bootstrap reads separate from authority reconciliation and cache writes", () => {
    const bootstrap = read("src/i18n/bootstrap.ts");
    const controller = read("src/i18n/localeController.ts");

    expect(bootstrap).not.toMatch(/\.write\(|getUiLocale|setUiLocale|fetch\s*\(/);
    expect(controller).toMatch(/authority\s*\.\s*get\(\)/);
    expect(controller).toMatch(/authority\s*\.\s*put\(locale\)/);
    expect(controller).toContain("writeCache(locale)");
  });

  it("records the exact I18N-1 migrated scopes and sole ArkScope allowlist", () => {
    const migrated = JSON.parse(read("scripts/i18n/migrated-scopes.json")) as {
      scopes: string[];
    };
    const allowlist = JSON.parse(read("scripts/i18n/visible-literal-allowlist.json")) as {
      entries: Array<Record<string, unknown>>;
    };
    const debt = JSON.parse(read("scripts/i18n/visible-literal-debt.json")) as {
      signatures: Array<{ signature: string }>;
    };

    expect(migrated.scopes.filter((scope) => I18N_1_MIGRATED_SCOPES.includes(scope)))
      .toEqual(I18N_1_MIGRATED_SCOPES);
    expect(allowlist.entries.filter(({ file }) => {
      return typeof file === "string" && (
        file === "src/App.tsx"
        || file.startsWith("src/shell/")
        || file === "src/ui/Drawer.tsx"
        || file === "src/ui/BoundedProgress.tsx"
      );
    })).toEqual([ARKSCOPE_ALLOWLIST_ENTRY]);

    const owned = (file: string) => (
      file === "src/App.tsx"
      || file.startsWith("src/shell/")
      || file === "src/ui/Drawer.tsx"
      || file === "src/ui/BoundedProgress.tsx"
    );
    const ownedDebt = debt.signatures.filter(({ signature }) => {
      const [file] = JSON.parse(signature) as [string];
      return owned(file);
    });
    expect(ownedDebt).toEqual([]);
  });

  it("records the exact I18N-2 migrated scopes and stable-value allowlist", () => {
    const migrated = JSON.parse(read("scripts/i18n/migrated-scopes.json")) as {
      scopes: string[];
    };
    const allowlist = JSON.parse(read("scripts/i18n/visible-literal-allowlist.json")) as {
      entries: Array<Record<string, unknown>>;
    };
    const debt = JSON.parse(read("scripts/i18n/visible-literal-debt.json")) as {
      signatures: Array<{ signature: string }>;
    };

    expect(migrated.scopes).toEqual([
      ...I18N_1_MIGRATED_SCOPES,
      ...I18N_2_SETTINGS_SCOPES,
      ...SLICE_5_MIGRATED_SCOPES,
    ]);
    expect(migrated.scopes).toHaveLength(30);
    expect(allowlist.entries).toEqual([
      ARKSCOPE_ALLOWLIST_ENTRY,
      ...I18N_2_SETTINGS_ALLOWLIST_ENTRIES,
    ]);
    expect(new Set(allowlist.entries.map(({ file, kind, literal }) => (
      JSON.stringify([file, kind, literal])
    ))).size).toBe(20);

    const ownedDebt = debt.signatures.filter(({ signature }) => {
      const [file] = JSON.parse(signature) as [string];
      return ownsSettingsDebt(file);
    });
    expect(ownedDebt).toEqual([]);
  });

  it("keeps the public locale selector absent after Settings migration", () => {
    const publicSurfacePaths = [
      "src/App.tsx",
      ...productionFiles("src/shell").map((path) => path.slice(projectRoot.length + 1)),
      ...migratedSettingsFiles,
    ];
    const publicSurfaceSource = publicSurfacePaths.map(read).join("\n");
    const source = [
      publicSurfaceSource,
      read("src/main.tsx"),
      read("src/i18n/LocaleProvider.tsx"),
    ].join("\n");

    expect(source).not.toMatch(/繁體中文|簡體中文|>\s*English\s*</);
    expect(publicSurfaceSource).not.toMatch(
      /(?:Locale|Language)Selector|(?:locale|language)-selector|changeLanguage\s*\(/,
    );
    expect(SETTINGS_GROUPS.map((group) => group.id)).toEqual([
      "ai_models",
      "personalization",
      "data_sync",
    ]);
  });

  it("forbids dynamic Settings keys and direct normal-mode raw diagnostic sinks", () => {
    const source = migratedSettingsFiles.map(read).join("\n");
    expect(source).not.toMatch(/\bt\s*\(\s*(?!\(\s*\$\s*\)\s*=>)/);

    const settingsUiSource = [
      "src/Settings.tsx",
      "src/InvestorProfilePanel.tsx",
      "src/SourceRunProgress.tsx",
      ...migratedSettingsFiles.filter((path) => path.endsWith(".tsx")),
    ].map(read).join("\n");
    const visibleExpressions = [
      ...settingsUiSource.matchAll(/\{([^{}\n]+)\}\s*<\//g),
      ...settingsUiSource.matchAll(/(?:title|label|description|errorMessage)=\{([^{}\n]+)\}/g),
    ].map((match) => match[1].trim());
    const rawDiagnosticSinks = visibleExpressions.filter((expression) => {
      if (/^t\s*\(/.test(expression)) return false;
      if (/Presentation\.message\b/.test(expression)) return false;
      return (
        /\.(?:detail|diagnostic|last_error|lastError|warning|reason|expected|observed|error|message)\b/.test(expression)
        || /\b(?:err|providerErr|oauthErr|rawDiagnostic)\b/.test(expression)
      );
    });
    expect(rawDiagnosticSinks).toEqual([]);

    const diagnosticsOwner = read("src/settings/DeveloperDiagnostics.tsx");
    expect(settingsUiSource).not.toContain('data-testid="developer-diagnostics"');
    expect(diagnosticsOwner).toContain('data-testid="developer-diagnostics"');
    expect(diagnosticsOwner).toContain("<summary>{t(($) => $.errors.diagnostics.title)}</summary>");
  });
});
