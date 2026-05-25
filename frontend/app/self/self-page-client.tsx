"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Trash2 } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, joinList, LifeStage, SelfProfile, splitList, toNumber } from "@/lib/api";

export function SelfPageClient() {
  const [profile, setProfile] = useState<SelfProfile | null>(null);
  const [stages, setStages] = useState<LifeStage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [nextProfile, nextStages] = await Promise.all([
      apiGet<SelfProfile>("/api/self"),
      apiGet<{ items: LifeStage[] }>("/api/stages")
    ]);
    setProfile(nextProfile);
    setStages(nextStages.items);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiJson<SelfProfile>("/api/self", "PATCH", {
        name: String(form.get("name") ?? ""),
        bio: String(form.get("bio") ?? ""),
        communication_style: String(form.get("communication_style") ?? ""),
        sensitivities: splitList(String(form.get("sensitivities") ?? "")),
        goals: splitList(String(form.get("goals") ?? ""))
      });
      setMessage("已保存我的画像");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiJson<LifeStage>("/api/stages", "POST", {
        name: String(form.get("name") ?? ""),
        kind: String(form.get("kind") ?? ""),
        location: String(form.get("location") ?? ""),
        started_at: String(form.get("started_at") ?? ""),
        ended_at: String(form.get("ended_at") ?? "") || null,
        notes: String(form.get("notes") ?? ""),
        sort_order: toNumber(form.get("sort_order"))
      });
      formElement.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateStage(event: FormEvent<HTMLFormElement>, stage: LifeStage) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiJson<LifeStage>(`/api/stages/${stage.id}`, "PATCH", {
        name: String(form.get("name") ?? ""),
        kind: String(form.get("kind") ?? ""),
        location: String(form.get("location") ?? ""),
        started_at: String(form.get("started_at") ?? ""),
        ended_at: String(form.get("ended_at") ?? "") || null,
        notes: String(form.get("notes") ?? ""),
        sort_order: toNumber(form.get("sort_order"))
      });
      setMessage("已保存人生阶段");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeStage(stage: LifeStage) {
    try {
      await apiJson(`/api/stages/${stage.id}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!profile) return <PageSection title="我的画像"><StatusMessage error={error} message="加载中" /></PageSection>;

  return (
    <PageSection title="我的画像">
      <StatusMessage error={error} message={message} />
      <div className="grid gap-4 lg:grid-cols-[1fr_420px]">
        <form onSubmit={saveProfile} className="grid gap-3 rounded border border-slate-200 bg-white p-4 md:grid-cols-2">
          <Field label="姓名"><TextInput name="name" defaultValue={profile.name} required /></Field>
          <Field label="沟通风格"><TextInput name="communication_style" defaultValue={profile.communication_style ?? ""} /></Field>
          <Field label="敏感点"><TextInput name="sensitivities" defaultValue={joinList(profile.sensitivities)} /></Field>
          <Field label="目标"><TextInput name="goals" defaultValue={joinList(profile.goals)} /></Field>
          <div className="md:col-span-2"><Field label="简介"><TextArea name="bio" defaultValue={profile.bio ?? ""} /></Field></div>
          <ActionButton icon={<Save size={16} />}>保存</ActionButton>
        </form>

        <form onSubmit={createStage} className="space-y-3 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-base font-semibold">新增人生阶段</h2>
          <Field label="名称"><TextInput name="name" placeholder="大学/工作1" required /></Field>
          <Field label="类型"><TextInput name="kind" placeholder="教育/工作/其他" /></Field>
          <Field label="地点"><TextInput name="location" /></Field>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="开始"><TextInput name="started_at" type="date" /></Field>
            <Field label="结束"><TextInput name="ended_at" type="date" /></Field>
          </div>
          <Field label="排序"><TextInput name="sort_order" type="number" /></Field>
          <Field label="备注"><TextArea name="notes" /></Field>
          <ActionButton icon={<Save size={16} />}>添加</ActionButton>
        </form>
      </div>

      <div className="rounded border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">名称</th>
              <th className="px-4 py-3 font-medium">类型</th>
              <th className="px-4 py-3 font-medium">地点</th>
              <th className="px-4 py-3 font-medium">开始</th>
              <th className="px-4 py-3 font-medium">结束</th>
              <th className="px-4 py-3 font-medium">排序</th>
              <th className="px-4 py-3 font-medium">备注</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((stage) => (
              <tr key={stage.id} className="border-t border-slate-100">
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="name" defaultValue={stage.name} required className="min-h-9 w-32 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="kind" defaultValue={stage.kind ?? ""} className="min-h-9 w-24 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="location" defaultValue={stage.location ?? ""} className="min-h-9 w-28 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="started_at" type="date" defaultValue={stage.started_at ?? ""} className="min-h-9 w-36 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="ended_at" type="date" defaultValue={stage.ended_at ?? ""} className="min-h-9 w-36 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="sort_order" type="number" defaultValue={stage.sort_order ?? ""} className="min-h-9 w-20 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <input form={`stage-${stage.id}`} name="notes" defaultValue={stage.notes ?? ""} className="min-h-9 w-44 rounded border border-slate-200 px-2 text-sm outline-none focus:border-slate-500" />
                </td>
                <td className="px-3 py-3">
                  <form id={`stage-${stage.id}`} onSubmit={(event) => updateStage(event, stage)} className="flex gap-2">
                    <ActionButton icon={<Save size={16} />}>保存</ActionButton>
                    <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => removeStage(stage)}>删除</ActionButton>
                  </form>
                </td>
              </tr>
            ))}
            {stages.length === 0 ? <tr><td className="px-4 py-6 text-slate-500" colSpan={8}>暂无人生阶段</td></tr> : null}
          </tbody>
        </table>
      </div>
    </PageSection>
  );
}
