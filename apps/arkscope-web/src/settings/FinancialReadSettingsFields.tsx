import { useTranslation } from "react-i18next";
import { RotateCcw, Save, Undo2 } from "lucide-react";
import type { FinancialReadSettingsValues, FinancialReadSettingsView } from "../api";
import { IconButton } from "../ui/Button";

const periods = ["annual", "quarterly"] as const;
const kinds = ["income_statement", "balance_sheet", "cash_flow_statement"] as const;
type Period = typeof periods[number];
type Kind = typeof kinds[number];
export type FinancialReadDraft = {
  limited: boolean; chars: string;
  periods: Record<Period, Record<Kind, string>>;
};

export function financialReadDraft(values: FinancialReadSettingsValues, defaults: FinancialReadSettingsValues): FinancialReadDraft {
  const row = (period: Period) => Object.fromEntries(kinds.map((kind) => [kind, String(values.fd_periods[period][kind])])) as Record<Kind, string>;
  return { limited: values.tool_output_chars !== 0, chars: String(values.tool_output_chars || defaults.tool_output_chars),
    periods: { annual: row("annual"), quarterly: row("quarterly") } };
}

function integer(value: string, maximum: number): number | null {
  if (!/^[1-9]\d*$/.test(value)) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number <= maximum ? number : null;
}

export function financialReadValues(draft: FinancialReadDraft): FinancialReadSettingsValues | null {
  const chars = draft.limited ? integer(draft.chars, Number.MAX_SAFE_INTEGER) : 0;
  if (chars === null) return null;
  const values = { tool_output_chars: chars, fd_periods: { annual: {}, quarterly: {} } } as FinancialReadSettingsValues;
  for (const period of periods) for (const kind of kinds) {
    const count = integer(draft.periods[period][kind], 2 ** 31 - 1);
    if (count === null) return null;
    values.fd_periods[period][kind] = count;
  }
  return values;
}

export function FinancialReadSettingsFields({ view, draft, onChange, onSave, onUndo, dirty, blocked, busy, invalid }: {
  view: FinancialReadSettingsView; draft: FinancialReadDraft | null;
  onChange: (value: FinancialReadDraft) => void; onSave: () => void; onUndo: () => void;
  dirty: boolean; blocked: boolean; busy: boolean; invalid: boolean;
}) {
  const { t } = useTranslation("settings");
  const current = draft ?? financialReadDraft(view.values ?? view.defaults, view.defaults);
  const unavailable = view.values === null && draft === null;
  const parsed = financialReadValues(current);
  const label = (period: Period) => period === "annual" ? t(($) => $.dataSources.routing.read.annual) : t(($) => $.dataSources.routing.read.quarterly);
  const kindLabel = (kind: Kind) => kind === "income_statement" ? t(($) => $.dataSources.routing.read.income)
    : kind === "balance_sheet" ? t(($) => $.dataSources.routing.read.balance) : t(($) => $.dataSources.routing.read.cashflow);
  return <div className="financial-read-settings">
    <div className="settings-section-head">
      <h4>{t(($) => $.dataSources.routing.read.title)}</h4>
      <div className="data-route-actions">
        <IconButton label={t(($) => $.dataSources.routing.read.save)} icon={<Save size={16} />}
          disabled={blocked || !dirty} busy={busy} onClick={onSave} />
        <IconButton label={t(($) => $.dataSources.routing.read.undo)} icon={<Undo2 size={16} />}
          disabled={blocked || !dirty} onClick={onUndo} />
        <IconButton label={t(($) => $.dataSources.routing.read.defaults)} icon={<RotateCcw size={16} />}
          disabled={blocked} onClick={() => onChange(financialReadDraft(view.defaults, view.defaults))} />
      </div>
    </div>
    {view.error_code ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.routing.read.invalidSaved)}</p> : null}
    <fieldset className="financial-read-fields" disabled={blocked || unavailable}>
      <div className="financial-read-output">
        <label className="data-route-budget-toggle">
          <input type="checkbox" aria-label={t(($) => $.dataSources.routing.read.limited)} checked={current.limited}
            onChange={(event) => onChange({ ...current, limited: event.target.checked })} />
          {t(($) => $.dataSources.routing.read.limited)}
        </label>
        <label>{t(($) => $.dataSources.routing.read.chars)}
          <input type="number" min={1} max={Number.MAX_SAFE_INTEGER} step={1} inputMode="numeric" value={current.chars}
            aria-label={t(($) => $.dataSources.routing.read.chars)} disabled={!current.limited}
            onChange={(event) => onChange({ ...current, chars: event.target.value })} />
        </label>
      </div>
      <p className="muted tiny">{current.limited ? t(($) => $.dataSources.routing.read.modelLimit) : t(($) => $.dataSources.routing.read.unlimited)}</p>
      <table className="financial-read-periods">
        <caption>{t(($) => $.dataSources.routing.read.history)}</caption>
        <thead><tr><th scope="col">{t(($) => $.dataSources.routing.read.statement)}</th>
          {periods.map((period) => <th key={period} scope="col">{label(period)}</th>)}
        </tr></thead>
        <tbody>{kinds.map((kind) => <tr key={kind}>
          <th scope="row">{kindLabel(kind)}</th>
          {periods.map((period) => <td key={period}>
            <input type="number" min={1} max={2 ** 31 - 1} step={1} inputMode="numeric" value={current.periods[period][kind]}
              aria-label={t(($) => $.dataSources.routing.read.periodLabel, { statement: kindLabel(kind), period: label(period) })}
              onChange={(event) => onChange({ ...current, periods: { ...current.periods,
                [period]: { ...current.periods[period], [kind]: event.target.value } } })} />
          </td>)}
        </tr>)}</tbody>
      </table>
      {parsed && !unavailable ? <div className="financial-read-estimate muted tiny" aria-live="polite">
        {periods.map((period) => <span key={period}>{t(($) => $.dataSources.routing.read.pages, {
          period: label(period), count: kinds.reduce((total, kind) => total + Math.ceil(parsed.fd_periods[period][kind] / 10), 0),
        })}</span>)}
      </div> : null}
      <p className="muted tiny">{t(($) => $.dataSources.routing.read.costBasis)}</p>
    </fieldset>
    {invalid ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.routing.read.invalid)}</p> : null}
  </div>;
}
