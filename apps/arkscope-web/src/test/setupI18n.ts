import i18n from "i18next";
import { beforeEach } from "vitest";

import { initializeI18n } from "../i18n/resources";

if (!i18n.isInitialized) initializeI18n(i18n, "zh-Hant");

beforeEach(() => {
  void i18n.changeLanguage("zh-Hant");
  if (typeof document !== "undefined") document.documentElement.lang = "zh-Hant";
});
