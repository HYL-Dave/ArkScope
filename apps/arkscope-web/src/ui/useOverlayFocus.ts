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

type OverlayEntry = {
  id: symbol;
  active: boolean;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
  inactiveFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
  previous: HTMLElement | null;
};

const overlayStack: OverlayEntry[] = [];

function topmostActiveOverlay(): OverlayEntry | null {
  for (let index = overlayStack.length - 1; index >= 0; index -= 1) {
    const entry = overlayStack[index];
    if (entry.active) return entry;
  }
  return null;
}

function focusOverlay(entry: OverlayEntry) {
  const container = entry.containerRef.current;
  if (!container?.isConnected) return;
  const items = focusables(container);
  const requestedInitial = entry.initialFocusRef?.current;
  const initial = requestedInitial && items.includes(requestedInitial)
    ? requestedInitial
    : items[0] ?? container;
  initial.focus();
}

function topmostInactiveFocusTarget(): HTMLElement | null {
  for (let index = overlayStack.length - 1; index >= 0; index -= 1) {
    const entry = overlayStack[index];
    const target = entry.active ? null : entry.inactiveFocusRef?.current;
    if (target?.isConnected) return target;
  }
  return null;
}

function restoreAfterRemoval(entry: OverlayEntry) {
  const nextOverlay = topmostActiveOverlay();
  if (nextOverlay) {
    const nextContainer = nextOverlay.containerRef.current;
    if (entry.previous?.isConnected && nextContainer?.contains(entry.previous)) {
      entry.previous.focus();
    } else {
      focusOverlay(nextOverlay);
    }
    return;
  }
  if (entry.previous?.isConnected) {
    entry.previous.focus();
    return;
  }
  const inactiveTarget = topmostInactiveFocusTarget();
  if (inactiveTarget) inactiveTarget.focus();
  else entry.fallbackFocusRef?.current?.focus();
}

export function useOverlayFocus({
  open,
  present = open,
  containerRef,
  initialFocusRef,
  inactiveFocusRef,
  returnFocusRef,
  fallbackFocusRef,
  onEscape,
}: {
  open: boolean;
  present?: boolean;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
  inactiveFocusRef?: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
  onEscape: () => void;
}) {
  const onEscapeRef = useRef(onEscape);
  const entryRef = useRef<OverlayEntry | null>(null);
  onEscapeRef.current = onEscape;
  if (entryRef.current) {
    entryRef.current.containerRef = containerRef;
    entryRef.current.initialFocusRef = initialFocusRef;
    entryRef.current.inactiveFocusRef = inactiveFocusRef;
    entryRef.current.fallbackFocusRef = fallbackFocusRef;
  }

  useEffect(() => {
    if (!present) return;
    const entry: OverlayEntry = {
      id: Symbol("overlay"),
      active: false,
      containerRef,
      initialFocusRef,
      inactiveFocusRef,
      fallbackFocusRef,
      previous: returnFocusRef?.current
        ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null),
    };
    entryRef.current = entry;
    overlayStack.push(entry);

    return () => {
      const wasTopmost = topmostActiveOverlay() === entry;
      const overlayIndex = overlayStack.findIndex((candidate) => candidate.id === entry.id);
      if (overlayIndex >= 0) overlayStack.splice(overlayIndex, 1);
      entryRef.current = null;
      if (wasTopmost) restoreAfterRemoval(entry);
    };
  }, [present]);

  useEffect(() => {
    const entry = entryRef.current;
    if (!entry) return;
    if (!open) {
      const wasTopmost = topmostActiveOverlay() === entry;
      entry.active = false;
      if (wasTopmost) {
        const nextOverlay = topmostActiveOverlay();
        if (nextOverlay) focusOverlay(nextOverlay);
        else if (entry.inactiveFocusRef?.current?.isConnected) entry.inactiveFocusRef.current.focus();
      }
      return;
    }

    entry.active = true;
    if (topmostActiveOverlay() === entry) focusOverlay(entry);

    const onKeyDown = (event: KeyboardEvent) => {
      if (topmostActiveOverlay() !== entry) return;
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onEscapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const container = entry.containerRef.current;
      if (!container) return;
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
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, present]);
}
