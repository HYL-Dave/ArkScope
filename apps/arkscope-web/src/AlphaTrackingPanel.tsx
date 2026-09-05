import { useCallback, useEffect, useRef, useState } from "react";
import { EyeOff, Plus, RefreshCw, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { commandAlphaTracking, getAlphaTracking, refreshAlphaTracking, type AlphaTrackingMembership, type AlphaTrackingResponse } from "./api";
import { Button, ConfirmDialog } from "./ui";

export function AlphaTrackingPanel({ status, onOpenTicker, onChanged }: {
  status: "current" | "closed";
  onOpenTicker: (ticker: string) => void;
  onChanged: () => void;
}) {
  const { t } = useTranslation("explore");
  const commands = {
    remove: t(($) => $.alphaTracking.commands.remove),
    restore: t(($) => $.alphaTracking.commands.restore),
    accept: t(($) => $.alphaTracking.commands.accept),
  };
  const states = {
    tracking: t(($) => $.alphaTracking.states.tracking),
    removed: t(($) => $.alphaTracking.states.removed),
    candidate: t(($) => $.alphaTracking.states.candidate),
  };
  const reasons = {
    current_observed: t(($) => $.alphaTracking.reasons.current_observed),
    bootstrap_accepted: t(($) => $.alphaTracking.reasons.bootstrap_accepted),
    capture_gap: t(($) => $.alphaTracking.reasons.capture_gap),
    identity_ambiguous: t(($) => $.alphaTracking.reasons.identity_ambiguous),
    related_security: t(($) => $.alphaTracking.reasons.related_security),
    user_removed: t(($) => $.alphaTracking.reasons.user_removed),
    user_restored: t(($) => $.alphaTracking.reasons.user_restored),
    user_accepted: t(($) => $.alphaTracking.reasons.user_accepted),
    terminal_delisting: t(($) => $.alphaTracking.reasons.terminal_delisting),
  };
  const [data, setData] = useState<AlphaTrackingResponse | null>(null);
  const [state, setState] = useState<AlphaTrackingMembership["state"]>("tracking");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState<{ row: AlphaTrackingMembership; action: "remove" | "restore" | "accept" } | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const request = useRef(0);
  const mounted = useRef(true);
  const load = useCallback(async (refresh = false) => {
    const id = ++request.current;
    setBusy(true);
    setFailed(false);
    try {
      const result = await (refresh ? refreshAlphaTracking() : getAlphaTracking());
      if (request.current === id) setData(result);
    } catch {
      if (request.current === id) setFailed(true);
    } finally {
      if (request.current === id) setBusy(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void load();
    return () => { mounted.current = false; request.current += 1; };
  }, [load]);
  const commit = async () => {
    if (!pending || busy) return;
    setBusy(true);
    setFailed(false);
    try {
      await commandAlphaTracking(pending.row.membership_id, pending.action);
      if (!mounted.current) return;
      setPending(null);
      await load();
      if (mounted.current) onChanged();
    } catch {
      if (mounted.current) setFailed(true);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  const rows = data?.memberships.filter((row) => row.portfolio_status === status && row.state === state && row.ticker.includes(query.trim().toUpperCase())) ?? [];
  const consequence = !pending ? "" : pending.action === "remove"
    ? t(($) => $.alphaTracking.confirm.remove, { ticker: pending.row.ticker })
    : pending.action === "restore"
      ? t(($) => $.alphaTracking.confirm.restore, { ticker: pending.row.ticker })
      : t(($) => $.alphaTracking.confirm.accept, { ticker: pending.row.ticker });
  return <section aria-busy={busy}>
    <h3 ref={heading} tabIndex={-1}>{status === "closed" ? t(($) => $.alphaTracking.former) : t(($) => $.alphaTracking.current)}</h3>
    <div className="ui-inline-form" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(110px, 160px) auto", maxWidth: 500, marginBlock: 12 }}>
      <label>{t(($) => $.alphaTracking.ticker)}<input aria-label={t(($) => $.alphaTracking.ticker)} value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <label>{t(($) => $.alphaTracking.state)}<select aria-label={t(($) => $.alphaTracking.state)} value={state} onChange={(event) => setState(event.target.value as AlphaTrackingMembership["state"])}>
        <option value="tracking">{t(($) => $.alphaTracking.states.tracking)}</option>
        <option value="removed">{t(($) => $.alphaTracking.states.removed)}</option>
        <option value="candidate">{t(($) => $.alphaTracking.states.candidate)}</option>
      </select></label>
      <Button icon={<RefreshCw size={16} />} title={t(($) => $.alphaTracking.refresh)} aria-label={t(($) => $.alphaTracking.refresh)} disabled={busy} onClick={() => void load(true)} />
    </div>
    {failed && <p role="alert" className="error">{t(($) => $.alphaTracking.failed)}</p>}
    {data?.available && data.sync_status !== "current" && <p role="status" className="muted">
      {data.sync_status === "pending" ? t(($) => $.alphaTracking.syncPending) : t(($) => $.alphaTracking.syncUnavailable)}
    </p>}
    {data?.available === false ? <p role="status">{t(($) => $.alphaTracking.unavailable)}</p> : (
      <div style={{ overflowX: "auto" }}><table className="wl" style={{ minWidth: 560 }}>
        <thead><tr><th>{t(($) => $.alphaTracking.ticker)}</th><th>{t(($) => $.alphaTracking.pickedDate)}</th><th>{t(($) => $.alphaTracking.state)}</th><th>{t(($) => $.alphaTracking.reason)}</th><th>{t(($) => $.alphaTracking.actions)}</th></tr></thead>
        <tbody>{rows.map((row) => {
          const action = row.state === "candidate" ? "accept" : row.state === "removed" ? "restore" : "remove";
          const canChange = row.state === "candidate" || (status === "closed" && row.reason !== "terminal_delisting");
          const label = commands[action];
          return <tr key={row.membership_id}>
            <td><button className="btn-ghost" onClick={() => onOpenTicker(row.ticker)}>{row.ticker}</button></td>
            <td>{row.picked_date}</td><td>{states[row.state]}</td><td>{reasons[row.reason]}</td>
            <td>{canChange && <Button title={label} aria-label={t(($) => $.alphaTracking.commandForTicker, { command: label, ticker: row.ticker })} disabled={busy} icon={action === "remove" ? <EyeOff size={16} /> : action === "restore" ? <RotateCcw size={16} /> : <Plus size={16} />} onClick={(event) => { trigger.current = event.currentTarget; setPending({ row, action }); }} />}</td>
          </tr>;
        })}</tbody>
      </table>{!busy && rows.length === 0 && <p className="muted">{t(($) => $.alphaTracking.empty)}</p>}</div>
    )}
    <ConfirmDialog open={pending !== null} title={pending ? commands[pending.action] : ""}
      consequence={consequence}
      confirmLabel={pending ? commands[pending.action] : ""}
      busy={busy} onConfirm={() => void commit()} onCancel={() => setPending(null)} returnFocusRef={trigger} fallbackFocusRef={heading} />
  </section>;
}
