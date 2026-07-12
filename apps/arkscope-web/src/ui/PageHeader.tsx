import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  context,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="ui-page-header">
      <div className="ui-page-header-copy">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {context ? <div className="ui-page-header-context">{context}</div> : null}
      </div>
      {actions ? <div className="ui-page-header-actions">{actions}</div> : null}
    </header>
  );
}
