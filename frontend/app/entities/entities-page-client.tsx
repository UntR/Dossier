"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Plus, RefreshCw, Search, Trash2 } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, Entity } from "@/lib/api";

type EntityList = { items: Entity[]; limit: number; offset: number };

export function EntitiesPageClient() {
  const [items, setItems] = useState<Entity[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load(q = query) {
    setError(null);
    const suffix = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
    const data = await apiGet<EntityList>(`/api/entities${suffix}`);
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
      await apiJson<Entity>("/api/entities", "POST", {
        type: String(form.get("type") ?? "company"),
        name: String(form.get("name") ?? ""),
        bio: String(form.get("bio") ?? "")
      });
      formElement.reset();
      setMessage("已创建实体");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(entity: Entity) {
    if (!window.confirm(`删除 ${entity.name}？`)) return;
    try {
      await apiJson(`/api/entities/${entity.id}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <PageSection
      title="实体"
      actions={<ActionButton variant="secondary" icon={<RefreshCw size={16} />} onClick={() => load().catch((err: Error) => setError(err.message))}>刷新</ActionButton>}
    >
      <form onSubmit={(event) => { event.preventDefault(); load().catch((err: Error) => setError(err.message)); }} className="flex flex-wrap gap-2">
        <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按名称、简介搜索" />
        <ActionButton icon={<Search size={16} />}>搜索</ActionButton>
      </form>

      <form onSubmit={create} className="grid gap-3 rounded border border-slate-200 bg-white p-4 md:grid-cols-4">
        <Field label="名称"><TextInput name="name" required /></Field>
        <Field label="类型">
          <select name="type" className="min-h-10 rounded border border-slate-200 bg-white px-3 py-2 text-sm">
            <option value="company">公司</option>
            <option value="family">家庭</option>
            <option value="friend_group">朋友圈</option>
            <option value="org">组织</option>
          </select>
        </Field>
        <div className="flex items-end"><ActionButton icon={<Plus size={16} />}>新建</ActionButton></div>
        <div className="md:col-span-4"><Field label="简介"><TextArea name="bio" /></Field></div>
      </form>
      <StatusMessage error={error} message={message} />

      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">名称</th>
              <th className="px-4 py-3 font-medium">类型</th>
              <th className="px-4 py-3 font-medium">简介</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((entity) => (
              <tr key={entity.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium"><Link href={`/entities/${entity.id}`} className="hover:underline">{entity.name}</Link></td>
                <td className="px-4 py-3 text-slate-600">{entity.type}</td>
                <td className="px-4 py-3 text-slate-600">{entity.bio}</td>
                <td className="px-4 py-3"><ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => remove(entity)}>删除</ActionButton></td>
              </tr>
            ))}
            {items.length === 0 ? <tr><td className="px-4 py-6 text-slate-500" colSpan={4}>暂无实体</td></tr> : null}
          </tbody>
        </table>
      </div>
    </PageSection>
  );
}
