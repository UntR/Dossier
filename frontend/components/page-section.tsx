import type { ReactNode } from "react";

export function PageSection({
  title,
  description,
  actions,
  children
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
          {description ? <p className="max-w-3xl text-sm text-[color:var(--dossier-muted)]">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
