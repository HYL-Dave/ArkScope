import React from 'react';
import i18next from 'i18next';
import { createRoot } from 'react-dom/client';
import { initializeI18n } from '@product/i18n';
import { LocaleProvider } from '@product/i18n/LocaleProvider';
import { createUiLocaleController } from '@product/i18n/localeController';
import '@product/styles.css';
import '@product/shell/shell.css';
import '@product/ui/primitives.css';
import '@product/settings/settings.css';

window.arkscope = { apiBase: location.origin + '/api' } as any;
const language = new URLSearchParams(location.search).get('lang') || 'en';
initializeI18n(i18next, language as 'en' | 'zh-Hant');
const { SettingsView } = await import('@product/Settings');
const controller = createUiLocaleController({ initialLocale: language as 'en' | 'zh-Hant',
  authority: { get: async () => ({ locale: language as 'en' | 'zh-Hant', source: 'stored' }),
    put: async locale => ({ locale, source: 'stored' }) },
  applyLocale: locale => { void i18next.changeLanguage(locale); }, writeCache: () => {} });
createRoot(document.getElementById('root')!).render(
  <LocaleProvider controller={controller}>
  <SettingsView runtime={null} developerMode={false} onRuntimeChanged={async () => {}}
    navigationRequest={{ sequence: 1, target: { kind: 'settings_section', section: 'sec_structured_storage' } }} />
  </LocaleProvider>
);
