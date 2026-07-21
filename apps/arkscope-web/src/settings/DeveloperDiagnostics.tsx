import type { SettingsT } from "./settingsCopy";

export function DeveloperDiagnostics({
  diagnostics,
  t,
}: {
  diagnostics: readonly (string | null | undefined)[];
  t: SettingsT;
}) {
  const visible = diagnostics.filter((value): value is string => !!value);
  if (!visible.length) return null;
  return (
    <details data-testid="developer-diagnostics">
      <summary>{t(($) => $.errors.diagnostics.title)}</summary>
      {visible.map((value, index) => (
        <p key={`${index}:${value}`}>
          <strong>{t(($) => $.errors.diagnostics.detail)}</strong>: {value}
        </p>
      ))}
    </details>
  );
}
