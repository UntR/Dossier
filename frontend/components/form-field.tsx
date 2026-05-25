import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

export function Field({
  label,
  children
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="font-semibold text-[color:var(--dossier-muted)]">{label}</span>
      {children}
    </label>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]" {...props} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="min-h-24 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]" {...props} />;
}
