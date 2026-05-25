export const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiEnvelope<T> = {
  ok: boolean;
  data?: T;
  error?: string;
};

export type Person = {
  id: number;
  name: string;
  aliases?: string[] | null;
  bio?: string | null;
  profile_json?: Record<string, unknown> | null;
  photo_path?: string | null;
  importance?: number | null;
};

export type Entity = {
  id: number;
  type: string;
  name: string;
  bio?: string | null;
  profile_json?: Record<string, unknown> | null;
};

export type Relationship = {
  id: number;
  from_type: string;
  from_id?: number | null;
  to_type: string;
  to_id: number;
  relation_type: string;
  role?: string | null;
  strength?: number | null;
  status?: string | null;
  notes?: string | null;
};

export type EventItem = {
  id: number;
  occurred_at?: string | null;
  title: string;
  description?: string | null;
  participants?: Array<Record<string, unknown>> | null;
  source?: string | null;
  importance?: number | null;
};

export type LifeStage = {
  id: number;
  name: string;
  kind?: string | null;
  location?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  notes?: string | null;
  sort_order?: number | null;
};

export type SelfProfile = {
  id: number;
  name: string;
  bio?: string | null;
  communication_style?: string | null;
  sensitivities?: string[] | null;
  goals?: string[] | null;
  profile_json?: Record<string, unknown> | null;
};

export type ChatSession = {
  id: number;
  title?: string | null;
  summary?: string | null;
  chat_model?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
};

export type ChatMessage = {
  id?: number;
  session_id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  context_used?: ChatContext | null;
  created_at?: string | null;
};

export type ChatContext = {
  self?: SelfProfile | null;
  people?: Person[];
  relationships?: Relationship[];
  events?: EventItem[];
  entities?: Entity[];
};

export type SettingsData = Record<string, unknown> & {
  chat_model?: string;
  extraction_model?: string;
  auto_extract_threshold?: number;
  obsidian_export_path?: string | null;
};

export type ModelProvider = {
  provider: string;
  configured: boolean;
  models: string[];
};

export type Extraction = {
  id: number;
  session_id?: number | null;
  kind: string;
  target_id?: number | null;
  payload: Record<string, unknown>;
  confidence?: number | null;
  status?: string | null;
  applied_at?: string | null;
  created_at?: string | null;
};

export type ExtractionSummary = {
  created: number;
  auto_applied: number;
  pending: number;
};

export type TimelinePerson = {
  person_id: number;
  name: string;
  role_in_stage?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
};

export type TimelineEvent = {
  id: number;
  title: string;
  occurred_at?: string | null;
};

export type TimelineStage = {
  id: number;
  name: string;
  kind?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  people: TimelinePerson[];
  events: TimelineEvent[];
};

export type TimelineData = {
  self: { name: string; birthday?: string | null };
  stages: TimelineStage[];
};

export type ImportResult = {
  created: number;
  ids: number[];
};

export function apiUrl(path: string) {
  if (path.startsWith("http")) return path;
  return `${apiBaseUrl}${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export async function apiJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
}

export async function apiForm<T>(path: string, formData: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body: formData });
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { ...init, cache: "no-store" });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? ((await response.json()) as ApiEnvelope<T>) : null;
  if (!response.ok || !body?.ok) {
    throw new Error(body?.error ?? `${response.status} ${response.statusText}`);
  }
  return body.data as T;
}

export function splitList(value: string): string[] {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinList(value?: string[] | null): string {
  return (value ?? []).join("，");
}

export function toNumber(value: FormDataEntryValue | null): number | undefined {
  if (value === null || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
