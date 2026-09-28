import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw, RotateCcw, Save, Undo2 } from "lucide-react";
import { getSAArticleAcquisitionSettings, putSAArticleAcquisitionSettings, getSABodyRecoveryStatus,
  type SAArticleAcquisitionValues, type SAArticleAcquisitionView, type SABodyRecoveryStatus } from "../api";
import { IconButton } from "../ui/Button";
import { CLEAR_SETTINGS_NAVIGATION_GUARD, type SettingsNavigationGuardReporter } from "./settingsNavigationGuard";

type Draft = Omit<SAArticleAcquisitionValues, "max_articles_per_job" | "body_lookback_days"> & {
  max_articles_per_job: string; body_lookback_days: string;
};
const draftOf = (v: SAArticleAcquisitionValues): Draft => ({ ...v, max_articles_per_job: String(v.max_articles_per_job), body_lookback_days: String(v.body_lookback_days) });
function valuesOf(draft: Draft): SAArticleAcquisitionValues | null {
  const integer = (s: string) => /^(0|[1-9]\d*)$/.test(s) && Number.isSafeInteger(Number(s));
  if (!integer(draft.max_articles_per_job) || !integer(draft.body_lookback_days)) return null;
  return { ...draft, max_articles_per_job: Number(draft.max_articles_per_job), body_lookback_days: Number(draft.body_lookback_days) };
}

