"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, Entity, EventItem, Person } from "@/lib/api";

type SearchResult = {
  people: Person[];
  entities: Entity[];
  notes: Array<{ id: number; content: string }>;
  events: EventItem[];
};

export function SearchPageClient() {
  const params = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(q: string) {
    if (!q.trim()) {
      setResult(null);
      return;
    }
    setResult(await apiGet<SearchResult>(`/api/search?q=${encodeURIComponent(q.trim())}`));
  }

  useEffect(() => {
    run(params.get("q") ?? "").catch((err: Error) => setError(err.message));
  }, [params]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(`/search?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <PageSection title="搜索">
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索人物、实体、笔记、事件" />
        <ActionButton icon={<Search size={16} />}>搜索</ActionButton>
      </form>
      <StatusMessage error={error} />
      {result ? (
        <div className="grid gap-4">
          <ResultBlock title="人物">
            {result.people.map((person) => <Link key={person.id} href={`/people/${person.id}`} className="block border-b border-slate-100 p-3 text-sm last:border-0"><strong>{person.name}</strong><span className="ml-2 text-slate-500">{person.bio}</span></Link>)}
          </ResultBlock>
          <ResultBlock title="实体">
            {result.entities.map((entity) => <Link key={entity.id} href={`/entities/${entity.id}`} className="block border-b border-slate-100 p-3 text-sm last:border-0"><strong>{entity.name}</strong><span className="ml-2 text-slate-500">{entity.type}</span></Link>)}
          </ResultBlock>
          <ResultBlock title="事件">
            {result.events.map((event) => <div key={event.id} className="border-b border-slate-100 p-3 text-sm last:border-0"><strong>{event.title}</strong><span className="ml-2 text-slate-500">{event.occurred_at}</span></div>)}
          </ResultBlock>
          <ResultBlock title="笔记">
            {result.notes.map((note) => <p key={note.id} className="border-b border-slate-100 p-3 text-sm last:border-0">{note.content}</p>)}
          </ResultBlock>
        </div>
      ) : <p className="text-sm text-slate-500">输入关键词开始搜索</p>}
    </PageSection>
  );
}

function ResultBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-slate-200 bg-white">
      <h2 className="bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">{title}</h2>
      {children}
    </section>
  );
}
