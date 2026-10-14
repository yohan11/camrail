import React from "react";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 md:p-12 rounded-[var(--radius-card,14px)] border border-dashed border-slate-200 bg-slate-50/60 max-w-lg mx-auto ${className}`}
    >
      {icon && (
        <div className="h-12 w-12 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-500 mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-900 tracking-tight mb-1.5">
        {title}
      </h3>
      <p className="text-sm text-slate-600 leading-relaxed max-w-sm mb-5">
        {description}
      </p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
