/** @vitest-environment jsdom */
import { useRef, useState, type ReactNode } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
import { Drawer } from "./Drawer";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  })));
}

function stubMutableMatchMedia(initialMatches: boolean) {
  let matches = initialMatches;
  const listeners = new Set<() => void>();
  const media = {
    get matches() { return matches; },
    media: "(max-width: var(--shell-overlay-breakpoint))",
    onchange: null,
    addEventListener: vi.fn((_type: string, listener: () => void) => listeners.add(listener)),
    removeEventListener: vi.fn((_type: string, listener: () => void) => listeners.delete(listener)),
    addListener: vi.fn((listener: () => void) => listeners.add(listener)),
    removeListener: vi.fn((listener: () => void) => listeners.delete(listener)),
    dispatchEvent: vi.fn(() => true),
  };
  vi.stubGlobal("matchMedia", vi.fn(() => media));
  return {
    async setMatches(nextMatches: boolean) {
      matches = nextMatches;
      await act(async () => {
        listeners.forEach((listener) => listener());
        await Promise.resolve();
      });
    },
  };
}

async function render(node: ReactNode) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(node);
    await Promise.resolve();
  });
}

async function rerender(node: ReactNode) {
  await act(async () => {
    root!.render(node);
    await Promise.resolve();
  });
}

function pressKey(key: string, shiftKey = false) {
  document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key, shiftKey }));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

