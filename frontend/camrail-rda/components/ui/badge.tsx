import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "success" | "warning" | "danger" | "neutral" | "brand";
  size?: "sm" | "md";
  icon?: React.ReactNode;
}

export function Badge({
  children,
  variant = "neutral",
  size = "md",
  icon,
  className = "",
  ...props
}: BadgeProps) {
  const baseStyles =
    "inline-flex items-center font-medium rounded-full border select-none transition-colors";

  const sizeStyles = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-2.5 py-1 text-xs gap-1.5",
  }[size];

  const variantStyles = {
    success:
      "bg-emerald-50 text-emerald-800 border-emerald-200/80 hover:bg-emerald-100/50",
    warning:
      "bg-amber-50 text-amber-800 border-amber-200/80 hover:bg-amber-100/50",
    danger:
      "bg-red-50 text-red-800 border-red-200/80 hover:bg-red-100/50",
    neutral:
      "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200/60",
    brand:
      "bg-red-50 text-[var(--color-camrail-red,#E00010)] border-red-200 hover:bg-red-100/60",
  }[variant];

  return (
    <span
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
