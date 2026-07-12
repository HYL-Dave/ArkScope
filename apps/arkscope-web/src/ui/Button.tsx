import React, { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonTone = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "compact" | "default";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: ButtonTone;
  size?: ButtonSize;
  icon?: ReactNode;
  busy?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    tone = "secondary",
    size = "default",
    icon,
    busy = false,
    className = "",
    type = "button",
    disabled,
    children,
    ...rest
  },
  ref,
) {
  return (
    <button
      {...rest}
      ref={ref}
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`ui-button ui-button-${tone} ui-button-${size} ${className}`.trim()}
    >
      {icon ? <span className="ui-button-icon" aria-hidden="true">{icon}</span> : null}
      {children}
    </button>
  );
});

export interface IconButtonProps
  extends Omit<ButtonProps, "children" | "icon" | "aria-label"> {
  label: string;
  icon: ReactNode;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, title = label, className = "", ...rest },
  ref,
) {
  return (
    <Button
      {...rest}
      ref={ref}
      aria-label={label}
      title={title}
      className={`ui-icon-button ${className}`.trim()}
      icon={icon}
    />
  );
});
