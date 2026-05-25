"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Plus, RefreshCw, Save, Search, Trash2 } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, joinList, Person, splitList, toNumber } from "@/lib/api";

type PeopleList = { items: Person[]; limit: number; offset: number };

export function PeoplePageClient() {
  const [items, setItems] = useState<Person[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(q = query) {
    setError(null);
    const suffix = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
    const data = await apiGet<PeopleList>(`/api/people${suffix}`);
    setItems(data.items);
  }

  useEffect(() => {
    load("").catch((err: Error) => setError(err.message));
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setError(null);
    setMessage(null);
    const form = new FormData(formElement);
    try {
      await apiJson<Person>("/api/people", "POST", {
        name: String(form.get("name") ?? ""),
        aliases: splitList(String(form.get("aliases") ?? "")),
        bio: String(form.get("bio") ?? ""),
        importance: toNumber(form.get("importance")) ?? 0
      });
      formElement.reset();
      setMessage("已创建人物");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(person: Person) {
    if (!window.confirm(`删除 ${person.name}？`)) return;
    try {
      await apiJson(`/api/people/${person.id}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <PageSection
      title="人物"
      actions={
        <ActionButton variant="secondary" icon={<RefreshCw size={16} />} title="刷新" onClick={() => load().catch((err: Error) => setError(err.message))}>
          刷新
        </ActionButton>
      }
    >
      <form onSubmit={(event) => { event.preventDefault(); load().catch((err: Error) => setError(err.message)); }} className="flex flex-wrap gap-2">
        <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按姓名、别名、简介搜索" />
        <ActionButton icon={<Search size={16} />}>搜索</ActionButton>
      </form>

      <form onSubmit={create} className="grid gap-3 rounded border border-slate-200 bg-white p-4 md:grid-cols-4">
        <Field label="姓名"><TextInput name="name" required /></Field>
        <Field label="别名"><TextInput name="aliases" placeholder="小张，张总" /></Field>
        <Field label="重要度"><TextInput name="importance" type="number" min="0" max="5" defaultValue="0" /></Field>
        <div className="flex items-end"><ActionButton icon={<Plus size={16} />}>新建</ActionButton></div>
        <div className="md:col-span-4">
          <Field label="简介"><TextArea name="bio" /></Field>
        </div>
      </form>
      <StatusMessage error={error} message={message} />

      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">姓名</th>
              <th className="px-4 py-3 font-medium">别名</th>
              <th className="px-4 py-3 font-medium">简介</th>
              <th className="px-4 py-3 font-medium">重要度</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((person) => (
              <tr key={person.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium"><Link href={`/people/${person.id}`} className="hover:underline">{person.name}</Link></td>
                <td className="px-4 py-3 text-slate-600">{joinList(person.aliases)}</td>
                <td className="px-4 py-3 text-slate-600">{person.bio}</td>
                <td className="px-4 py-3">{person.importance ?? 0}</td>
                <td className="px-4 py-3">
                  <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => remove(person)}>删除</ActionButton>
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr><td className="px-4 py-6 text-slate-500" colSpan={5}>暂无人物</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </PageSection>
  );
}
