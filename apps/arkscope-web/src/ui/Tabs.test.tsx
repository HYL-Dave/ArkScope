/** @vitest-environment jsdom */
import React, { createRef, useState, type RefObject } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Tabs, type TabItem } from "./Tabs";

type View = "first" | "second" | "third";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mount(node: React.ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root!.render(node));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

function Harness({
  onRequest,
  tabRefs,
}: {
  onRequest?: (value: View) => boolean | void;
  tabRefs?: readonly RefObject<HTMLButtonElement>[];
}) {
  const [value, setValue] = useState<View>("first");
  const items: readonly TabItem<View>[] = [
    { value: "first", label: "First", panel: <p>First panel</p>, tabRef: tabRefs?.[0] },
    { value: "second", label: "Second", panel: <p>Second panel</p>, tabRef: tabRefs?.[1] },
    { value: "third", label: "Third", panel: <p>Third panel</p>, tabRef: tabRefs?.[2] },
  ];

  return (
    <Tabs
      ariaLabel="Workspace views"
      value={value}
      items={items}
      onValueChange={(next) => {
        if (onRequest?.(next) === false) return false;
        setValue(next);
        return true;
      }}
    />
  );
}

function tabs() {
  return Array.from(host!.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
}

async function press(target: HTMLElement, key: string) {
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
}

describe("Tabs", () => {
  it("renders_accessible_linkage_and_only_the_selected_panel", async () => {
    await mount(<Harness />);

    expect(host!.querySelectorAll('[role="tablist"]')).toHaveLength(1);
    expect(host!.querySelector('[role="tablist"]')?.getAttribute("aria-label")).toBe("Workspace views");
    expect(tabs()).toHaveLength(3);
    expect(host!.querySelectorAll('[role="tabpanel"]')).toHaveLength(1);

    const selected = tabs()[0];
    const panel = host!.querySelector<HTMLElement>('[role="tabpanel"]')!;
    expect(selected.getAttribute("aria-selected")).toBe("true");
    expect(selected.tabIndex).toBe(0);
    expect(tabs().filter((tab) => tab.tabIndex === 0)).toHaveLength(1);
    expect(selected.getAttribute("aria-controls")).toBe(panel.id);
    expect(panel.getAttribute("aria-labelledby")).toBe(selected.id);
    expect(panel.textContent).toContain("First panel");
    expect(host!.textContent).not.toContain("Second panel");
    expect(host!.textContent).not.toContain("Third panel");
  });

  it("click_activates_and_roves_tabindex", async () => {
    await mount(<Harness />);

    await act(async () => tabs()[1].click());

    expect(tabs()[0].getAttribute("aria-selected")).toBe("false");
    expect(tabs()[0].tabIndex).toBe(-1);
    expect(tabs()[1].getAttribute("aria-selected")).toBe("true");
    expect(tabs()[1].tabIndex).toBe(0);
    expect(host!.querySelector('[role="tabpanel"]')?.textContent).toContain("Second panel");
  });

  it("arrow_right_activates_next_and_wraps", async () => {
    await mount(<Harness />);
    tabs()[0].focus();

    await press(tabs()[0], "ArrowRight");
    expect(tabs()[1].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[1]);

    await press(tabs()[1], "End");
    await press(tabs()[2], "ArrowRight");
    expect(tabs()[0].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[0]);
  });

  it("arrow_left_activates_previous_and_wraps", async () => {
    await mount(<Harness />);
    tabs()[0].focus();

    await press(tabs()[0], "ArrowLeft");
    expect(tabs()[2].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[2]);

    await press(tabs()[2], "ArrowLeft");
    expect(tabs()[1].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[1]);
  });

  it("home_and_end_activate_boundaries", async () => {
    await mount(<Harness />);
    await act(async () => tabs()[1].click());

    await press(tabs()[1], "End");
    expect(tabs()[2].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[2]);

    await press(tabs()[2], "Home");
    expect(tabs()[0].getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabs()[0]);
  });

  it("vetoed_change_preserves_selected_tab_and_focus", async () => {
    const onRequest = vi.fn(() => false);
    const tabRefs = [
      createRef<HTMLButtonElement>(),
      createRef<HTMLButtonElement>(),
      createRef<HTMLButtonElement>(),
    ] as const;
    await mount(<Harness onRequest={onRequest} tabRefs={tabRefs} />);
    tabRefs[0].current!.focus();

    await act(async () => tabRefs[1].current!.click());

    expect(tabRefs.every((ref) => ref.current instanceof HTMLButtonElement)).toBe(true);
    expect(onRequest).toHaveBeenCalledWith("second");
    expect(tabs()[0].getAttribute("aria-selected")).toBe("true");
    expect(tabs()[1].getAttribute("aria-selected")).toBe("false");
    expect(host!.querySelector('[role="tabpanel"]')?.textContent).toContain("First panel");
    expect(document.activeElement).toBe(tabRefs[0].current);
  });
});