describe("overlay focus contracts", () => {
  it("closed_drawer_renders_nothing_and_reserves_no_width", async () => {
    stubMatchMedia(false);

    await render(
      <Drawer open={false} title="篩選條件" onClose={vi.fn()}>
        <button>套用</button>
      </Drawer>,
    );

    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector(".ui-overlay-backdrop")).toBeNull();
  });

  it("open_drawer_close_button_closes_and_restores_its_trigger", async () => {
    stubMatchMedia(false);
    const onClose = vi.fn();

    function Fixture() {
      const triggerRef = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      return (
        <>
          <button ref={triggerRef} onClick={() => setOpen(true)}>開啟篩選</button>
          <Drawer
            open={open}
            title="篩選條件"
            returnFocusRef={triggerRef}
            onClose={() => {
              onClose();
              setOpen(false);
            }}
          >
            <button>套用</button>
          </Drawer>
        </>
      );
    }

    await render(<Fixture />);
    const trigger = document.querySelector<HTMLButtonElement>("button")!;
    trigger.focus();
    await act(async () => trigger.click());
    const close = document.querySelector<HTMLButtonElement>('[aria-label="關閉"]')!;
    close.focus();
    await act(async () => close.click());

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(trigger);
  });

  it("drawer_escape_closes_and_restores_the_trigger", async () => {
    stubMatchMedia(false);
    const onClose = vi.fn();

    function Fixture() {
      const triggerRef = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      return (
        <>
          <button ref={triggerRef} onClick={() => setOpen(true)}>開啟篩選</button>
          <Drawer
            open={open}
            title="篩選條件"
            returnFocusRef={triggerRef}
            onClose={() => {
              onClose();
              setOpen(false);
            }}
          >
            <button>套用</button>
          </Drawer>
        </>
      );
    }

    await render(<Fixture />);
    const trigger = document.querySelector<HTMLButtonElement>("button")!;
    trigger.focus();
    await act(async () => trigger.click());
    const handledEscape = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Escape" });
    handledEscape.preventDefault();
    await act(async () => document.dispatchEvent(handledEscape));
    expect(onClose).not.toHaveBeenCalled();
    await act(async () => pressKey("Escape"));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(trigger);
  });

  it("drawer_tabs_between_its_own_focusable_controls", async () => {
    stubMatchMedia(false);

    await render(
      <Drawer
        open
        title="篩選條件"
        onClose={vi.fn()}
        footer={<button>套用</button>}
      >
        <button>重設</button>
      </Drawer>,
    );

    const close = document.querySelector<HTMLButtonElement>('[aria-label="關閉"]')!;
    const apply = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "套用")!;
    expect(document.activeElement).toBe(close);
    await act(async () => pressKey("Tab", true));
    expect(document.activeElement).toBe(apply);
    await act(async () => pressKey("Tab"));
    expect(document.activeElement).toBe(close);
  });

  it("drawer_marks_961px_as_wide", async () => {
    stubMatchMedia(false);

    await render(<Drawer open title="篩選條件" onClose={vi.fn()}><button>套用</button></Drawer>);

    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("data-shell-overlay")).toBe("false");
  });

  it("drawer_marks_959px_as_shell_overlay", async () => {
    stubMatchMedia(true);

    await render(<Drawer open title="篩選條件" onClose={vi.fn()}><button>套用</button></Drawer>);

    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("data-shell-overlay")).toBe("true");
  });

  it("wide_pinned_drawer_is_inline_without_modal_focus_ownership", async () => {
    stubMatchMedia(false);
    const onClose = vi.fn();

    await render(
      <>
        <button>外部操作</button>
        <Drawer
          open
          pinnable
          pinned
          title="研究證據"
          onClose={onClose}
          onPinnedChange={vi.fn()}
        >
          <button>查看證據</button>
        </Drawer>
      </>,
    );

    const inline = document.querySelector<HTMLElement>('[role="complementary"]')!;
    const outside = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "外部操作")!;
    expect(inline).not.toBeNull();
    expect(host!.contains(inline)).toBe(true);
    expect(inline.getAttribute("aria-modal")).toBeNull();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector(".ui-overlay-backdrop")).toBeNull();
    expect(document.querySelector('[aria-label="取消釘選"]')).not.toBeNull();

    outside.focus();
    await act(async () => pressKey("Escape"));
    expect(onClose).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(outside);
  });

  it("pinned_drawer_uses_modal_contract_at_the_shell_overlay_token", async () => {
    stubMatchMedia(true);

    await render(
      <Drawer
        open
        pinnable
        pinned
        title="研究證據"
        onClose={vi.fn()}
        onPinnedChange={vi.fn()}
      >
        <button>查看證據</button>
      </Drawer>,
    );

    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog).not.toBeNull();
    expect(host!.contains(dialog)).toBe(false);
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("data-shell-overlay")).toBe("true");
    expect(document.querySelector(".ui-overlay-backdrop")).not.toBeNull();
    expect(document.querySelector('[aria-label="釘選"]')).toBeNull();
    expect(document.querySelector('[aria-label="取消釘選"]')).toBeNull();
    expect(document.activeElement).toBe(document.querySelector('[aria-label="關閉"]'));
  });

  it("pinning_keeps_focus_in_the_drawer_then_inline_close_restores_the_trigger", async () => {
    const viewport = stubMutableMatchMedia(false);
    const onClose = vi.fn();
    const onPinnedChange = vi.fn();
    const onConfirmCancel = vi.fn();

    function Fixture() {
      const triggerRef = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      const [pinned, setPinned] = useState(false);
      const [confirmOpen, setConfirmOpen] = useState(false);
      return (
        <>
          <button ref={triggerRef} onClick={() => setOpen(true)}>查看研究證據</button>
          <Drawer
            open={open}
            pinnable
            pinned={pinned}
            title="研究證據"
            returnFocusRef={triggerRef}
            onPinnedChange={(nextPinned) => {
              onPinnedChange(nextPinned);
              setPinned(nextPinned);
            }}
            onClose={() => {
              onClose();
              setOpen(false);
            }}
          >
            <button>查看證據</button>
            <button onClick={() => setConfirmOpen(true)}>開啟確認</button>
          </Drawer>
          <ConfirmDialog
            open={confirmOpen}
            title="移除證據"
            consequence="移除後無法復原。"
            confirmLabel="移除"
            onConfirm={vi.fn()}
            onCancel={() => {
              onConfirmCancel();
              setConfirmOpen(false);
            }}
          />
        </>
      );
    }

    await render(<Fixture />);
    const trigger = document.querySelector<HTMLButtonElement>("button")!;
    trigger.focus();
    await act(async () => trigger.click());

    const pin = document.querySelector<HTMLButtonElement>('[aria-label="釘選"]')!;
    pin.focus();
    await act(async () => pin.click());
    expect(onPinnedChange).toHaveBeenCalledWith(true);
    expect(onClose).not.toHaveBeenCalled();
    expect(document.querySelector('[role="complementary"]')).not.toBeNull();
    expect(document.activeElement).not.toBe(trigger);
    expect(document.activeElement).toBe(document.querySelector('[aria-label="取消釘選"]'));

    const close = document.querySelector<HTMLButtonElement>('[aria-label="關閉"]')!;
    await act(async () => close.click());
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(trigger);

    await viewport.setMatches(true);
    await act(async () => trigger.click());
    const confirmTrigger = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "開啟確認")!;
    confirmTrigger.focus();
    await act(async () => confirmTrigger.click());
    const confirmDialog = document.querySelector<HTMLElement>(".ui-confirm-dialog")!;
    expect(confirmDialog.contains(document.activeElement)).toBe(true);

    await viewport.setMatches(false);
    expect(document.querySelector('[role="complementary"]')).not.toBeNull();
    expect(confirmDialog.contains(document.activeElement)).toBe(true);

    await viewport.setMatches(true);
    const modalDrawer = document.querySelector<HTMLElement>(".ui-drawer")!;
    expect(modalDrawer.getAttribute("aria-modal")).toBe("true");
    expect(confirmDialog.contains(document.activeElement)).toBe(true);

    await act(async () => pressKey("Escape"));
    expect(onConfirmCancel).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector(".ui-confirm-dialog")).toBeNull();
    expect(modalDrawer.contains(document.activeElement)).toBe(true);

    await act(async () => pressKey("Escape"));
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(document.activeElement).toBe(trigger);
  });

  it("confirm_dialog_focuses_cancel_for_a_destructive_action", async () => {
    await render(
      <ConfirmDialog
        open
        title="刪除觀察清單"
        consequence="刪除後無法復原。"
        confirmLabel="刪除"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(document.querySelector('[role="dialog"]')?.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement?.textContent).toContain("取消");
  });

  it("confirm_dialog_cancel_does_not_confirm_and_restores_focus", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    function Fixture() {
      const triggerRef = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      return (
        <>
          <button ref={triggerRef} onClick={() => setOpen(true)}>刪除觀察清單</button>
          <ConfirmDialog
            open={open}
            title="刪除觀察清單"
            consequence="刪除後無法復原。"
            confirmLabel="刪除"
            returnFocusRef={triggerRef}
            onConfirm={onConfirm}
            onCancel={() => {
              onCancel();
              setOpen(false);
            }}
          />
        </>
      );
    }

    await render(<Fixture />);
    const trigger = document.querySelector<HTMLButtonElement>("button")!;
    trigger.focus();
    await act(async () => trigger.click());
    const cancel = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "取消")!;
    await act(async () => cancel.click());

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(trigger);
  });

  it("confirm_dialog_confirms_once_then_uses_fallback_if_the_trigger_disappears", async () => {
    const onConfirm = vi.fn();

    function Fixture() {
      const triggerRef = useRef<HTMLButtonElement>(null);
      const fallbackFocusRef = useRef<HTMLButtonElement>(null);
      const [open, setOpen] = useState(false);
      const [showTrigger, setShowTrigger] = useState(true);
      return (
        <>
          {showTrigger ? <button ref={triggerRef} onClick={() => setOpen(true)}>刪除觀察清單</button> : null}
          <button ref={fallbackFocusRef}>返回觀察清單</button>
          <ConfirmDialog
            open={open}
            title="刪除觀察清單"
            consequence="刪除後無法復原。"
            confirmLabel="刪除"
            returnFocusRef={triggerRef}
            fallbackFocusRef={fallbackFocusRef}
            onConfirm={() => {
              onConfirm();
              setShowTrigger(false);
              setOpen(false);
            }}
            onCancel={vi.fn()}
          />
        </>
      );
    }

    await render(<Fixture />);
    const trigger = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "刪除觀察清單")!;
    trigger.focus();
    await act(async () => trigger.click());
    const confirm = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "刪除")!;
    await act(async () => confirm.click());

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(document.activeElement?.textContent).toContain("返回觀察清單");
  });

  it("confirm_dialog_escape_cancels_only_when_not_busy", async () => {
    stubMatchMedia(false);
    const onDrawerClose = vi.fn();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const overlays = (busy: boolean) => (
      <>
        <Drawer open title="篩選條件" onClose={onDrawerClose}>
          <button>套用</button>
        </Drawer>
        <ConfirmDialog
          open
          busy={busy}
          title="刪除觀察清單"
          consequence="刪除後無法復原。"
          confirmLabel="刪除"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      </>
    );

    await render(overlays(true));
    const drawer = document.querySelector<HTMLElement>(".ui-drawer")!;
    const confirmDialog = document.querySelector<HTMLElement>(".ui-confirm-dialog")!;
    expect.soft(document.activeElement).toBe(confirmDialog);
    await act(async () => pressKey("Escape"));
    expect.soft(onDrawerClose).not.toHaveBeenCalled();
    expect.soft(onCancel).not.toHaveBeenCalled();
    expect.soft(onConfirm).not.toHaveBeenCalled();
    expect.soft(drawer.isConnected).toBe(true);

    onDrawerClose.mockClear();
    onCancel.mockClear();
    await rerender(overlays(false));
    await act(async () => pressKey("Escape"));
    expect.soft(onDrawerClose).not.toHaveBeenCalled();
    expect.soft(onCancel).toHaveBeenCalledTimes(1);
    expect.soft(onConfirm).not.toHaveBeenCalled();
    expect.soft(drawer.isConnected).toBe(true);

    onDrawerClose.mockClear();
    onCancel.mockClear();
    await rerender(overlays(true));
    await act(async () => pressKey("Escape"));
    expect.soft(onDrawerClose).not.toHaveBeenCalled();
    expect.soft(onCancel).not.toHaveBeenCalled();
    expect.soft(onConfirm).not.toHaveBeenCalled();
  });
});
