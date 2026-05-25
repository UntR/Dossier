"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  variant?: "primary" | "secondary" | "danger";
};

export function ActionButton({ icon, variant = "primary", className = "", children, ...props }: ActionButtonProps) {
  const base =
    "inline-flex min-h-9 items-center justify-center gap-2 rounded-[8px] border px-3 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60";
  const variants = {
    primary: "border-[color:var(--dossier-green)] bg-[color:var(--dossier-green)] text-[color:var(--dossier-panel)] hover:bg-[#2d4d3a]",
    secondary: "border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] text-[color:var(--dossier-green)] hover:bg-[color:var(--dossier-green-soft)]",
    danger: "border-[#dfb8aa] bg-[color:var(--dossier-panel)] text-[color:var(--dossier-rust)] hover:bg-[#f6e5df]"
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {icon}
      <span>{children}</span>
    </button>
  );
}
