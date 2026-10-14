import React from "react";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "rectangular" | "circular";
}

export function Skeleton({
  variant = "rectangular",
  className = "",
  ...props
}: SkeletonProps) {
  const variantStyles = {
    text: "h-4 rounded",
    rectangular: "rounded-xl",
    circular: "rounded-full",
  }[variant];

  return (
    <div
      className={`animate-pulse bg-slate-200/80 ${variantStyles} ${className}`}
      {...props}
    />
  );
}
