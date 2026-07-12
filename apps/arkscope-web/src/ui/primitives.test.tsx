/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Search } from "lucide-react";
import { Button, IconButton } from "./Button";
import { PageHeader } from "./PageHeader";
import { COMMON_UI_STATES, InlineAlert, StatusBadge } from "./Status";

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

describe("UI primitives", () => {
  it("renders one page title with compact context and commands", async () => {
    await mount(
      <PageHeader
        eyebrow="Holdings"
        title="持倉"
        context={<span>9 positions</span>}
        actions={<Button>重新整理</Button>}
      />,
    );
    expect(host!.querySelectorAll("h1")).toHaveLength(1);
    expect(host!.textContent).toContain("9 positions");
    expect(host!.querySelector(".ui-page-header-actions button")).not.toBeNull();
  });

  it("keeps command-button type and disabled state explicit", async () => {
    await mount(<Button tone="primary" disabled>儲存</Button>);
    const button = host!.querySelector("button")!;
    expect(button.type).toBe("button");
    expect(button.disabled).toBe(true);
    expect(button.className).toContain("ui-button-primary");
  });

  it("requires an accessible label and tooltip for an icon button", async () => {
    await mount(<IconButton label="搜尋" icon={<Search />} />);
    const button = host!.querySelector("button")!;
    expect(button.getAttribute("aria-label")).toBe("搜尋");
    expect(button.title).toBe("搜尋");
    expect(button.querySelector(".ui-button-icon")?.getAttribute("aria-hidden")).toBe("true");
  });

  it.each(COMMON_UI_STATES)("renders %s with a visible domain label", async (state) => {
    await mount(<StatusBadge state={state} label={`domain:${state}`} />);
    const badge = host!.querySelector("[data-state]")!;
    expect(badge.getAttribute("data-state")).toBe(state);
    expect(badge.textContent).toContain(`domain:${state}`);
    expect(badge.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("uses alert semantics for failed and blocked messages", async () => {
    await mount(<InlineAlert state="failed" title="同步失敗">重新整理後再試</InlineAlert>);
    expect(host!.querySelector('[role="alert"]')).not.toBeNull();
    expect(host!.textContent).toContain("重新整理後再試");
  });

  it("uses status semantics for nonterminal information", async () => {
    await mount(<InlineAlert state="partial" title="尚未套用">先檢查差異</InlineAlert>);
    expect(host!.querySelector('[role="status"]')).not.toBeNull();
  });
});
