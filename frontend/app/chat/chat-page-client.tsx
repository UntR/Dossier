"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MessageSquarePlus, RefreshCw, Send } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextArea } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import {
  apiGet,
  apiJson,
  apiUrl,
  ChatContext,
  ChatMessage,
  ChatSession,
  ExtractionSummary,
  ModelProvider,
  SettingsData
} from "@/lib/api";

type SessionList = { items: ChatSession[] };
type SessionDetail = ChatSession & { messages: ChatMessage[] };
type ModelsData = { providers: ModelProvider[] };
type StreamEvent = { event: string; data: unknown };

export function ChatPageClient() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [context, setContext] = useState<ChatContext | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [chatModel, setChatModel] = useState("anthropic/claude-sonnet-4-6");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [extractionSummary, setExtractionSummary] = useState<ExtractionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadSessions(nextSelectedId = selectedSessionId) {
    const data = await apiGet<SessionList>("/api/chat/sessions");
    setSessions(data.items);
    if (nextSelectedId) {
      await loadSession(nextSelectedId);
    }
  }

  async function loadSession(sessionId: number) {
    const detail = await apiGet<SessionDetail>(`/api/chat/sessions/${sessionId}`);
    setSelectedSessionId(detail.id);
    setMessages(detail.messages);
    setContext(findLatestContext(detail.messages));
    setExtractionSummary(null);
  }

  async function loadSettings() {
    const [settings, providerData] = await Promise.all([
      apiGet<SettingsData>("/api/settings"),
      apiGet<ModelsData>("/api/settings/models")
    ]);
    setChatModel(settings.chat_model ?? "anthropic/claude-sonnet-4-6");
    setModels(providerData.providers.flatMap((provider) => provider.models));
  }

  useEffect(() => {
    Promise.all([loadSessions(null), loadSettings()]).catch((err: Error) => setError(err.message));
  }, []);

  async function selectModel(value: string) {
    setChatModel(value);
    setError(null);
    try {
      await apiJson<SettingsData>("/api/settings", "PATCH", { chat_model: value });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function startNewSession() {
    setSelectedSessionId(null);
    setMessages([]);
    setContext(null);
    setExtractionSummary(null);
    setMessage("已准备新会话");
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const content = String(form.get("content") ?? "").trim();
    if (!content || sending) return;

    setSending(true);
    setError(null);
    setMessage(null);
    formElement.reset();

    try {
      const sessionId = selectedSessionId ?? (await apiJson<{ session_id: number }>("/api/chat/sessions", "POST", { title: content.slice(0, 32) })).session_id;
      setSelectedSessionId(sessionId);
      setMessages((current) => [...current, { role: "user", content }, { role: "assistant", content: "" }]);

      await streamMessage(sessionId, content, {
        onContext: (nextContext) => setContext(nextContext),
        onDelta: (chunk) => {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: `${last.content}${chunk}` };
            }
            return next;
          });
        }
      });
      await loadSessions(sessionId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSending(false);
    }
  }

  async function endSession() {
    if (!selectedSessionId || ending) return;
    setEnding(true);
    setError(null);
    setMessage(null);
    try {
      const ended = await apiJson<ChatSession & { extractions: ExtractionSummary }>(`/api/chat/sessions/${selectedSessionId}/end`, "POST");
      await loadSessions(selectedSessionId);
      setExtractionSummary(ended.extractions);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setEnding(false);
    }
  }

  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId),
    [sessions, selectedSessionId]
  );

  return (
    <PageSection
      title="对话驾驶舱"
      description="从对话开始检索记忆、生成回复，并把候选变更送入审核队列。"
      actions={
        <div className="flex gap-2">
          <ActionButton type="button" variant="secondary" icon={<RefreshCw size={16} />} onClick={() => loadSessions().catch((err: Error) => setError(err.message))}>
            刷新
          </ActionButton>
          <ActionButton type="button" variant="secondary" icon={<MessageSquarePlus size={16} />} onClick={startNewSession}>
            新会话
          </ActionButton>
        </div>
      }
    >
      <StatusMessage error={error} message={message} />
      {extractionSummary ? (
        <div className="flex flex-wrap items-center gap-3 rounded-[8px] border border-[#b9cfb6] bg-[color:var(--dossier-green-soft)] px-4 py-3 text-sm text-[color:var(--dossier-green)]">
          <span>
            抽取了 {extractionSummary.created} 项，{extractionSummary.auto_applied} 项已自动应用，{extractionSummary.pending} 项待审核
          </span>
          {extractionSummary.pending > 0 ? <Link href="/inbox" className="font-medium underline">去审核</Link> : null}
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="dossier-panel">
          <div className="dossier-panel-header">
            <h2 className="text-sm font-semibold">会话</h2>
            <span className="dossier-chip">{sessions.length}</span>
          </div>
          <div className="space-y-2 p-3">
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => loadSession(session.id).catch((err: Error) => setError(err.message))}
                className={`w-full rounded-[8px] border px-3 py-2 text-left text-sm transition ${
                  session.id === selectedSessionId
                    ? "border-[color:var(--dossier-green)] bg-[color:var(--dossier-green-soft)]"
                    : "border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] hover:bg-[color:var(--dossier-panel-soft)]"
                }`}
              >
                <span className="block truncate font-medium">{session.title || `会话 ${session.id}`}</span>
                <span className="block truncate text-xs text-[color:var(--dossier-muted)]">{session.ended_at ? "已结束" : "进行中"}</span>
              </button>
            ))}
            {sessions.length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">暂无会话</p> : null}
          </div>
        </aside>

        <section className="dossier-panel flex min-h-[620px] flex-col">
          <div className="dossier-panel-header">
            <h2 className="text-base font-semibold">{selectedSession?.title || "新会话"}</h2>
            <span className="dossier-chip">引用优先</span>
          </div>
          <div className="flex flex-wrap gap-2 border-b border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] px-4 py-2 text-xs text-[color:var(--dossier-muted)]">
            <span>当前聚焦：{context?.people?.[0]?.name ?? "未锁定"}</span>
            <span>相关人物：{context?.people?.length ?? 0}</span>
            <span>相关事件：{context?.events?.length ?? 0}</span>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.map((item, index) => (
              <div key={`${item.role}-${item.id ?? index}`} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[78%] whitespace-pre-wrap rounded-[8px] border px-3 py-2 text-sm leading-6 ${
                  item.role === "user"
                    ? "border-[#c7d8c3] bg-[color:var(--dossier-green-soft)]"
                    : "border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)]"
                }`}>
                  {item.content || (item.role === "assistant" && sending ? "生成中..." : "")}
                </div>
              </div>
            ))}
            {messages.length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">输入一条消息开始对话</p> : null}
          </div>
          <form onSubmit={submitMessage} className="space-y-3 border-t border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-4">
            <Field label="消息">
              <TextArea name="content" placeholder="粘贴对方消息，或直接描述你想怎么回" disabled={sending} required />
            </Field>
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid gap-1 text-sm">
                <span className="font-medium text-[color:var(--dossier-muted)]">对话模型</span>
                <select
                  value={chatModel}
                  onChange={(event) => selectModel(event.target.value)}
                  className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]"
                >
                  {(models.length ? models : [chatModel]).map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </label>
              <ActionButton icon={<Send size={16} />} disabled={sending}>
                {sending ? "发送中" : "发送"}
              </ActionButton>
              <ActionButton type="button" variant="secondary" disabled={!selectedSessionId || sending || ending || Boolean(selectedSession?.ended_at)} onClick={endSession}>
                {ending ? "结束中" : "结束会话"}
              </ActionButton>
            </div>
          </form>
        </section>

        <ContextPanel context={context} />
      </div>
    </PageSection>
  );
}

function ContextPanel({ context }: { context: ChatContext | null }) {
  return (
    <aside className="dossier-panel">
      <div className="dossier-panel-header">
        <h2 className="text-base font-semibold">上下文</h2>
      </div>
      <div className="space-y-4 p-4">
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-2">
          <strong className="block text-lg">{context?.people?.length ?? 0}</strong>
          <span className="text-xs text-[color:var(--dossier-muted)]">人物</span>
        </div>
        <div className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-2">
          <strong className="block text-lg">{context?.relationships?.length ?? 0}</strong>
          <span className="text-xs text-[color:var(--dossier-muted)]">关系</span>
        </div>
        <div className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-2">
          <strong className="block text-lg">{context?.events?.length ?? 0}</strong>
          <span className="text-xs text-[color:var(--dossier-muted)]">事件</span>
        </div>
      </div>
      {context?.self ? (
        <section className="space-y-1 text-sm">
          <h3 className="font-medium text-[color:var(--dossier-muted)]">我的画像</h3>
          <p>{context.self.name}</p>
          {context.self.communication_style ? <p className="text-[color:var(--dossier-muted)]">沟通风格：{context.self.communication_style}</p> : null}
        </section>
      ) : null}
      <section className="space-y-2">
        <h3 className="text-sm font-medium text-[color:var(--dossier-muted)]">相关人物</h3>
        {(context?.people ?? []).map((person) => (
          <div key={person.id} className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-3 text-sm">
            <p className="font-medium">{person.name}</p>
            {person.bio ? <p className="mt-1 text-[color:var(--dossier-muted)]">{person.bio}</p> : null}
          </div>
        ))}
        {(context?.people ?? []).length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">暂无命中的人物</p> : null}
      </section>
      <section className="space-y-2">
        <h3 className="text-sm font-medium text-[color:var(--dossier-muted)]">相关事件</h3>
        {(context?.events ?? []).map((event) => (
          <div key={event.id} className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-3 text-sm">
            <p className="font-medium">{event.title}</p>
            {event.occurred_at ? <p className="mt-1 text-[color:var(--dossier-muted)]">{event.occurred_at}</p> : null}
          </div>
        ))}
        {(context?.events ?? []).length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">暂无相关事件</p> : null}
      </section>
      </div>
    </aside>
  );
}

function findLatestContext(messages: ChatMessage[]): ChatContext | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const context = messages[index].context_used;
    if (context) return context;
  }
  return null;
}

async function streamMessage(
  sessionId: number,
  content: string,
  handlers: { onContext: (context: ChatContext) => void; onDelta: (chunk: string) => void }
) {
  const response = await fetch(apiUrl(`/api/chat/sessions/${sessionId}/messages`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content })
  });
  if (!response.ok || !response.body) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      handleStreamEvent(parseSseEvent(part), handlers);
    }
  }
  if (buffer) {
    handleStreamEvent(parseSseEvent(buffer), handlers);
  }
}

function parseSseEvent(part: string): StreamEvent | null {
  const event = part.match(/^event: (.+)$/m)?.[1];
  const data = part.match(/^data: (.+)$/m)?.[1];
  if (!event || !data) return null;
  return { event, data: JSON.parse(data) };
}

function handleStreamEvent(
  parsed: StreamEvent | null,
  handlers: { onContext: (context: ChatContext) => void; onDelta: (chunk: string) => void }
) {
  if (!parsed) return;
  if (parsed.event === "context") {
    handlers.onContext(parsed.data as ChatContext);
  }
  if (parsed.event === "delta") {
    const data = parsed.data as { content?: string; text?: string };
    handlers.onDelta(data.content ?? data.text ?? "");
  }
}
