"use client";

import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export function GlobalSearch() {
  const router = useRouter();
  const params = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(`/search?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <form onSubmit={submit} className="ml-auto flex min-w-56 items-center gap-2 rounded border border-slate-200 bg-white px-2 py-1">
      <Search size={16} aria-hidden="true" className="text-slate-500" />
      <input
        aria-label="全局搜索"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="搜索人物、实体、事件"
        className="min-h-7 w-full bg-transparent text-sm outline-none"
      />
    </form>
  );
}
