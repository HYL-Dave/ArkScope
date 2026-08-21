import type { ReactNode, RefObject } from "react";

import { Drawer } from "../ui/Drawer";

export function LifecycleCaseDrawer({
  open,
  title,
  onClose,
  returnFocusRef,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  return (
    <Drawer
      open={open}
      title={title}
      onClose={onClose}
      returnFocusRef={returnFocusRef}
    >
      <div className="lifecycle-drawer-content">{children}</div>
    </Drawer>
  );
}

export function LifecycleCaseSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="lifecycle-detail-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}
