"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw, RotateCcw, Save, Wrench, X } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { TextArea } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, Extraction, Person, Relationship, SelfProfile } from "@/lib/api";

type ExtractionList = { items: Extraction[] };
type PersonDetail = { person: Person };
type DiffCurrentValues = Record<number, Record<string, unknown>>;
type StatusFilter = "pending" | "auto_applied" | "rejected" | "all";
type InboxLogEntry = {
  id: number;
  time: string;
  level: "info" | "error";
  action: string;
  path: string;
  detail: string;
};
type LoggedRequest = <T>(action: string, path: string, request: () => Promise<T>) => Promise<T>;

export function InboxPageClient() {
  const [items, setItems] = useState<Extraction[]>([]);
  const [diffCurrentValues, setDiffCurrentValues] = useState<DiffCurrentValues>({});
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingPayload, setEditingPayload] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<InboxLogEntry[]>([]);
  const [repairReasons, setRepairReasons] = useState<Record<number, string>>({});

  const appendLog = useCallback((entry: Omit<InboxLogEntry, "id" | "time">) => {
    setLogs((current) => [
      { ...entry, id: Date.now() + Math.random(), time: new Date().toLocaleTimeString("zh-CN", { hour12: false }) },
      ...current,
    ].slice(0, 20));
  }, []);

  const runRequest = useCallback<LoggedRequest>(async (action, path, request) => {
    appendLog({ level: "info", action, path, detail: "开始" });
    try {
      const result = await request();
      appendLog({ level: "info", action, path, detail: "成功" });
      return result;
    } catch (err) {
      appendLog({ level: "error", action, path, detail: `失败：${errorMessage(err)}` });
      throw err;
    }
  }, [appendLog]);

  const load = useCallback(async () => {
    setError(null);
    const statusQuery = statusFilter === "all" ? "" : statusFilter;
    const path = `/api/extractions?status=${encodeURIComponent(statusQuery)}`;
    const data = await runRequest("加载审核列表", path, () => apiGet<ExtractionList>(path));
    setItems(data.items);
    setDiffCurrentValues(await loadDiffCurrentValues(data.items, runRequest));
  }, [runRequest, statusFilter]);

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, [load]);

  async function accept(item: Extraction) {
    try {
      const path = `/api/extractions/${item.id}/accept`;
      await runRequest("接受抽取", path, () => apiJson<Extraction>(path, "POST"));
      setRepairReasons((current) => withoutKey(current, item.id));
      setMessage("已接受 1 条");
      await load();
    } catch (err) {
      const reason = errorMessage(err);
      setRepairReasons((current) => ({ ...current, [item.id]: reason }));
      setError(reason);
    }
  }

  async function undo(item: Extraction) {
    try {
      const path = `/api/extractions/${item.id}/undo`;
      await runRequest("撤销抽取", path, () => apiJson<Extraction>(path, "POST"));
      setMessage("已撤销 1 条");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function saveAndAccept(item: Extraction) {
    try {
      const payload = JSON.parse(editingPayload) as Record<string, unknown>;
      const updatePath = `/api/extractions/${item.id}`;
      const acceptPath = `/api/extractions/${item.id}/accept`;
      await runRequest("保存抽取", updatePath, () => apiJson<Extraction>(updatePath, "PATCH", { payload }));
      await runRequest("接受抽取", acceptPath, () => apiJson<Extraction>(acceptPath, "POST"));
      setEditingId(null);
      setEditingPayload("");
      setRepairReasons((current) => withoutKey(current, item.id));
      setMessage("已编辑并接受 1 条");
      await load();
    } catch (err) {
      const reason = errorMessage(err);
      setRepairReasons((current) => ({ ...current, [item.id]: reason }));
      setError(reason);
    }
  }

  async function repair(item: Extraction) {
    try {
      const path = `/api/extractions/${item.id}/repair`;
      const repaired = await runRequest("模型修正格式", path, () => apiJson<Extraction>(path, "POST", { error: repairReasons[item.id] ?? error }));
      setItems((current) => current.map((row) => (row.id === repaired.id ? repaired : row)));
      setEditingId(repaired.id);
      setEditingPayload(JSON.stringify(repaired.payload, null, 2));
      setRepairReasons((current) => withoutKey(current, item.id));
      setMessage("已用模型修正格式，请复核后再接受");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function reject(item: Extraction) {
    try {
      const path = `/api/extractions/${item.id}/reject`;
      await runRequest("拒绝抽取", path, () => apiJson<Extraction>(path, "POST"));
      setMessage("已拒绝 1 条");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function acceptAll() {
    const ids = items.filter((item) => item.status === "pending").map((item) => item.id);
    if (ids.length === 0) return;
    try {
      const result = await runRequest("批量接受", "/api/extractions/bulk", () => apiJson<{ accepted: number[]; rejected: number[] }>("/api/extractions/bulk", "POST", { accept: ids, reject: [] }));
      setMessage(`已接受 ${result.accepted.length} 条`);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <PageSection
      title="审核"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <span className="font-medium text-slate-700">状态筛选</span>
            <select
              aria-label="状态筛选"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value as StatusFilter);
                setDiffCurrentValues({});
                setEditingId(null);
                setEditingPayload("");
                setRepairReasons({});
              }}
              className="min-h-9 rounded border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-slate-500"
            >
              <option value="pending">待审核</option>
              <option value="auto_applied">自动应用</option>
              <option value="rejected">已拒绝</option>
              <option value="all">全部</option>
            </select>
          </label>
          <ActionButton type="button" variant="secondary" icon={<RefreshCw size={16} />} onClick={() => load().catch((err: Error) => setError(err.message))}>
            刷新
          </ActionButton>
          <ActionButton type="button" icon={<Check size={16} />} onClick={acceptAll} disabled={!items.some((item) => item.status === "pending")}>
            全部接受
          </ActionButton>
        </div>
      }
    >
      <StatusMessage error={error} message={message} />
      <div className="overflow-hidden rounded border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">类型</th>
              <th className="px-4 py-3 font-medium">摘要</th>
              <th className="px-4 py-3 font-medium">置信度</th>
              <th className="px-4 py-3 font-medium">状态</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-mono text-xs">{item.kind}</td>
                <td className="px-4 py-3">
                  <div className="grid gap-2">
                    {renderExtractionDetails(item, diffCurrentValues[item.id])}
                    {editingId === item.id ? (
                      renderExtractionEditor(item, editingPayload, setEditingPayload)
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-3">{item.confidence ?? "-"}</td>
                <td className="px-4 py-3">{item.status}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    {item.status === "pending" && editingId !== item.id ? (
                      <>
                        <ActionButton type="button" icon={<Check size={16} />} onClick={() => accept(item)}>接受</ActionButton>
                        {repairReasons[item.id] ? (
                          <ActionButton type="button" variant="secondary" icon={<Wrench size={16} />} onClick={() => repair(item)}>修正格式</ActionButton>
                        ) : null}
                        <ActionButton
                          type="button"
                          variant="secondary"
                          icon={<Save size={16} />}
                          onClick={() => {
                            setEditingId(item.id);
                            setEditingPayload(JSON.stringify(item.payload, null, 2));
                          }}
                        >
                          编辑
                        </ActionButton>
                        <ActionButton type="button" variant="danger" icon={<X size={16} />} onClick={() => reject(item)}>拒绝</ActionButton>
                      </>
                    ) : null}
                    {item.status === "pending" && editingId === item.id ? (
                      <>
                        <ActionButton type="button" icon={<Save size={16} />} onClick={() => saveAndAccept(item)}>保存并接受</ActionButton>
                        <ActionButton
                          type="button"
                          variant="secondary"
                          icon={<X size={16} />}
                          onClick={() => {
                            setEditingId(null);
                            setEditingPayload("");
                          }}
                        >
                          取消
                        </ActionButton>
                      </>
                    ) : null}
                    {item.status === "auto_applied" ? (
                      <ActionButton type="button" variant="danger" icon={<RotateCcw size={16} />} onClick={() => undo(item)}>撤销</ActionButton>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr><td className="px-4 py-6 text-slate-500" colSpan={5}>暂无待审核抽取</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {renderInboxLogs(logs)}
    </PageSection>
  );
}

function renderExtractionEditor(item: Extraction, editingPayload: string, setEditingPayload: (payload: string) => void) {
  const structuredRows = editableDiffRows(item, editingPayload);
  return (
    <div className="grid gap-2">
      {structuredRows.length > 0 ? (
        <div className="grid gap-2 rounded border border-slate-200 bg-white p-3 text-xs">
          {structuredRows.map((row) => (
            <label key={row.field} className="grid gap-1 sm:grid-cols-[10rem_1fr] sm:items-center">
              <span className="font-medium text-slate-700">新值 {row.field}</span>
              <input
                aria-label={`新值 ${row.field}`}
                value={editableValue(row.value)}
                onChange={(event) => setEditingPayload(updateEditingPayload(item, editingPayload, row.field, event.target.value))}
                className="min-h-9 rounded border border-slate-200 bg-white px-2 text-sm outline-none focus:border-slate-500"
              />
            </label>
          ))}
        </div>
      ) : null}
      <TextArea aria-label="Payload JSON" value={editingPayload} onChange={(event) => setEditingPayload(event.target.value)} rows={6} />
    </div>
  );
}

async function loadDiffCurrentValues(items: Extraction[], request: LoggedRequest): Promise<DiffCurrentValues> {
  const entries = await Promise.all(items.map(async (item) => {
    const payload = item.payload;
    try {
      if (item.kind === "self_update") {
        const profile = await request("加载当前画像", "/api/self", () => apiGet<SelfProfile>("/api/self"));
        return [item.id, profile as Record<string, unknown>] as const;
      } else if (item.kind === "person_update") {
        const personId = numberValue(payload.person_id);
        if (personId !== null) {
          const path = `/api/people/${personId}`;
          const detail = await request("加载当前人物", path, () => apiGet<PersonDetail>(path));
          return [item.id, (detail.person.profile_json ?? {}) as Record<string, unknown>] as const;
        }
      } else if (item.kind === "relationship_update") {
        const relationshipId = numberValue(payload.relationship_id);
        if (relationshipId !== null) {
          const path = `/api/relationships/${relationshipId}`;
          return [item.id, await request("加载当前关系", path, () => apiGet<Relationship>(path)) as Record<string, unknown>] as const;
        }
      }
    } catch {
      return null;
    }
    return null;
  }));
  return Object.fromEntries(entries.filter((entry) => entry !== null));
}

function renderInboxLogs(logs: InboxLogEntry[]) {
  return (
    <section className="rounded border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold">日志</h2>
      <div className="mt-3 grid gap-2 text-xs">
        {logs.map((log) => (
          <div key={log.id} className={`grid gap-1 rounded border p-2 ${log.level === "error" ? "border-rose-100 bg-rose-50 text-rose-800" : "border-slate-100 bg-slate-50 text-slate-700"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono">{log.time}</span>
              <span className="font-medium">{log.action}</span>
              <span className="font-mono">{log.path}</span>
            </div>
            <div>{log.detail}</div>
          </div>
        ))}
        {logs.length === 0 ? <div className="text-slate-500">暂无日志</div> : null}
      </div>
    </section>
  );
}

function renderExtractionDetails(item: Extraction, currentValues?: Record<string, unknown>) {
  const payload = item.payload;
  if (item.kind === "self_update") {
    return renderDiffSummary("更新我的画像", diffRows(payload.patches, currentValues));
  }
  if (item.kind === "person_update") {
    return renderDiffSummary(`更新人物 #${stringValue(payload.person_id)}`, diffRows(payload.profile_json, currentValues));
  }
  if (item.kind === "relationship_update") {
    return renderDiffSummary(`更新关系 #${stringValue(payload.relationship_id)}`, diffRows(payload, currentValues, ["relationship_id"]));
  }
  return <p>{renderExtractionSummary(item)}</p>;
}

function renderDiffSummary(title: string, rows: Array<{ field: string; current: unknown; value: unknown }>) {
  return (
    <div className="grid gap-2">
      <p>{title}</p>
      <div className="grid gap-2 rounded border border-slate-200 bg-slate-50 p-3 text-xs">
        {rows.map((row) => (
          <div key={row.field} className="grid gap-1 sm:grid-cols-[10rem_1fr_1fr] sm:items-start">
            <div className="font-mono text-slate-700">{row.field}</div>
            <div><span className="font-medium text-slate-600">现状：</span>{displayValue(row.current)}</div>
            <div><span className="font-medium text-slate-600">新值：</span>{displayValue(row.value)}</div>
          </div>
        ))}
        {rows.length === 0 ? <div className="text-slate-500">无可显示变更</div> : null}
      </div>
    </div>
  );
}

function diffRows(value: unknown, currentValues: Record<string, unknown> = {}, excludedKeys: string[] = []): Array<{ field: string; current: unknown; value: unknown }> {
  if (!isRecord(value)) return [];
  return Object.entries(value)
    .filter(([key]) => !excludedKeys.includes(key))
    .map(([field, rowValue]) => ({ field, current: currentValues[field], value: rowValue }));
}

function editableDiffRows(item: Extraction, editingPayload: string): Array<{ field: string; value: unknown }> {
  const payload = safeParsePayload(editingPayload, item.payload);
  if (item.kind === "self_update") {
    return editRows(payload.patches);
  }
  if (item.kind === "person_update") {
    return editRows(payload.profile_json);
  }
  if (item.kind === "relationship_update") {
    return editRows(payload, ["relationship_id"]);
  }
  return [];
}

function editRows(value: unknown, excludedKeys: string[] = []): Array<{ field: string; value: unknown }> {
  if (!isRecord(value)) return [];
  return Object.entries(value)
    .filter(([key]) => !excludedKeys.includes(key))
    .map(([field, rowValue]) => ({ field, value: rowValue }));
}

function updateEditingPayload(item: Extraction, editingPayload: string, field: string, text: string): string {
  const payload = safeParsePayload(editingPayload, item.payload);
  const value = parseEditableValue(text);
  if (item.kind === "self_update") {
    payload.patches = isRecord(payload.patches) ? { ...payload.patches, [field]: value } : { [field]: value };
  } else if (item.kind === "person_update") {
    payload.profile_json = isRecord(payload.profile_json) ? { ...payload.profile_json, [field]: value } : { [field]: value };
  } else if (item.kind === "relationship_update") {
    payload[field] = value;
  }
  return JSON.stringify(payload, null, 2);
}

function safeParsePayload(value: string, fallback: Record<string, unknown>): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value) as unknown;
    if (isRecord(parsed)) return parsed;
  } catch {
    return fallback;
  }
  return fallback;
}

function renderExtractionSummary(item: Extraction): string {
  const payload = item.payload;
  if (item.kind === "relationship_new") {
    return `我 → ${stringValue(payload.to_name ?? payload.to_id)}，${stringValue(payload.relation_type)}，角色：${stringValue(payload.role)}`;
  }
  if (item.kind === "self_update") {
    return `更新我的画像：${JSON.stringify(payload.patches ?? {}, null, 0)}`;
  }
  if (item.kind === "event_new") {
    return `事件：${stringValue(payload.title)}`;
  }
  if (item.kind === "person_new" || item.kind === "entity_new") {
    return stringValue(payload.name);
  }
  if (item.kind === "note_new") {
    return stringValue(payload.content);
  }
  return JSON.stringify(payload);
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseEditableValue(value: string): unknown {
  const trimmed = value.trim();
  if (trimmed === "") return "";
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}

function editableValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "";
  return JSON.stringify(value);
}

function displayValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "空";
  return JSON.stringify(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function withoutKey<T>(value: Record<number, T>, key: number): Record<number, T> {
  const next = { ...value };
  delete next[key];
  return next;
}

function errorMessage(value: unknown): string {
  return value instanceof Error ? value.message : String(value);
}
