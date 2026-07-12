/** @vitest-environment jsdom */
import { act, type ComponentProps, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "./DataTable";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

type Row = { id: number; symbol: string; closed: boolean };

const columns: DataTableColumn<Row>[] = [
  { id: "symbol", header: "Symbol", render: (row) => row.symbol },
  {
    id: "state",
    header: "State",
    render: (row) => row.closed ? "Closed" : "Open",
    align: "right",
  },
];

const rows: Row[] = [{ id: 1, symbol: "NVDA", closed: false }];

async function mount(node: ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(node);
  });
}

function table(over: Partial<ComponentProps<typeof DataTable<Row>>> = {}) {
  return (
    <DataTable
      ariaLabel="Positions"
      rows={rows}
      columns={columns}
      rowKey={(row) => row.id}
      rowLabel={(row) => row.symbol}
      emptyText="尚無持倉"
      {...over}
    />
  );
}

function rect(top: number, height: number): DOMRect {
  return {
    x: 0,
    y: top,
    top,
    left: 0,
    width: 132,
    height,
    right: 132,
    bottom: top + height,
    toJSON: () => ({}),
  };
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.restoreAllMocks();
});

describe("DataTable", () => {
  it("renders_typed_columns_and_rows", async () => {
    await mount(table());

    expect(host!.querySelector("table")?.getAttribute("aria-label")).toBe("Positions");
    expect(Array.from(host!.querySelectorAll("th")).map((cell) => cell.textContent)).toEqual([
      "Symbol",
      "State",
    ]);
    expect(Array.from(host!.querySelectorAll("tbody td")).map((cell) => cell.textContent)).toEqual([
      "NVDA",
      "Open",
    ]);
    expect(host!.querySelector('td[data-align="right"]')?.textContent).toBe("Open");
  });

  it("renders_one_full_width_empty_row", async () => {
    await mount(table({ rows: [] }));

    const bodyRows = host!.querySelectorAll("tbody tr");
    const empty = bodyRows[0]?.querySelector("td");
    expect(bodyRows).toHaveLength(1);
    expect(empty?.textContent).toBe("尚無持倉");
    expect(empty?.colSpan).toBe(columns.length);
  });

  it("opens_a_labelled_row_action_menu_flips_from_viewport_edge_and_runs_one_action", async () => {
    const onEdit = vi.fn();
    const onClose = vi.fn();
    Object.defineProperty(window, "innerHeight", { value: 600, configurable: true });
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      if (this.classList.contains("ui-row-action-menu")) return rect(580, 120);
      if (this.matches('button[aria-haspopup="menu"]')) return rect(500, 28);
      return rect(0, 0);
    });
    await mount(table({
      actions: (row) => [
        { id: "edit", label: "編輯", onSelect: () => onEdit(row) },
        { id: "close", label: "關閉", tone: "danger", onSelect: () => onClose(row) },
      ],
    }));

    const trigger = host!.querySelector<HTMLButtonElement>('button[aria-label="NVDA 操作"]')!;
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    await act(async () => {
      trigger.click();
    });

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const menu = document.querySelector<HTMLElement>('[role="menu"]')!;
    expect(menu.parentElement).toBe(document.body);
    expect(menu.getAttribute("data-placement")).toBe("up");
    expect(menu.style.position).toBe("fixed");
    expect(menu.style.top).toBe("376px");
    const menuItems = document.querySelectorAll<HTMLButtonElement>('[role="menuitem"]');
    expect(Array.from(menuItems).map((item) => item.textContent)).toEqual(["編輯", "關閉"]);
    await act(async () => {
      menuItems[1].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(document.querySelector('[role="menu"]')).toBe(menu);
    await act(async () => {
      menuItems[1].click();
    });
    expect(onClose).toHaveBeenCalledWith(rows[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onEdit).not.toHaveBeenCalled();
    expect(document.querySelector('[role="menu"]')).toBeNull();

    await act(async () => {
      trigger.click();
    });
    await act(async () => {
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("escape_closes_the_row_menu_and_restores_its_trigger", async () => {
    await mount(table({
      actions: () => [{ id: "edit", label: "編輯", onSelect: vi.fn() }],
    }));
    const trigger = host!.querySelector<HTMLButtonElement>('button[aria-label="NVDA 操作"]')!;
    await act(async () => {
      trigger.click();
    });
    document.querySelector<HTMLButtonElement>('[role="menuitem"]')!.focus();

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });

    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
  });

  it("keeps_only_one_row_action_menu_open_and_focuses_the_new_menu", async () => {
    const visibilityAtFocus: string[] = [];
    const recordMenuFocus = (event: FocusEvent) => {
      const item = event.target as HTMLElement;
      if (item.getAttribute("role") === "menuitem") {
        visibilityAtFocus.push(item.closest<HTMLElement>('[role="menu"]')?.style.visibility ?? "");
      }
    };
    document.addEventListener("focusin", recordMenuFocus);
    await mount(table({
      rows: [
        { id: 1, symbol: "NVDA", closed: false },
        { id: 2, symbol: "AMD", closed: false },
      ],
      actions: () => [{ id: "edit", label: "編輯", onSelect: vi.fn() }],
    }));
    const first = host!.querySelector<HTMLButtonElement>('button[aria-label="NVDA 操作"]')!;
    const second = host!.querySelector<HTMLButtonElement>('button[aria-label="AMD 操作"]')!;

    await act(async () => first.click());
    expect(document.querySelectorAll('[role="menu"]')).toHaveLength(1);
    expect(document.activeElement?.textContent).toContain("編輯");

    await act(async () => second.click());
    expect(document.querySelectorAll('[role="menu"]')).toHaveLength(1);
    expect(first.getAttribute("aria-expanded")).toBe("false");
    expect(second.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement?.textContent).toContain("編輯");
    expect(visibilityAtFocus).toEqual(["visible", "visible"]);
    document.removeEventListener("focusin", recordMenuFocus);
  });

  it("renders_an_inline_expansion_directly_after_its_owner_row", async () => {
    await mount(table({ renderExpandedRow: (row) => <div>Edit {row.symbol}</div> }));

    const bodyRows = host!.querySelectorAll("tbody tr");
    expect(bodyRows).toHaveLength(2);
    expect(bodyRows[0].textContent).toContain("NVDA");
    expect(bodyRows[1].classList.contains("ui-data-table-expanded")).toBe(true);
    expect(bodyRows[1].textContent).toBe("Edit NVDA");
    expect(bodyRows[1].querySelector("td")?.colSpan).toBe(columns.length);
  });
});
