"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ClipboardPaste, FileUp, Upload } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiForm, apiGet, apiJson, ImportResult, Person } from "@/lib/api";

type PromptTemplate = { template: string };
type ImportTab = "file" | "llm" | "text";
type LlmMemoryData = Record<string, unknown> & {
  people?: Array<Record<string, unknown>>;
  entities?: Array<Record<string, unknown>>;
  events?: Array<Record<string, unknown>>;
  self?: Record<string, unknown> | null;
};
type LlmPreviewItem = {
  id: string;
  field: "people" | "entities" | "events" | "self";
  index: number;
  category: string;
  title: string;
  detail?: string;
};
type LlmPreview = {
  data: LlmMemoryData | null;
  error: string | null;
  items: LlmPreviewItem[];
  selectionKey: string;
};
type ImportProgress = {
  current: number;
  total: number;
  label: string;
} | null;

const tabs: Array<{ id: ImportTab; label: string }> = [
  { id: "file", label: "文件" },
  { id: "llm", label: "LLM 记忆" },
  { id: "text", label: "文本粘贴" }
];

export function ImportPageClient() {
  const [activeTab, setActiveTab] = useState<ImportTab>("file");
  const [people, setPeople] = useState<Person[]>([]);
  const [promptTemplate, setPromptTemplate] = useState("");
  const [memoryJson, setMemoryJson] = useState("");
  const llmPreview = useMemo(() => parseLlmMemoryPreview(memoryJson), [memoryJson]);
  const [selectedLlmPreviewIds, setSelectedLlmPreviewIds] = useState<string[]>([]);
  const [pastedText, setPastedText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importProgress, setImportProgress] = useState<ImportProgress>(null);
  const selectedLlmCount = selectedLlmPreviewIds.filter((id) => llmPreview.items.some((item) => item.id === id)).length;
  const importBusy = importProgress !== null;

  useEffect(() => {
    Promise.all([
      apiGet<{ items: Person[] }>("/api/people"),
      apiGet<PromptTemplate>("/api/import/llm-prompt-template")
    ])
      .then(([peopleData, promptData]) => {
        setPeople(peopleData.items);
        setPromptTemplate(promptData.template);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    setSelectedLlmPreviewIds(llmPreview.items.map((item) => item.id));
  }, [llmPreview.selectionKey]);

  async function importFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const files = form.getAll("file").filter((file): file is File => file instanceof File && file.size > 0);
    if (files.length === 0) {
      setError("请选择文件");
      return;
    }
    await submitFileBatch(form, files);
  }

  async function importText(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pastedText.trim()) {
      setError("请填写粘贴文本");
      return;
    }
    const form = new FormData(event.currentTarget);
    const file = new File([pastedText], "pasted.txt", { type: "text/plain" });
    const ok = await submitFileBatch(form, [file]);
    if (ok) setPastedText("");
  }

  async function importLlmMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (llmPreview.error) {
      setError(llmPreview.error);
      return;
    }
    if (!llmPreview.data) {
      setError("请填写 LLM JSON");
      return;
    }
    if (selectedLlmCount === 0) {
      setError("请选择至少一条要导入的内容");
      return;
    }
    try {
      setImportProgress({ current: 1, total: 1, label: "LLM 记忆" });
      const selectedData = buildSelectedLlmMemoryData(llmPreview.data, selectedLlmPreviewIds);
      const result = await apiJson<ImportResult>("/api/import/llm-memory", "POST", { json: JSON.stringify(selectedData) });
      setMessage(`已导入 ${result.created} 条`);
      setMemoryJson("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setImportProgress(null);
    }
  }

  async function submitFileBatch(form: FormData, files: File[]) {
    setError(null);
    setMessage(null);
    const personId = String(form.get("person_id") ?? "");
    let created = 0;
    try {
      for (const [index, file] of files.entries()) {
        setImportProgress({ current: index + 1, total: files.length, label: file.name || `文件 ${index + 1}` });
        const batchForm = new FormData();
        batchForm.set("file", file);
        if (personId) {
          batchForm.set("target_type", "person");
          batchForm.set("target_id", personId);
        } else {
          batchForm.set("target_type", "self");
        }
        const result = await apiForm<ImportResult>("/api/import/file", batchForm);
        created += result.created;
      }
      setMessage(files.length === 1 ? `已导入 ${created} 条` : `已导入 ${created} 条，处理 ${files.length} 个文件`);
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setImportProgress(null);
    }
  }

  return (
    <PageSection title="导入">
      <StatusMessage error={error} message={message} />
      {importProgress ? (
        <div role="status" aria-label="导入进度" className="mb-4 grid max-w-3xl gap-2 rounded border border-slate-200 bg-white p-3 text-sm text-slate-700">
          <div className="flex items-center justify-between gap-3">
            <span>正在导入 {importProgress.current} / {importProgress.total}：{importProgress.label}</span>
            <span>{Math.round((importProgress.current / importProgress.total) * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded bg-slate-100">
            <div className="h-full bg-slate-900 transition-all" style={{ width: `${(importProgress.current / importProgress.total) * 100}%` }} />
          </div>
        </div>
      ) : null}
      <div className="space-y-4">
        <div role="tablist" aria-label="导入方式" className="flex flex-wrap gap-2 border-b border-slate-200">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              id={`${tab.id}-tab`}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${activeTab === tab.id ? "border-slate-900 text-slate-950" : "border-transparent text-slate-500 hover:text-slate-800"}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "file" ? (
          <form id="file-panel" role="tabpanel" aria-labelledby="file-tab" onSubmit={importFile} className="grid max-w-2xl gap-4 rounded border border-slate-200 bg-white p-4">
            <PersonSelect people={people} />
            <Field label="文件">
              <input name="file" type="file" accept=".txt,.md,.docx" multiple className="text-sm" />
            </Field>
            <ActionButton icon={<FileUp size={16} />} disabled={importBusy}>导入文件</ActionButton>
          </form>
        ) : null}

        {activeTab === "llm" ? (
          <form id="llm-panel" role="tabpanel" aria-labelledby="llm-tab" onSubmit={importLlmMemory} className="grid max-w-3xl gap-4 rounded border border-slate-200 bg-white p-4">
            <Field label="提示词模板">
              <TextArea value={promptTemplate} readOnly rows={8} />
            </Field>
            <Field label="LLM JSON">
              <TextArea value={memoryJson} onChange={(event) => setMemoryJson(event.target.value)} rows={10} />
            </Field>
            {llmPreview.error ? <p className="text-sm text-rose-700">{llmPreview.error}</p> : null}
            {llmPreview.items.length > 0 ? (
              <fieldset className="grid gap-3 rounded border border-slate-200 bg-slate-50 p-3">
                <legend className="px-1 text-sm font-medium text-slate-700">LLM JSON 结构化预览</legend>
                <p className="text-sm text-slate-600">已选择 {selectedLlmCount} / {llmPreview.items.length} 条</p>
                <div className="grid gap-2">
                  {llmPreview.items.map((item) => (
                    <label key={item.id} className="flex gap-3 rounded border border-slate-200 bg-white p-3 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        aria-label={llmPreviewItemLabel(item)}
                        checked={selectedLlmPreviewIds.includes(item.id)}
                        onChange={(event) => toggleLlmPreviewItem(item.id, event.currentTarget.checked, setSelectedLlmPreviewIds)}
                      />
                      <span className="grid gap-1">
                        <span className="font-medium text-slate-900">{item.category} · {item.title}</span>
                        {item.detail ? <span className="text-slate-600">{item.detail}</span> : null}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
            <ActionButton icon={<Upload size={16} />} disabled={importBusy}>导入 LLM 记忆</ActionButton>
          </form>
        ) : null}

        {activeTab === "text" ? (
          <form id="text-panel" role="tabpanel" aria-labelledby="text-tab" onSubmit={importText} className="grid max-w-2xl gap-4 rounded border border-slate-200 bg-white p-4">
            <PersonSelect people={people} />
            <Field label="粘贴文本">
              <TextArea name="pasted_text" value={pastedText} onChange={(event) => setPastedText(event.target.value)} rows={8} />
            </Field>
            <ActionButton icon={<ClipboardPaste size={16} />} disabled={importBusy}>导入文本</ActionButton>
          </form>
        ) : null}
      </div>
    </PageSection>
  );
}

function parseLlmMemoryPreview(raw: string): LlmPreview {
  const trimmed = raw.trim();
  if (!trimmed) return { data: null, error: null, items: [], selectionKey: "" };

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { data: null, error: "LLM JSON 无法解析", items: [], selectionKey: trimmed };
  }
  if (!isRecord(parsed)) {
    return { data: null, error: "LLM JSON 必须是对象", items: [], selectionKey: trimmed };
  }

  const data = parsed as LlmMemoryData;
  const items = [
    ...previewArray("people", "人物", data.people, "name", "bio"),
    ...previewArray("entities", "实体", data.entities, "name", "bio"),
    ...previewArray("events", "事件", data.events, "title", "description"),
    ...previewSelf(data.self)
  ];
  return {
    data,
    error: null,
    items,
    selectionKey: items.map((item) => `${item.id}:${item.title}`).join("|")
  };
}

function previewArray(
  field: "people" | "entities" | "events",
  category: string,
  value: unknown,
  titleKey: string,
  detailKey: string
) {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((item, index) => ({
    id: `${field}:${index}`,
    field,
    index,
    category,
    title: String(item[titleKey] || `${category}${index + 1}`),
    detail: item[detailKey] ? String(item[detailKey]) : undefined
  }));
}

function previewSelf(value: unknown): LlmPreviewItem[] {
  if (!isRecord(value)) return [];
  return [
    {
      id: "self:0",
      field: "self",
      index: 0,
      category: "我的画像",
      title: "更新",
      detail: Object.keys(value).join("、")
    }
  ];
}

function buildSelectedLlmMemoryData(data: LlmMemoryData, selectedIds: string[]) {
  const selected = new Set(selectedIds);
  const next: LlmMemoryData = {};
  const people = selectedItems(data.people, "people", selected);
  const entities = selectedItems(data.entities, "entities", selected);
  const events = selectedItems(data.events, "events", selected);
  if (people.length > 0) next.people = people;
  if (entities.length > 0) next.entities = entities;
  if (events.length > 0) next.events = events;
  if (isRecord(data.self) && selected.has("self:0")) next.self = data.self;
  return next;
}

function llmPreviewItemLabel(item: LlmPreviewItem) {
  if (item.field === "self") return "导入我的画像更新";
  return `导入${item.category} ${item.title}`;
}

function selectedItems(value: unknown, field: "people" | "entities" | "events", selected: Set<string>) {
  if (!Array.isArray(value)) return [];
  return value.filter((item, index) => selected.has(`${field}:${index}`) && isRecord(item)) as Array<Record<string, unknown>>;
}

function toggleLlmPreviewItem(id: string, checked: boolean, setSelected: (updater: (current: string[]) => string[]) => void) {
  setSelected((current) => {
    if (checked) return current.includes(id) ? current : [...current, id];
    return current.filter((item) => item !== id);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function PersonSelect({ people }: { people: Person[] }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="font-medium text-slate-700">关联人物</span>
      <select name="person_id" className="min-h-10 rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500">
        <option value="">我的画像</option>
        {people.map((person) => (
          <option key={person.id} value={person.id}>{person.name}</option>
        ))}
      </select>
    </label>
  );
}