export function SAArticleAcquisitionSection({ onNavigationGuardChange }: { onNavigationGuardChange?: SettingsNavigationGuardReporter }) {
  const { t, i18n } = useTranslation("settings");
  const [view, setView] = useState<SAArticleAcquisitionView | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [job, setJob] = useState<SABodyRecoveryStatus | null>(null);
  const [readError, setReadError] = useState(false), [jobError, setJobError] = useState(false), [saveError, setSaveError] = useState(false);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const dirty = draft !== null;
  useEffect(() => {
    mounted.current = true;
    getSAArticleAcquisitionSettings().then(v => { if (mounted.current) setView(v); }).catch(() => { if (mounted.current) setReadError(true); });
    getSABodyRecoveryStatus().then(v => { if (mounted.current) setJob(v); }).catch(() => { if (mounted.current) setJobError(true); });
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    onNavigationGuardChange?.({ dirty, busy, reason: busy ? t(($) => $.dataSources.guard.busy) : dirty ? t(($) => $.dataSources.guard.dirty) : null });
  }, [dirty, busy, onNavigationGuardChange, t]);
  useEffect(() => () => onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD), [onNavigationGuardChange]);
  const current = draft ?? (view?.values ? draftOf(view.values) : null);
  const values = current ? valuesOf(current) : null;
  async function save() {
    if (!values || busy || !dirty) return;
    setBusy(true); setSaveError(false);
    try {
      const next = await putSAArticleAcquisitionSettings(values);
      if (mounted.current) { setView(next); setDraft(null); }
    } catch { if (mounted.current) setSaveError(true); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function reload() {
    if (dirty || busy) return;
    setBusy(true);
    const results = await Promise.allSettled([getSAArticleAcquisitionSettings(), getSABodyRecoveryStatus()]);
    if (!mounted.current) return;
    const [settings, progress] = results;
    setReadError(settings.status !== "fulfilled");
    setView(settings.status === "fulfilled" ? settings.value : null);
    setJobError(progress.status !== "fulfilled");
    setJob(progress.status === "fulfilled" ? progress.value : null);
    setBusy(false);
  }
  const counts = job?.counts;
  const nextTime = job?.next_eligible_at ? new Date(job.next_eligible_at) : null;
  const states: Record<SABodyRecoveryStatus["state"], string> = {
    not_started: t(($) => $.dataSources.articles.states.not_started), pending: t(($) => $.dataSources.articles.states.pending),
    running: t(($) => $.dataSources.articles.states.running), waiting: t(($) => $.dataSources.articles.states.waiting),
    paused: t(($) => $.dataSources.articles.states.paused), cancelling: t(($) => $.dataSources.articles.states.cancelling),
    cancelled: t(($) => $.dataSources.articles.states.cancelled), partial: t(($) => $.dataSources.articles.states.partial),
    complete: t(($) => $.dataSources.articles.states.complete),
  };
  return <section className="sa-article-settings" aria-labelledby="sa-article-settings-title">
    <div className="settings-section-head">
      <h4 id="sa-article-settings-title">{t(($) => $.dataSources.articles.title)}</h4>
      <div className="data-route-actions">
        <IconButton label={t(($) => $.dataSources.articles.refresh)} icon={<RefreshCw size={16} />} disabled={dirty || busy} onClick={() => void reload()} />
        <IconButton label={t(($) => $.dataSources.articles.save)} icon={<Save size={16} />} disabled={!dirty || !values || busy} onClick={() => void save()} />
        <IconButton label={t(($) => $.dataSources.articles.undo)} icon={<Undo2 size={16} />} disabled={!dirty || busy} onClick={() => { setDraft(null); setSaveError(false); }} />
        <IconButton label={t(($) => $.dataSources.articles.defaults)} icon={<RotateCcw size={16} />} disabled={!view || busy} onClick={() => view && setDraft(draftOf(view.defaults))} />
      </div>
    </div>
    {readError ? <p role="alert">{t(($) => $.dataSources.articles.unavailable)}</p> : !view ? <p>{t(($) => $.dataSources.loading)}</p> : <>
      {view.error_code ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.articles.invalidSaved)}</p> : null}
      <fieldset className="ui-inline-form sa-article-fields" disabled={busy || !current}>
        <label>{t(($) => $.dataSources.articles.limit)}
          <input type="number" min={0} max={Number.MAX_SAFE_INTEGER} step={1} inputMode="numeric" value={current?.max_articles_per_job ?? ""}
            aria-label={t(($) => $.dataSources.articles.limit)} onChange={e => current && setDraft({ ...current, max_articles_per_job: e.target.value })} />
        </label>
        <label>{t(($) => $.dataSources.articles.age)}
          <input type="number" min={0} max={Number.MAX_SAFE_INTEGER} step={1} inputMode="numeric" value={current?.body_lookback_days ?? ""}
            aria-label={t(($) => $.dataSources.articles.age)} onChange={e => current && setDraft({ ...current, body_lookback_days: e.target.value })} />
        </label>
        <label>{t(($) => $.dataSources.articles.bodyScope)}
          <select value={current?.body_scope ?? ""} aria-label={t(($) => $.dataSources.articles.bodyScope)} onChange={e => current && setDraft({ ...current, body_scope: e.target.value as Draft["body_scope"] })}>
            {!current ? <option value="" /> : null}
            <option value="all_retained">{t(($) => $.dataSources.articles.allRetained)}</option><option value="current">{t(($) => $.dataSources.articles.current)}</option>
          </select>
        </label>
        <label>{t(($) => $.dataSources.articles.commentScope)}
          <select value={current?.comment_scope ?? ""} aria-label={t(($) => $.dataSources.articles.commentScope)} onChange={e => current && setDraft({ ...current, comment_scope: e.target.value as Draft["comment_scope"] })}>
            {!current ? <option value="" /> : null}
            <option value="current">{t(($) => $.dataSources.articles.current)}</option><option value="tracked">{t(($) => $.dataSources.articles.tracked)}</option>
          </select>
        </label>
      </fieldset>
    </>}
    {saveError ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.articles.saveError)}</p> : null}
    <div className="sa-body-progress" role="status">
      <strong>{t(($) => $.dataSources.articles.progress)}</strong>
      {jobError ? <span>{t(($) => $.dataSources.articles.progressUnavailable)}</span> : job ? <>
        <span>{states[job.state]}</span>
        {counts ? <>
          <span>{t(($) => $.dataSources.articles.counts, counts)}</span>
          <progress max={Math.max(1, counts.selected)} value={counts.saved + counts.skipped + counts.failed} aria-label={t(($) => $.dataSources.articles.progress)} />
        </> : null}
        {job.reason_code ? <code>{job.reason_code}</code> : null}
        {nextTime && Number.isFinite(nextTime.getTime()) ? <span>{t(($) => $.dataSources.articles.next, { time: nextTime.toLocaleString(i18n.language) })}</span> : null}
      </> : <span>{t(($) => $.dataSources.loading)}</span>}
    </div>
  </section>;
}
