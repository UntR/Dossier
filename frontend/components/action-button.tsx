"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  variant?: "primary" | "secondary" | "danger";
};

export function ActionButton({ icon, variant = "primary", className = "", children, ...props }: ActionButtonProps) {
  const base =
    "inline-flex min-h-9 items-center justify-center gap-2 rounded border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60";
  const variants = {
    primary: "border-slate-900 bg-slate-900 text-white hover:bg-slate-700",
    secondary: "border-slate-200 bg-white text-slate-800 hover:bg-slate-100",
    danger: "border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {icon}
      <span>{children}</span>
    </button>
  );
}
