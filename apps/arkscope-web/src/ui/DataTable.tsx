import {
  Fragment,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type Key,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
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
  open,
  onOpenChange,
}: {
  row: Row;
  label: string;
  actions: DataTableAction<Row>[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [placement, setPlacement] = useState<"up" | "down">("down");
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const positionMenu = useCallback(() => {
    if (!menuRef.current || !triggerRef.current) return;
    const menu = menuRef.current.getBoundingClientRect();
    const trigger = triggerRef.current.getBoundingClientRect();
    const nextPlacement = trigger.bottom + 4 + menu.height > window.innerHeight
      && trigger.top >= menu.height
      ? "up"
      : "down";
    const unclampedTop = nextPlacement === "up"
      ? trigger.top - menu.height - 4
      : trigger.bottom + 4;
    const maxLeft = Math.max(0, window.innerWidth - menu.width);
    setPlacement(nextPlacement);
    setMenuPosition({
      top: Math.max(0, Math.min(unclampedTop, window.innerHeight - menu.height)),
      left: Math.max(0, Math.min(trigger.right - menu.width, maxLeft)),
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    positionMenu();
    menuRef.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]:not(:disabled)')
      ?.focus();
  }, [open, positionMenu]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, true);
    return () => {
      window.removeEventListener("resize", positionMenu);
      window.removeEventListener("scroll", positionMenu, true);
    };
  }, [open, positionMenu]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      onOpenChange(false);
      setMenuPosition(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.key !== "Escape") return;
      event.preventDefault();
      onOpenChange(false);
      setMenuPosition(null);
      triggerRef.current?.focus();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [onOpenChange, open]);

  const menu = open ? createPortal(
    <div
      ref={menuRef}
      className="ui-row-action-menu"
      role="menu"
      data-placement={placement}
      style={{
        position: "fixed",
        top: menuPosition?.top ?? 0,
        left: menuPosition?.left ?? 0,
        visibility: menuPosition ? "visible" : "hidden",
      }}
    >
      {actions.map((action) => (
        <button
          key={action.id}
          type="button"
          role="menuitem"
          className={action.tone === "danger" ? "danger" : ""}
          disabled={action.disabled}
          onClick={() => {
            onOpenChange(false);
            setMenuPosition(null);
            if (triggerRef.current) action.onSelect(row, triggerRef.current);
          }}
        >
          {action.label}
        </button>
      ))}
    </div>,
    document.body,
  ) : null;

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
        onClick={() => {
          setMenuPosition(null);
          onOpenChange(!open);
        }}
      />
      {menu}
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
  const [activeActionKey, setActiveActionKey] = useState<Key | null>(null);
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
            const key = rowKey(row);
            const expanded = renderExpandedRow?.(row);
            const rowActions = actions?.(row) ?? [];
            return (
              <Fragment key={key}>
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
                        <RowActionMenu
                          row={row}
                          label={rowLabel(row)}
                          actions={rowActions}
                          open={activeActionKey === key}
                          onOpenChange={(open) => setActiveActionKey(open ? key : null)}
                        />
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
