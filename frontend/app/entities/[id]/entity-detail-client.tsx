"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Save, Trash2, UserPlus } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, Entity, Person } from "@/lib/api";

type EntityMember = {
  id: number;
  person_id: number;
  role?: string | null;
  person: Person;
};

type EntityDetail = {
  entity: Entity;
  members: EntityMember[];
};

export function EntityDetailClient({ id }: { id: number }) {
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [nextDetail, nextPeople] = await Promise.all([
      apiGet<EntityDetail>(`/api/entities/${id}`),
      apiGet<{ items: Person[] }>("/api/people")
    ]);
    setDetail(nextDetail);
    setPeople(nextPeople.items);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, [id]);

  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiJson<Entity>(`/api/entities/${id}`, "PATCH", {
        type: String(form.get("type") ?? ""),
        name: String(form.get("name") ?? ""),
        bio: String(form.get("bio") ?? "")
      });
      setMessage("已保存实体");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiJson(`/api/entities/${id}/members`, "POST", {
        person_id: Number(form.get("person_id")),
        role: String(form.get("role") ?? "")
      });
      formElement.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeMember(member: EntityMember) {
    try {
      await apiJson(`/api/entities/${id}/members/${member.person_id}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!detail) return <PageSection title="实体详情"><StatusMessage error={error} message="加载中" /></PageSection>;

  return (
    <PageSection title={detail.entity.name} actions={<Link href="/entities" className="text-sm text-slate-600 hover:underline">返回实体</Link>}>
      <StatusMessage error={error} message={message} />
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <form onSubmit={update} className="grid gap-3 rounded border border-slate-200 bg-white p-4 md:grid-cols-2">
          <Field label="名称"><TextInput name="name" defaultValue={detail.entity.name} required /></Field>
          <Field label="类型">
            <select name="type" defaultValue={detail.entity.type} className="min-h-10 rounded border border-slate-200 bg-white px-3 py-2 text-sm">
              <option value="company">公司</option>
              <option value="family">家庭</option>
              <option value="friend_group">朋友圈</option>
              <option value="org">组织</option>
            </select>
          </Field>
          <div className="md:col-span-2"><Field label="简介"><TextArea name="bio" defaultValue={detail.entity.bio ?? ""} /></Field></div>
          <ActionButton icon={<Save size={16} />}>保存</ActionButton>
        </form>

        <form onSubmit={addMember} className="space-y-3 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-base font-semibold">新增成员</h2>
          <Field label="人物">
            <select name="person_id" className="min-h-10 rounded border border-slate-200 bg-white px-3 py-2 text-sm" required>
              <option value="">选择人物</option>
              {people.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
            </select>
          </Field>
          <Field label="角色"><TextInput name="role" placeholder="老板/母亲/同事" /></Field>
          <ActionButton icon={<UserPlus size={16} />}>添加</ActionButton>
        </form>
      </div>

      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">成员</th>
              <th className="px-4 py-3 font-medium">角色</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {detail.members.map((member) => (
              <tr key={member.id} className="border-t border-slate-100">
                <td className="px-4 py-3"><Link href={`/people/${member.person_id}`} className="font-medium hover:underline">{member.person.name}</Link></td>
                <td className="px-4 py-3 text-slate-600">{member.role}</td>
                <td className="px-4 py-3"><ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => removeMember(member)}>移除</ActionButton></td>
              </tr>
            ))}
            {detail.members.length === 0 ? <tr><td className="px-4 py-6 text-slate-500" colSpan={3}>暂无成员</td></tr> : null}
          </tbody>
        </table>
      </div>
    </PageSection>
  );
}
