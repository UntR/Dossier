"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Plus, RefreshCw, Search, Trash2 } from "lucide-react";

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
      title="人物档案"
      description="人物列表是 v2 的核心索引；导入和编辑能力收进人物详情或 API 流程。"
      actions={
        <ActionButton variant="secondary" icon={<RefreshCw size={16} />} title="刷新" onClick={() => load().catch((err: Error) => setError(err.message))}>
          刷新
        </ActionButton>
      }
    >
      <StatusMessage error={error} message={message} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="dossier-panel">
          <div className="dossier-panel-header">
            <div>
              <h2 className="text-sm font-semibold">人物列表</h2>
              <p className="text-xs text-[color:var(--dossier-muted)]">{items.length} 个档案</p>
            </div>
            <form onSubmit={(event) => { event.preventDefault(); load().catch((err: Error) => setError(err.message)); }} className="flex min-w-[320px] max-w-md flex-1 gap-2">
              <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按姓名、别名、简介搜索" />
              <ActionButton icon={<Search size={16} />}>搜索</ActionButton>
            </form>
          </div>
          <div className="overflow-x-auto">
            <table className="dossier-table">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>别名</th>
                  <th>简介</th>
                  <th>重要度</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((person) => (
                  <tr key={person.id}>
                    <td className="font-medium"><Link href={`/people/${person.id}`} className="hover:underline">{person.name}</Link></td>
                    <td className="text-[color:var(--dossier-muted)]">{joinList(person.aliases)}</td>
                    <td className="max-w-xl text-[color:var(--dossier-muted)]">{person.bio}</td>
                    <td>{person.importance ?? 0}</td>
                    <td>
                      <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => remove(person)}>删除</ActionButton>
                    </td>
                  </tr>
                ))}
                {items.length === 0 ? (
                  <tr><td className="px-4 py-6 text-[color:var(--dossier-muted)]" colSpan={5}>暂无人物</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="dossier-panel">
          <div className="dossier-panel-header">
            <h2 className="text-sm font-semibold">新建人物</h2>
            <span className="dossier-chip">手动补录</span>
          </div>
          <form onSubmit={create} className="grid gap-3 p-4">
            <Field label="姓名"><TextInput name="name" required /></Field>
            <Field label="别名"><TextInput name="aliases" placeholder="小张，张总" /></Field>
            <Field label="重要度"><TextInput name="importance" type="number" min="0" max="5" defaultValue="0" /></Field>
            <Field label="简介"><TextArea name="bio" /></Field>
            <ActionButton icon={<Plus size={16} />}>新建</ActionButton>
          </form>
        </aside>
      </div>
    </PageSection>
  );
}
