"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ClipboardPaste, FileUp, Merge, Save, Trash2, Upload } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiForm, apiGet, apiJson, apiUrl, EventItem, ImportResult, joinList, LifeStage, Person, Relationship, splitList, toNumber } from "@/lib/api";

type StageAssignment = {
  id: number;
  person_id: number;
  stage_id: number;
  role_in_stage?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  stage?: LifeStage;
};

type PersonDetail = {
  person: Person;
  relationships: Relationship[];
  events: EventItem[];
  notes: Array<{ id: number; content: string }>;
  stages: StageAssignment[];
};

export function PersonDetailClient({ id }: { id: number }) {
  const [detail, setDetail] = useState<PersonDetail | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [stages, setStages] = useState<LifeStage[]>([]);
  const [tab, setTab] = useState("profile");
  const [memoryText, setMemoryText] = useState("");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setError(null);
    const [nextDetail, nextPeople, nextStages] = await Promise.all([
      apiGet<PersonDetail>(`/api/people/${id}`),
      apiGet<{ items: Person[] }>("/api/people"),
      apiGet<{ items: LifeStage[] }>("/api/stages")
    ]);
    setDetail(nextDetail);
    setPeople(nextPeople.items.filter((person) => person.id !== id));
    setStages(nextStages.items);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, [id]);

  function personName(personId?: number | null) {
    if (!personId) return "";
    if (personId === id) return detail?.person.name ?? `人物 ${personId}`;
    return people.find((person) => person.id === personId)?.name ?? `人物 ${personId}`;
  }

  function endpointLabel(type: string, endpointId?: number | null) {
    if (type === "self") return "我";
    if (type === "person") return personName(endpointId);
    return `${type} ${endpointId}`;
  }

  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiJson<Person>(`/api/people/${id}`, "PATCH", {
        name: String(form.get("name") ?? ""),
        aliases: splitList(String(form.get("aliases") ?? "")),
        bio: String(form.get("bio") ?? ""),
        importance: toNumber(form.get("importance")) ?? 0
      });
      setMessage("已保存人物画像");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function uploadPhoto(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiForm(`/api/people/${id}/photo`, form);
      setMessage("已上传头像");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function mergePerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const target = Number(form.get("target_person_id"));
    if (!target || !window.confirm("合并后当前人物会被删除，继续？")) return;
    try {
      await apiJson(`/api/people/${id}/merge`, "POST", { target_person_id: target });
      window.location.href = `/people/${target}`;
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createRelationship(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const direction = String(form.get("direction") ?? "self_current");
    const otherPersonId = Number(form.get("other_person_id"));
    let payload: Record<string, unknown> = {
      relation_type: String(form.get("relation_type") ?? ""),
      role: String(form.get("role") ?? ""),
      strength: toNumber(form.get("strength"))
    };
    if (direction === "self_current") {
      payload = { ...payload, from_type: "self", to_type: "person", to_id: id };
    } else if (direction === "current_other") {
      payload = { ...payload, from_type: "person", from_id: id, to_type: "person", to_id: otherPersonId };
    } else {
      payload = { ...payload, from_type: "person", from_id: otherPersonId, to_type: "person", to_id: id };
    }
    try {
      await apiJson<Relationship>("/api/relationships", "POST", payload);
      formElement.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteRelationship(relationship: Relationship) {
    try {
      await apiJson(`/api/relationships/${relationship.id}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function createEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiJson<EventItem>("/api/events", "POST", {
        occurred_at: String(form.get("occurred_at") ?? ""),
        title: String(form.get("title") ?? ""),
        description: String(form.get("description") ?? ""),
        participants: [{ type: "person", id }],
        source: "manual"
      });
      formElement.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateEvent(event: FormEvent<HTMLFormElement>, eventId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiJson<EventItem>(`/api/events/${eventId}`, "PATCH", {
        occurred_at: String(form.get("occurred_at") ?? ""),
        title: String(form.get("title") ?? ""),
        description: String(form.get("description") ?? ""),
        importance: toNumber(form.get("importance"))
      });
      setMessage("已保存事件");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteEvent(eventId: number) {
    try {
      await apiJson(`/api/events/${eventId}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function addStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await apiJson(`/api/people/${id}/stages`, "POST", {
        stage_id: Number(form.get("stage_id")),
        role_in_stage: String(form.get("role_in_stage") ?? ""),
        started_at: String(form.get("started_at") ?? "") || null,
        ended_at: String(form.get("ended_at") ?? "") || null
      });
      formElement.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeStage(stageId: number) {
    try {
      await apiJson(`/api/people/${id}/stages/${stageId}`, "DELETE");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function importMemoryFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const files = form.getAll("file").filter((file): file is File => file instanceof File && file.size > 0);
    if (files.length === 0) {
      setError("请选择文件");
      return;
    }
    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      let created = 0;
      for (const file of files) {
        const batchForm = new FormData();
        batchForm.set("file", file);
        batchForm.set("target_type", "person");
        batchForm.set("target_id", String(id));
        const result = await apiForm<ImportResult>("/api/import/file", batchForm);
        created += result.created;
      }
      setMessage(`已导入 ${created} 条记忆`);
      event.currentTarget.reset();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImporting(false);
    }
  }

  async function importMemoryText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!memoryText.trim()) {
      setError("请填写粘贴文本");
      return;
    }
    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      const form = new FormData();
      form.set("file", new File([memoryText], `${detail?.person.name ?? "person"}-memory.txt`, { type: "text/plain" }));
      form.set("target_type", "person");
      form.set("target_id", String(id));
      const result = await apiForm<ImportResult>("/api/import/file", form);
      setMessage(`已导入 ${result.created} 条记忆`);
      setMemoryText("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImporting(false);
    }
  }

  if (!detail) {
    return <PageSection title="人物详情"><StatusMessage error={error} message="加载中" /></PageSection>;
  }

  const person = detail.person;
  const tabs = [
    ["profile", "画像"],
    ["relationships", "关系"],
    ["events", "事件"],
    ["stages", "阶段"],
    ["notes", "笔记"],
    ["import", "导入记忆"]
  ];

  return (
    <PageSection title={person.name} description="人物详情承载画像、关系、事件、阶段、笔记和定向导入。" actions={<Link href="/people" className="text-sm text-[color:var(--dossier-muted)] hover:underline">返回人物</Link>}>
      <StatusMessage error={error} message={message} />
      <div className="flex flex-wrap gap-2 border-b border-[color:var(--dossier-line)]">
        {tabs.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={`border-b-2 px-3 py-2 text-sm font-semibold ${tab === key ? "border-[color:var(--dossier-green)] text-[color:var(--dossier-green)]" : "border-transparent text-[color:var(--dossier-muted)]"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "profile" ? (
        <div className="grid gap-4 lg:grid-cols-[180px_1fr]">
          <div className="space-y-3">
            {person.photo_path ? <img src={apiUrl(person.photo_path)} alt={`${person.name} 头像`} className="h-40 w-40 rounded-[8px] border border-[color:var(--dossier-line)] object-cover" /> : <div className="flex h-40 w-40 items-center justify-center rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] text-[color:var(--dossier-muted)]">无头像</div>}
            <form onSubmit={uploadPhoto} className="space-y-2">
              <input name="file" type="file" accept="image/*" className="text-sm" required />
              <ActionButton icon={<Upload size={16} />}>上传</ActionButton>
            </form>
          </div>
          <form onSubmit={updateProfile} className="dossier-panel grid gap-3 p-4 md:grid-cols-2">
            <Field label="姓名"><TextInput name="name" defaultValue={person.name} required /></Field>
            <Field label="别名"><TextInput name="aliases" defaultValue={joinList(person.aliases)} /></Field>
            <Field label="重要度"><TextInput name="importance" type="number" min="0" max="5" defaultValue={person.importance ?? 0} /></Field>
            <div className="flex items-end"><ActionButton icon={<Save size={16} />}>保存</ActionButton></div>
            <div className="md:col-span-2"><Field label="简介"><TextArea name="bio" defaultValue={person.bio ?? ""} /></Field></div>
          </form>
          <form onSubmit={mergePerson} className="dossier-panel space-y-3 p-4 lg:col-span-2">
            <h2 className="text-base font-semibold">合并人物</h2>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="目标人物">
                <select name="target_person_id" className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm">
                  <option value="">选择目标</option>
                  {people.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </Field>
              <ActionButton variant="danger" icon={<Merge size={16} />}>合并</ActionButton>
            </div>
          </form>
        </div>
      ) : null}

      {tab === "relationships" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="dossier-panel">
            {detail.relationships.map((relationship) => (
              <div key={relationship.id} className="flex items-start justify-between gap-3 border-b border-[color:var(--dossier-line)] p-4 text-sm last:border-0">
                <div>
                  <div className="font-medium">{relationship.relation_type} {relationship.role ? `· ${relationship.role}` : ""}</div>
                  <div className="text-[color:var(--dossier-muted)]">{endpointLabel(relationship.from_type, relationship.from_id)} → {endpointLabel(relationship.to_type, relationship.to_id)}</div>
                </div>
                <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => deleteRelationship(relationship)}>删除</ActionButton>
              </div>
            ))}
            {detail.relationships.length === 0 ? <p className="p-4 text-sm text-[color:var(--dossier-muted)]">暂无关系</p> : null}
          </div>
          <form onSubmit={createRelationship} className="dossier-panel space-y-3 p-4">
            <h2 className="text-base font-semibold">新增关系</h2>
            <Field label="方向">
              <select name="direction" className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm">
                <option value="self_current">我 → {person.name}</option>
                <option value="current_other">{person.name} → 其他人物</option>
                <option value="other_current">其他人物 → {person.name}</option>
              </select>
            </Field>
            <Field label="其他人物">
              <select name="other_person_id" className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm">
                <option value="">仅 person↔person 时选择</option>
                {people.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>
            <Field label="关系类型"><TextInput name="relation_type" placeholder="朋友/上下级/家人" required /></Field>
            <Field label="角色"><TextInput name="role" placeholder="老板/同学" /></Field>
            <Field label="强度"><TextInput name="strength" type="number" min="1" max="5" /></Field>
            <ActionButton icon={<Save size={16} />}>保存</ActionButton>
          </form>
        </div>
      ) : null}

      {tab === "events" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="space-y-3">
            {detail.events.map((item) => (
              <form key={item.id} onSubmit={(event) => updateEvent(event, item.id)} className="dossier-panel grid gap-3 p-4 md:grid-cols-4">
                <Field label="日期"><TextInput name="occurred_at" type="date" defaultValue={item.occurred_at ?? ""} /></Field>
                <Field label="标题"><TextInput name="title" defaultValue={item.title} required /></Field>
                <Field label="重要度"><TextInput name="importance" type="number" min="0" max="5" defaultValue={item.importance ?? 0} /></Field>
                <div className="flex items-end gap-2">
                  <ActionButton icon={<Save size={16} />}>保存</ActionButton>
                  <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => deleteEvent(item.id)}>删除</ActionButton>
                </div>
                <div className="md:col-span-4"><Field label="描述"><TextArea name="description" defaultValue={item.description ?? ""} /></Field></div>
              </form>
            ))}
            {detail.events.length === 0 ? <p className="dossier-panel p-4 text-sm text-[color:var(--dossier-muted)]">暂无事件</p> : null}
          </div>
          <form onSubmit={createEvent} className="dossier-panel space-y-3 p-4">
            <h2 className="text-base font-semibold">新增事件</h2>
            <Field label="日期"><TextInput name="occurred_at" type="date" /></Field>
            <Field label="标题"><TextInput name="title" required /></Field>
            <Field label="描述"><TextArea name="description" /></Field>
            <ActionButton icon={<Save size={16} />}>保存</ActionButton>
          </form>
        </div>
      ) : null}

      {tab === "stages" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="dossier-panel">
            {detail.stages.map((assignment) => (
              <div key={assignment.id} className="flex items-start justify-between gap-3 border-b border-[color:var(--dossier-line)] p-4 text-sm last:border-0">
                <div>
                  <div className="font-medium">{assignment.stage?.name ?? `阶段 ${assignment.stage_id}`}</div>
                  <div className="text-[color:var(--dossier-muted)]">{assignment.role_in_stage} {assignment.started_at ? `${assignment.started_at} - ${assignment.ended_at ?? "至今"}` : ""}</div>
                </div>
                <ActionButton type="button" variant="danger" icon={<Trash2 size={16} />} onClick={() => removeStage(assignment.stage_id)}>移除</ActionButton>
              </div>
            ))}
            {detail.stages.length === 0 ? <p className="p-4 text-sm text-[color:var(--dossier-muted)]">暂无阶段</p> : null}
          </div>
          <form onSubmit={addStage} className="dossier-panel space-y-3 p-4">
            <h2 className="text-base font-semibold">挂接阶段</h2>
            <Field label="阶段">
              <select name="stage_id" className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm" required>
                <option value="">选择阶段</option>
                {stages.map((stage) => <option key={stage.id} value={stage.id}>{stage.name}</option>)}
              </select>
            </Field>
            <Field label="阶段角色"><TextInput name="role_in_stage" placeholder="同学/室友/同事" /></Field>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="开始"><TextInput name="started_at" type="date" /></Field>
              <Field label="结束"><TextInput name="ended_at" type="date" /></Field>
            </div>
            <ActionButton icon={<Save size={16} />}>保存</ActionButton>
          </form>
        </div>
      ) : null}

      {tab === "notes" ? (
        <div className="dossier-panel">
          {detail.notes.map((note) => <p key={note.id} className="border-b border-[color:var(--dossier-line)] p-4 text-sm last:border-0">{note.content}</p>)}
          {detail.notes.length === 0 ? <p className="p-4 text-sm text-[color:var(--dossier-muted)]">暂无笔记</p> : null}
        </div>
      ) : null}

      {tab === "import" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <form onSubmit={importMemoryFile} className="dossier-panel grid gap-4 p-4">
            <h2 className="text-base font-semibold">导入文件到 {person.name}</h2>
            <Field label="文件">
              <input name="file" type="file" accept=".txt,.md,.docx" multiple className="text-sm" />
            </Field>
            <ActionButton icon={<FileUp size={16} />} disabled={importing}>导入文件</ActionButton>
          </form>
          <form onSubmit={importMemoryText} className="dossier-panel grid gap-4 p-4">
            <h2 className="text-base font-semibold">粘贴文本到 {person.name}</h2>
            <Field label="文本">
              <TextArea value={memoryText} onChange={(event) => setMemoryText(event.target.value)} rows={8} />
            </Field>
            <ActionButton icon={<ClipboardPaste size={16} />} disabled={importing}>导入文本</ActionButton>
          </form>
        </div>
      ) : null}
    </PageSection>
  );
}
