import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { SETTINGS_GROUPS } from "../settings/settingsRegistry";

const projectRoot = resolve(import.meta.dirname, "../..");

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
});
