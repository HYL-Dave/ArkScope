import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw, RotateCcw, Save, Undo2 } from "lucide-react";
import { getSAFinancialAcquisitionSettings, putSAFinancialAcquisitionSettings, type SAFinancialAcquisitionView } from "../api";
import { IconButton } from "../ui/Button";
import { CLEAR_SETTINGS_NAVIGATION_GUARD, type SettingsNavigationGuardReporter } from "./settingsNavigationGuard";

export function SAFinancialAcquisitionSection({ onNavigationGuardChange }: { onNavigationGuardChange?: SettingsNavigationGuardReporter }) {
  const { t } = useTranslation("settings");
  const [view, setView] = useState<SAFinancialAcquisitionView | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [readError, setReadError] = useState(false), [saveError, setSaveError] = useState(false);
  const mounted = useRef(true);
  const dirty = draft !== null;
  const value = draft ?? (view?.values ? String(view.values.parser_failure_ticker_threshold) : "");
  const valid = /^(0|[1-9]\d*)$/.test(value) && Number.isSafeInteger(Number(value));
  useEffect(() => {
    mounted.current = true;
    getSAFinancialAcquisitionSettings().then(v => { if (mounted.current) setView(v); }).catch(() => { if (mounted.current) setReadError(true); });
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    onNavigationGuardChange?.({ dirty, busy, reason: busy ? t(($) => $.dataSources.guard.busy) : dirty ? t(($) => $.dataSources.guard.dirty) : null });
  }, [dirty, busy, onNavigationGuardChange, t]);
  useEffect(() => () => onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD), [onNavigationGuardChange]);
  async function save() {
    if (!dirty || !valid || busy) return;
    setBusy(true); setSaveError(false);
    try {
      const next = await putSAFinancialAcquisitionSettings({ parser_failure_ticker_threshold: Number(value) });
      if (mounted.current) { setView(next); setDraft(null); }
    } catch { if (mounted.current) setSaveError(true); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function reload() {
    if (dirty || busy) return;
    setBusy(true);
    try {
      const next = await getSAFinancialAcquisitionSettings();
      if (mounted.current) { setView(next); setReadError(false); }
    } catch { if (mounted.current) { setReadError(true); setView(null); } }
    finally { if (mounted.current) setBusy(false); }
  }
  return <section className="sa-article-settings" aria-labelledby="sa-financial-settings-title">
    <div className="settings-section-head">
      <h4 id="sa-financial-settings-title">{t(($) => $.dataSources.financialCapture.title)}</h4>
      <div className="data-route-actions">
        <IconButton label={t(($) => $.dataSources.financialCapture.refresh)} icon={<RefreshCw size={16} />} disabled={dirty || busy} onClick={() => void reload()} />
        <IconButton label={t(($) => $.dataSources.financialCapture.save)} icon={<Save size={16} />} disabled={!dirty || !valid || busy} onClick={() => void save()} />
        <IconButton label={t(($) => $.dataSources.financialCapture.undo)} icon={<Undo2 size={16} />} disabled={!dirty || busy} onClick={() => { setDraft(null); setSaveError(false); }} />
        <IconButton label={t(($) => $.dataSources.financialCapture.defaults)} icon={<RotateCcw size={16} />} disabled={!view || busy} onClick={() => view && setDraft(String(view.defaults.parser_failure_ticker_threshold))} />
      </div>
    </div>
    {readError ? <p role="alert">{t(($) => $.dataSources.financialCapture.unavailable)}</p> : !view ? <p>{t(($) => $.dataSources.loading)}</p> : <>
      {view.error_code ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.financialCapture.invalidSaved)}</p> : null}
      <fieldset className="ui-inline-form sa-article-fields" disabled={busy || !view.values && !dirty}>
        <label>{t(($) => $.dataSources.financialCapture.threshold)}
          <input type="number" min={0} max={Number.MAX_SAFE_INTEGER} step={1} inputMode="numeric" value={value}
            aria-label={t(($) => $.dataSources.financialCapture.threshold)} onChange={e => setDraft(e.target.value)} />
        </label>
      </fieldset>
    </>}
    {saveError ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.financialCapture.saveError)}</p> : null}
  </section>;
}
