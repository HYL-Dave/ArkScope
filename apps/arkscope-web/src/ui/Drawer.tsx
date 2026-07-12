import { useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { IconButton } from "./Button";
import { useOverlayFocus } from "./useOverlayFocus";
import { useShellOverlay } from "./useShellOverlay";

export function Drawer({
  open,
  title,
  onClose,
  returnFocusRef,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const shellOverlay = useShellOverlay();
  useOverlayFocus({
    open,
    containerRef: panelRef,
    initialFocusRef: closeRef,
    returnFocusRef,
    onEscape: onClose,
  });
  if (!open) return null;

  return createPortal(
    <div
      className="ui-overlay-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        ref={panelRef}
        className="ui-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-shell-overlay={String(shellOverlay)}
        tabIndex={-1}
      >
        <header className="ui-overlay-head">
          <h2 id={titleId}>{title}</h2>
          <IconButton
            ref={closeRef}
            label="關閉"
            tone="ghost"
            icon={<X size={18} />}
            onClick={onClose}
          />
        </header>
        <div className="ui-drawer-body">{children}</div>
        {footer ? <footer className="ui-drawer-footer">{footer}</footer> : null}
      </aside>
    </div>,
    document.body,
  );
}
