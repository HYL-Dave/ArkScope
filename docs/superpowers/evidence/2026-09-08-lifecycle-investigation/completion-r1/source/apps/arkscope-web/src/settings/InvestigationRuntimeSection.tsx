import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, RefreshCw, RotateCcw, Save, Upload } from "lucide-react";
import { getInvestigationRuntime, saveInvestigationRuntime, resetInvestigationRuntime } from "../api";
import { INVESTIGATION_LIMITS, parseInvestigationRuntime, type InvestigationRuntime } from "../lifecycle/investigationContract";
import { investigationCopy } from "../lifecycle/investigationPresentation";
import { Button, IconButton } from "../ui/Button";
import { CLEAR_SETTINGS_NAVIGATION_GUARD, type SettingsNavigationGuard } from "./settingsNavigationGuard";

export function InvestigationRuntimeSection({ authMode, onNavigationGuardChange }: {
  authMode?: string; onNavigationGuardChange?: (guard: SettingsNavigationGuard) => void;
}) {
  const { i18n } = useTranslation("explore"), locale = i18n.resolvedLanguage === "en" ? "en" : "zh-Hant", copy = investigationCopy(locale);
  const [opened, setOpened] = useState(false), [saved, setSaved] = useState<InvestigationRuntime | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({}), [busy, setBusy] = useState(false), [error, setError] = useState(false);
  const [success, setSuccess] = useState(false), [readVersion, setReadVersion] = useState(0); const file = useRef<HTMLInputElement>(null);
  const keys = Object.keys(INVESTIGATION_LIMITS) as (keyof InvestigationRuntime)[];
  const dirty = !!saved && keys.some(key => draft[key] !== String(saved[key]));
  let parsed: InvestigationRuntime | null = null;
  try { if (keys.every(key => draft[key]?.trim())) parsed = parseInvestigationRuntime(Object.fromEntries(keys.map(key => [key, Number(draft[key])]))); } catch { /* Invalid drafts remain visible, never clamped. */ }
  function adopt(value: InvestigationRuntime) { setSaved(value); setDraft(Object.fromEntries(keys.map(key => [key, String(value[key])]))); }
  useEffect(() => { if (!opened || saved) return; let cancelled = false; setBusy(true); setError(false);
    void getInvestigationRuntime().then(value => { if (!cancelled) adopt(value); }).catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setBusy(false); }); return () => { cancelled = true; };
  }, [opened, readVersion]);
  useEffect(() => { onNavigationGuardChange?.({ busy, dirty, reason: busy ? copy.loading : dirty ? copy.dirty : null }); }, [busy, dirty, copy.loading, copy.dirty, onNavigationGuardChange]);
  useEffect(() => () => onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD), [onNavigationGuardChange]);
  async function save(reset = false) { if (busy || (!reset && !parsed)) return; setBusy(true); setError(false); setSuccess(false);
    try { adopt(reset ? await resetInvestigationRuntime() : await saveInvestigationRuntime(parsed!)); setSuccess(true); }
    catch { setError(true); } finally { setBusy(false); } }
  async function importFile(value?: File) { if (!value || busy) return; setError(false); setSuccess(false);
    try { const next = parseInvestigationRuntime(JSON.parse(await value.text())); setDraft(Object.fromEntries(keys.map(key => [key, String(next[key])]))); }
    catch { setError(true); } finally { if (file.current) file.current.value = ""; } }
  function exportFile() { if (!saved) return; const url = URL.createObjectURL(new Blob([JSON.stringify(saved, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "lifecycle-investigation-limits.json"; a.click(); URL.revokeObjectURL(url); }
  return <details className="investigation-runtime" onToggle={e => { if (e.currentTarget.open) setOpened(true); }}>
    <summary>{copy.settingsTitle}{dirty && <> · {copy.dirty}</>}</summary>
    {opened && <><div className="investigation-runtime-fields">{keys.map(key => <label className="field" key={key}><span>{copy.limits[key]}</span>
      <input type="number" min={INVESTIGATION_LIMITS[key][0]} max={INVESTIGATION_LIMITS[key][1]} step={1} value={draft[key] ?? ""}
        disabled={busy || !saved || (key === "api_output_tokens" && !!authMode && authMode !== "api_key")}
        onChange={e => { setDraft(old => ({ ...old, [key]: e.target.value })); setSuccess(false); }} />
    </label>)}</div><p className="tiny">{copy.apiOnly}</p>
      {error && <p role="alert">{copy.settingsError}</p>}{dirty && !parsed && <p role="alert">{copy.settingsInvalid}</p>}
      {success && <p role="status">{copy.saved}</p>}
      <div className="lifecycle-commands"><Button icon={<Save size={15} />} disabled={busy || !dirty || !parsed} onClick={() => void save()}>{copy.save}</Button>
        {!saved && <IconButton label={copy.refresh} icon={<RefreshCw size={15} />} disabled={busy} onClick={() => setReadVersion(x => x + 1)} />}
        <IconButton label={copy.reset} icon={<RotateCcw size={15} />} disabled={busy || !saved} onClick={() => void save(true)} />
        <IconButton label={copy.import} icon={<Upload size={15} />} disabled={busy || !saved} onClick={() => file.current?.click()} />
        <IconButton label={copy.export} icon={<Download size={15} />} disabled={busy || !saved} onClick={exportFile} />
        <input ref={file} type="file" accept="application/json,.json" hidden onChange={e => void importFile(e.target.files?.[0])} />
      </div></>}
  </details>;
}
