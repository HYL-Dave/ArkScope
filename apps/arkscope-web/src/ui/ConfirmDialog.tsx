import { useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";
import { useOverlayFocus } from "./useOverlayFocus";

export function ConfirmDialog({
  open,
  title,
  consequence,
  confirmLabel,
  cancelLabel = "取消",
  tone = "danger",
  busy = false,
  onConfirm,
  onCancel,
  returnFocusRef,
  fallbackFocusRef,
}: {
  open: boolean;
  title: string;
  consequence: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "primary" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const consequenceId = useId();
  useOverlayFocus({
    open,
    containerRef: panelRef,
    initialFocusRef: cancelRef,
    returnFocusRef,
    fallbackFocusRef,
    onEscape: () => {
      if (!busy) onCancel();
    },
  });
  if (!open) return null;

  return createPortal(
    <div className="ui-overlay-backdrop">
      <section
        ref={panelRef}
        className="ui-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={consequenceId}
        tabIndex={-1}
      >
        <h2 id={titleId}>{title}</h2>
        <div id={consequenceId} className="ui-confirm-consequence">{consequence}</div>
        <div className="ui-confirm-actions">
          <Button ref={cancelRef} onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
          <Button tone={tone} onClick={onConfirm} busy={busy}>{confirmLabel}</Button>
        </div>
      </section>
    </div>,
    document.body,
  );
}
