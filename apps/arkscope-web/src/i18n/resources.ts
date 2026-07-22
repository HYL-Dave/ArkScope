import type { i18n } from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./resources/en/common";
import enResearch from "./resources/en/research";
import enSettings from "./resources/en/settings";
import enShell from "./resources/en/shell";
import zhHantCommon from "./resources/zh-Hant/common";
import zhHantResearch from "./resources/zh-Hant/research";
import zhHantSettings from "./resources/zh-Hant/settings";
import zhHantShell from "./resources/zh-Hant/shell";

export const defaultNamespace = "common" as const;
export const resourceNamespaces = ["common", "shell", "settings", "research"] as const;

export const resources = {
  "zh-Hant": {
    common: zhHantCommon,
    shell: zhHantShell,
    settings: zhHantSettings,
    research: zhHantResearch,
  },
  en: {
    common: enCommon,
    shell: enShell,
    settings: enSettings,
    research: enResearch,
  },
} as const;

type ResourceLocale = keyof typeof resources;

function safeMissingCopy(instance: i18n): string {
  const locale: ResourceLocale = instance.language === "en" ? "en" : "zh-Hant";
  return resources[locale].common.i18n.missingTranslation;
}

export function initializeI18n(
  instance: i18n,
  initialLocale: ResourceLocale,
): i18n {
  instance.use(initReactI18next);
  void instance.init({
    resources,
    lng: initialLocale,
    fallbackLng: "zh-Hant",
    supportedLngs: ["zh-Hant", "en"],
    load: "currentOnly",
    ns: resourceNamespaces,
    defaultNS: defaultNamespace,
    initAsync: false,
    debug: import.meta.env.DEV,
    returnEmptyString: false,
    parseMissingKeyHandler: () => safeMissingCopy(instance),
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: false,
    },
  });
  return instance;
}
