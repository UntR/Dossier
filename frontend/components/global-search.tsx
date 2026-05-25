"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";

import { apiGet, Entity, EventItem, Person } from "@/lib/api";

type SearchResult = {
  people: Person[];
  entities: Entity[];
  notes: Array<{ id: number; content: string }>;
  events: EventItem[];
};

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = query.trim();

  useEffect(() => {
    if (!trimmed) {
      setResult(null);
      setError(null);
      setLoading(false);
      return;
    }

    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      apiGet<SearchResult>(`/api/search?q=${encodeURIComponent(trimmed)}`)
        .then((nextResult) => {
          if (active) setResult(nextResult);
        })
        .catch((err: Error) => {
          if (active) setError(err.message);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 240);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [trimmed]);

  const resultCount = useMemo(() => {
    if (!result) return 0;
    return result.people.length + result.entities.length + result.events.length + result.notes.length;
  }, [result]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOpen(Boolean(trimmed));
  }

  return (
    <form onSubmit={submit} className="relative w-full max-w-3xl">
      <div className="flex min-h-10 items-center gap-2 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3">
        <Search size={16} aria-hidden="true" className="text-[color:var(--dossier-muted)]" />
        <input
          aria-label="全局搜索"
          value={query}
          onFocus={() => setOpen(Boolean(trimmed))}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(Boolean(event.target.value.trim()));
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder="搜索人物、事件和原文片段"
          className="min-h-9 w-full bg-transparent text-sm outline-none"
        />
        {loading ? <Loader2 size={15} aria-label="搜索中" className="animate-spin text-[color:var(--dossier-muted)]" /> : null}
      </div>

      {open && trimmed ? (
        <div className="absolute left-0 right-0 top-12 z-30 overflow-hidden rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] shadow-lg">
          <div className="border-b border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] px-3 py-2 text-xs text-[color:var(--dossier-muted)]">
            {error ? `搜索失败：${error}` : loading ? "正在搜索本地记忆" : `找到 ${resultCount} 条结果`}
          </div>
          {!error && result ? (
            <div className="grid max-h-[520px] gap-3 overflow-y-auto p-3">
              {result.people.length > 0 ? (
                <SearchGroup title="人物">
                  {result.people.map((person) => (
                    <Link key={person.id} href={`/people/${person.id}`} onClick={() => setOpen(false)} className="block rounded-[8px] px-3 py-2 text-sm hover:bg-[color:var(--dossier-green-soft)]">
                      <span className="font-semibold">{person.name}</span>
                      {person.bio ? <span className="ml-2 text-[color:var(--dossier-muted)]">{person.bio}</span> : null}
                    </Link>
                  ))}
                </SearchGroup>
              ) : null}
              {result.events.length > 0 ? (
                <SearchGroup title="事件">
                  {result.events.map((event) => (
                    <div key={event.id} className="rounded-[8px] px-3 py-2 text-sm">
                      <span className="font-semibold">{event.title}</span>
                      {event.occurred_at ? <span className="ml-2 text-[color:var(--dossier-muted)]">{event.occurred_at}</span> : null}
                    </div>
                  ))}
                </SearchGroup>
              ) : null}
              {result.notes.length > 0 ? (
                <SearchGroup title="原文片段">
                  {result.notes.map((note) => (
                    <p key={note.id} className="rounded-[8px] px-3 py-2 text-sm leading-6 text-[color:var(--dossier-muted)]">{note.content}</p>
                  ))}
                </SearchGroup>
              ) : null}
              {result.entities.length > 0 ? (
                <SearchGroup title="实体线索">
                  {result.entities.map((entity) => (
                    <Link key={entity.id} href={`/entities/${entity.id}`} onClick={() => setOpen(false)} className="block rounded-[8px] px-3 py-2 text-sm hover:bg-[color:var(--dossier-green-soft)]">
                      <span className="font-semibold">{entity.name}</span>
                      <span className="ml-2 text-[color:var(--dossier-muted)]">{entity.type}</span>
                    </Link>
                  ))}
                </SearchGroup>
              ) : null}
              {resultCount === 0 ? <p className="px-3 py-4 text-sm text-[color:var(--dossier-muted)]">没有匹配结果</p> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </form>
  );
}

function SearchGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-1 px-3 text-xs font-semibold text-[color:var(--dossier-muted)]">{title}</h2>
      <div className="grid gap-1">{children}</div>
    </section>
  );
}
