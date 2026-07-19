import { StrictMode } from "react";
import i18n from "i18next";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";
import { App } from "./App";
import { getUiLocale, setUiLocale } from "./api";
import {
  LocaleProvider,
  bootstrapUiLocale,
  browserUiLocaleCache,
  createUiLocaleController,
  type UiLocale,
} from "./i18n";
import { installUiTokens } from "./ui/tokens";
import "./styles.css";
import "./shell/shell.css";
import "./ui/primitives.css";
import "./settings/settings.css";

installUiTokens(document.documentElement);

const initialLocale = bootstrapUiLocale({
  instance: i18n,
  cache: browserUiLocaleCache,
  root: document.documentElement,
});

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("root element #root not found");

const applyLocale = (locale: UiLocale) => {
  void i18n.changeLanguage(locale);
  document.documentElement.lang = locale;
};

const localeController = createUiLocaleController({
  initialLocale,
  authority: {
    get: getUiLocale,
    put: setUiLocale,
  },
  applyLocale,
  writeCache: (locale) => browserUiLocaleCache.write(locale),
});

const root = createRoot(rootEl);
root.render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <LocaleProvider controller={localeController}>
        <App />
      </LocaleProvider>
    </I18nextProvider>
  </StrictMode>,
);
