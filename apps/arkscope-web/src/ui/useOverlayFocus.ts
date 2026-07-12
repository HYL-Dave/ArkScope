import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function focusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

const activeOverlays: symbol[] = [];

export function useOverlayFocus({
  open,
  containerRef,
  initialFocusRef,
  returnFocusRef,
  fallbackFocusRef,
  onEscape,
}: {
  open: boolean;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
  onEscape: () => void;
}) {
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    if (!open || !containerRef.current) return;
    const container = containerRef.current;
    const overlay = Symbol("overlay");
    const previous = returnFocusRef?.current
      ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const items = focusables(container);
    const requestedInitial = initialFocusRef?.current;
    const initial = requestedInitial && items.includes(requestedInitial)
      ? requestedInitial
      : items[0] ?? container;
    activeOverlays.push(overlay);
    initial.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (activeOverlays[activeOverlays.length - 1] !== overlay) return;
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onEscapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables(container);
      if (items.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const overlayIndex = activeOverlays.lastIndexOf(overlay);
      const wasTopmost = overlayIndex === activeOverlays.length - 1;
      if (overlayIndex >= 0) activeOverlays.splice(overlayIndex, 1);
      if (!wasTopmost) return;
      if (previous?.isConnected) previous.focus();
      else fallbackFocusRef?.current?.focus();
    };
  }, [containerRef, fallbackFocusRef, initialFocusRef, open, returnFocusRef]);
}
