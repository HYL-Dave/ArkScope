import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  FixedTaskRuntimeMap,
  FixedTaskRuntimeSettings,
  ResearchRuntimeSettings,
} from "../api";
import { routeSourceBadge } from "../modelRouteDisplay";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";
import type { SettingsT } from "./settingsCopy";

function RuntimeDiagnostics({ warning, t }: { warning: string | null; t: SettingsT }) {
  if (!warning) return null;
  return (
    <details className="developer-diagnostics">
      <summary>{t(($) => $.errors.diagnostics.title)}</summary>
      <p>
        <strong>{t(($) => $.errors.diagnostics.detail)}</strong>: {warning}
      </p>
    </details>
  );
}
function parseFixedTaskTimeout(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 60 || value > 3600) return null;
  return value;
}

export function FixedTaskRuntimeSection({
  settings,
  saving,
  onSave,
  onReset,
  onNavigationGuardChange,
  developerMode,
}: {
  settings: FixedTaskRuntimeMap;
  saving: boolean;
  onSave: (body: {
    tasks: {
      card_synthesis: { model_timeout_s: number };
      card_translation: { model_timeout_s: number };
    };
  }) => void | Promise<void>;
  onReset: () => void | Promise<void>;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode: boolean;
}) {
  const { t } = useTranslation("settings");
  const [draft, setDraft] = useState({
    card_synthesis: String(settings.card_synthesis.model_timeout_s),
    card_translation: String(settings.card_translation.model_timeout_s),
  });

  useEffect(() => {
    setDraft({
      card_synthesis: String(settings.card_synthesis.model_timeout_s),
      card_translation: String(settings.card_translation.model_timeout_s),
    });
  }, [
    settings.card_synthesis.model_timeout_s,
    settings.card_translation.model_timeout_s,
  ]);

  const synthesis = parseFixedTaskTimeout(draft.card_synthesis);
  const translation = parseFixedTaskTimeout(draft.card_translation);
  const disabled = saving || synthesis == null || translation == null;
  const canReset = settings.card_synthesis.db_saved || settings.card_translation.db_saved;
  const dirty = draft.card_synthesis !== String(settings.card_synthesis.model_timeout_s)
    || draft.card_translation !== String(settings.card_translation.model_timeout_s);

  useEffect(() => {
    onNavigationGuardChange?.(dirty
      ? { dirty: true, busy: false, reason: t(($) => $.runtime.fixed.dirty) }
      : CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [dirty, onNavigationGuardChange, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);
  const rows: Array<{
    key: "card_synthesis" | "card_translation";
    label: string;
    settings: FixedTaskRuntimeSettings;
  }> = [
    {
      key: "card_synthesis",
      label: t(($) => $.runtime.fixed.fields.cardSynthesis),
      settings: settings.card_synthesis,
    },
    {
      key: "card_translation",
      label: t(($) => $.runtime.fixed.fields.cardTranslation),
      settings: settings.card_translation,
    },
  ];

  return (
    <section className="settings-panel research-runtime-panel">
      <div className="settings-panel-head">
        <div>
          <h2>{t(($) => $.runtime.fixed.title)}</h2>
          <p className="muted">{t(($) => $.runtime.fixed.description)}</p>
        </div>
      </div>

      <div className="runtime-limit-grid">
        {rows.map((row) => {
          const badge = routeSourceBadge(row.settings.source, t);
          return (
            <label className="field" key={row.key}>
              <span>{row.label}</span>
              <input
                name={`${row.key}_model_timeout_s`}
                type="number"
                min={60}
                max={3600}
                step={30}
                value={draft[row.key]}
                onChange={(e) => setDraft((prev) => ({
                  ...prev,
                  [row.key]: e.target.value,
                }))}
              />
              <span className={`route-source ${badge.tone}`}>{badge.label}</span>
              <span className="field-help">{t(($) => $.runtime.fixed.help.seconds)}</span>
              {developerMode ? <RuntimeDiagnostics warning={row.settings.warning} t={t} /> : null}
            </label>
          );
        })}
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="btn-ghost small"
          disabled={disabled}
          onClick={() => {
            if (synthesis == null || translation == null) return;
            void onSave({
              tasks: {
                card_synthesis: { model_timeout_s: synthesis },
                card_translation: { model_timeout_s: translation },
              },
            });
          }}
        >
          {saving ? t(($) => $.actions.saving) : t(($) => $.actions.save)}
        </button>
        {canReset && (
          <button
            type="button"
            className="btn-ghost small"
            disabled={saving}
            onClick={() => void onReset()}
          >
            {t(($) => $.actions.reset)}
          </button>
        )}
      </div>
    </section>
  );
}

export function ResearchRuntimeSection({
  settings,
  saving,
  onSave,
  onReset,
  onNavigationGuardChange,
  developerMode,
}: {
  settings: ResearchRuntimeSettings;
  saving: boolean;
  onSave: (body: Pick<ResearchRuntimeSettings, "max_tool_calls" | "session_timeout_s" | "per_tool_timeout_s">) => void | Promise<void>;
  onReset: () => void | Promise<void>;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode: boolean;
}) {
  const { t } = useTranslation("settings");
  const [draft, setDraft] = useState({
    max_tool_calls: String(settings.max_tool_calls),
    session_timeout_s: String(settings.session_timeout_s),
    per_tool_timeout_s: String(settings.per_tool_timeout_s),
  });

  useEffect(() => {
    setDraft({
      max_tool_calls: String(settings.max_tool_calls),
      session_timeout_s: String(settings.session_timeout_s),
      per_tool_timeout_s: String(settings.per_tool_timeout_s),
    });
  }, [settings.max_tool_calls, settings.session_timeout_s, settings.per_tool_timeout_s]);

  const badge = routeSourceBadge(settings.source, t);
  const disabled = saving || !draft.max_tool_calls || !draft.session_timeout_s || !draft.per_tool_timeout_s;
  const dirty = draft.max_tool_calls !== String(settings.max_tool_calls)
    || draft.session_timeout_s !== String(settings.session_timeout_s)
    || draft.per_tool_timeout_s !== String(settings.per_tool_timeout_s);

  useEffect(() => {
    onNavigationGuardChange?.(dirty
      ? { dirty: true, busy: false, reason: t(($) => $.runtime.research.dirty) }
      : CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [dirty, onNavigationGuardChange, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  return (
    <section className="settings-panel research-runtime-panel">
      <div className="settings-panel-head">
        <div>
          <h2>{t(($) => $.runtime.research.title)}</h2>
          <p className="muted">{t(($) => $.runtime.research.description)}</p>
        </div>
        <span className={`route-source ${badge.tone}`}>{badge.label}</span>
      </div>

      {developerMode ? <RuntimeDiagnostics warning={settings.warning} t={t} /> : null}

      <div className="runtime-limit-grid">
        <label className="field">
          <span>{t(($) => $.runtime.research.fields.maxToolCalls)}</span>
          <input
            name="max_tool_calls"
            type="number"
            min={1}
            max={500}
            step={1}
            value={draft.max_tool_calls}
            onChange={(e) => setDraft((prev) => ({ ...prev, max_tool_calls: e.target.value }))}
          />
          <span className="field-help">{t(($) => $.runtime.research.help.maxToolCalls)}</span>
        </label>
        <label className="field">
          <span>{t(($) => $.runtime.research.fields.sessionTimeout)}</span>
          <input
            name="session_timeout_s"
            type="number"
            min={0}
            max={86400}
            step={30}
            value={draft.session_timeout_s}
            onChange={(e) => setDraft((prev) => ({ ...prev, session_timeout_s: e.target.value }))}
          />
          <span className="field-help">{t(($) => $.runtime.research.help.session)}</span>
        </label>
        <label className="field">
          <span>{t(($) => $.runtime.research.fields.perToolTimeout)}</span>
          <input
            name="per_tool_timeout_s"
            type="number"
            min={1}
            max={3600}
            step={5}
            value={draft.per_tool_timeout_s}
            onChange={(e) => setDraft((prev) => ({ ...prev, per_tool_timeout_s: e.target.value }))}
          />
          <span className="field-help">{t(($) => $.runtime.research.help.perTool)}</span>
        </label>
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="btn-ghost small"
          disabled={disabled}
          onClick={() => onSave({
            max_tool_calls: Number(draft.max_tool_calls),
            session_timeout_s: Number(draft.session_timeout_s),
            per_tool_timeout_s: Number(draft.per_tool_timeout_s),
          })}
        >
          {saving ? t(($) => $.actions.saving) : t(($) => $.actions.save)}
        </button>
        {settings.db_saved && (
          <button type="button" className="btn-ghost small" disabled={saving} onClick={() => onReset()}>
            {t(($) => $.actions.reset)}
          </button>
        )}
      </div>
    </section>
  );
}
