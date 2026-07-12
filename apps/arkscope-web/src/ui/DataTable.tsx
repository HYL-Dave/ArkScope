import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type Key,
  type ReactNode,
} from "react";
import { MoreHorizontal } from "lucide-react";

import { IconButton } from "./Button";

export interface DataTableColumn<Row> {
  id: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

export interface DataTableAction<Row> {
  id: string;
  label: string;
  tone?: "default" | "danger";
  disabled?: boolean;
  onSelect: (row: Row, trigger: HTMLButtonElement) => void;
}

function RowActionMenu<Row>({
  row,
  label,
  actions,
}: {
  row: Row;
  label: string;
  actions: DataTableAction<Row>[];
}) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState<"up" | "down">("down");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !menuRef.current || !triggerRef.current) return;
    const menu = menuRef.current.getBoundingClientRect();
    const trigger = triggerRef.current.getBoundingClientRect();
    setPlacement(
      menu.bottom > window.innerHeight && trigger.top >= menu.height ? "up" : "down",
    );
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ui-row-actions" ref={rootRef}>
      <IconButton
        ref={triggerRef}
        label={`${label} 操作`}
        tone="ghost"
        size="compact"
        icon={<MoreHorizontal size={17} />}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      />
      {open ? (
        <div
          ref={menuRef}
          className="ui-row-action-menu"
          role="menu"
          data-placement={placement}
        >
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              role="menuitem"
              className={action.tone === "danger" ? "danger" : ""}
              disabled={action.disabled}
              onClick={() => {
                setOpen(false);
                if (triggerRef.current) action.onSelect(row, triggerRef.current);
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function DataTable<Row>({
  ariaLabel,
  rows,
  columns,
  rowKey,
  rowLabel,
  emptyText,
  actions,
  renderExpandedRow,
}: {
  ariaLabel: string;
  rows: readonly Row[];
  columns: readonly DataTableColumn<Row>[];
  rowKey: (row: Row) => Key;
  rowLabel: (row: Row) => string;
  emptyText: string;
  actions?: (row: Row) => DataTableAction<Row>[];
  renderExpandedRow?: (row: Row) => ReactNode;
}) {
  const actionColumn = Boolean(actions);
  const columnCount = columns.length + (actionColumn ? 1 : 0);

  return (
    <div className="ui-data-table-wrap">
      <table className="ui-data-table" aria-label={ariaLabel}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                className={column.className}
                data-align={column.align ?? "left"}
              >
                {column.header}
              </th>
            ))}
            {actionColumn ? <th className="ui-data-table-action-head">操作</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="ui-data-table-empty" colSpan={columnCount}>{emptyText}</td>
            </tr>
          ) : rows.map((row) => {
            const expanded = renderExpandedRow?.(row);
            const rowActions = actions?.(row) ?? [];
            return (
              <Fragment key={rowKey(row)}>
                <tr>
                  {columns.map((column) => (
                    <td
                      key={column.id}
                      className={column.className}
                      data-align={column.align ?? "left"}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                  {actionColumn ? (
                    <td className="ui-data-table-actions">
                      {rowActions.length > 0 ? (
                        <RowActionMenu row={row} label={rowLabel(row)} actions={rowActions} />
                      ) : null}
                    </td>
                  ) : null}
                </tr>
                {expanded ? (
                  <tr className="ui-data-table-expanded">
                    <td colSpan={columnCount}>{expanded}</td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
