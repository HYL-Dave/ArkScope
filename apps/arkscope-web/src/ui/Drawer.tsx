import { useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Pin, PinOff, X } from "lucide-react";
import { useTranslation } from "react-i18next";
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
  pinnable = false,
  pinned = false,
  onPinnedChange,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
  footer?: ReactNode;
  pinnable?: boolean;
  pinned?: boolean;
  onPinnedChange?: (pinned: boolean) => void;
}) {
  const { t } = useTranslation("common");
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const pinRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const shellOverlay = useShellOverlay();
  const inline = open && pinnable && pinned && !shellOverlay;
  const modalOpen = open && !inline;

  useOverlayFocus({
    open: modalOpen,
    present: open,
    containerRef: panelRef,
    initialFocusRef: closeRef,
    inactiveFocusRef: pinRef,
    returnFocusRef,
    onEscape: onClose,
  });

  if (!open) return null;

  const close = () => {
    const returnTarget = inline ? returnFocusRef?.current : null;
    onClose();
    if (returnTarget?.isConnected) returnTarget.focus();
  };
  const panel = (
    <aside
      ref={panelRef}
      className={`ui-drawer${inline ? " ui-drawer-inline" : ""}`}
      role={inline ? "complementary" : "dialog"}
      aria-modal={inline ? undefined : "true"}
      aria-labelledby={titleId}
      data-shell-overlay={inline ? undefined : String(shellOverlay)}
      tabIndex={inline ? undefined : -1}
    >
      <header className="ui-overlay-head">
        <h2 id={titleId}>{title}</h2>
        <div className="ui-overlay-head-actions">
          {pinnable && !shellOverlay && onPinnedChange ? (
            <IconButton
              ref={pinRef}
              label={pinned
                ? t(($) => $.actions.unpin)
                : t(($) => $.actions.pin)}
              tone="ghost"
              icon={pinned ? <PinOff size={18} /> : <Pin size={18} />}
              onClick={() => onPinnedChange(!pinned)}
            />
          ) : null}
          <IconButton
            ref={closeRef}
            label={t(($) => $.actions.close)}
            tone="ghost"
            icon={<X size={18} />}
            onClick={close}
          />
        </div>
      </header>
      <div className="ui-drawer-body">{children}</div>
      {footer ? <footer className="ui-drawer-footer">{footer}</footer> : null}
    </aside>
  );

  if (inline) return panel;

  return createPortal(
    <div
      className="ui-overlay-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {panel}
    </div>,
    document.body,
  );
}
