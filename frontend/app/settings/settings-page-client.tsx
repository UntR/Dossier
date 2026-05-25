"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Download, RefreshCw, Save, Upload } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { Field, TextInput } from "@/components/form-field";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, apiJson, apiUrl, ModelProvider, SettingsData } from "@/lib/api";

type ModelsData = { providers: ModelProvider[] };

export function SettingsPageClient() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setError(null);
    const [nextSettings, nextModels] = await Promise.all([
      apiGet<SettingsData>("/api/settings"),
      apiGet<ModelsData>("/api/settings/models")
    ]);
    setSettings(nextSettings);
    setProviders(nextModels.providers);
  }

  useEffect(() => {
    load().catch((err: Error) => setError(err.message));
  }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const obsidianExportPath = String(form.get("obsidian_export_path") ?? "").trim();
    setError(null);
    setMessage(null);
    try {
      const updated = await apiJson<SettingsData>("/api/settings", "PATCH", {
        chat_model: String(form.get("chat_model") ?? ""),
        extraction_model: String(form.get("extraction_model") ?? ""),
        auto_extract_threshold: Number(form.get("auto_extract_threshold") ?? 0.85),
        obsidian_export_path: obsidianExportPath || null
      });
      setSettings(updated);
      setMessage("已保存设置");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function exportObsidian() {
    setError(null);
    setMessage(null);
    try {
      const result = await apiJson<{ people: number }>("/api/export/obsidian", "POST");
      setMessage(`已导出 ${result.people} 人`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const modelOptions = useMemo(
    () => providers.flatMap((provider) => provider.models),
    [providers]
  );

  if (!settings) {
    return (
      <PageSection title="设置">
        <StatusMessage error={error} message="加载中" />
      </PageSection>
    );
  }

  return (
    <PageSection
      title="设置"
      description="模型、阈值和本地导出路径集中在这里，保持为安静的工具页。"
      actions={
        <ActionButton type="button" variant="secondary" icon={<RefreshCw size={16} />} onClick={() => load().catch((err: Error) => setError(err.message))}>
          刷新
        </ActionButton>
      }
    >
      <StatusMessage error={error} message={message} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <form onSubmit={save} className="dossier-panel grid gap-4 p-4">
          <label className="grid gap-1 text-sm">
            <span className="font-medium text-[color:var(--dossier-muted)]">对话模型</span>
            <select
              name="chat_model"
              defaultValue={settings.chat_model ?? "anthropic/claude-sonnet-4-6"}
              className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]"
            >
              {modelOptions.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-medium text-[color:var(--dossier-muted)]">抽取模型</span>
            <select
              name="extraction_model"
              defaultValue={settings.extraction_model ?? "anthropic/claude-haiku-4-5-20251001"}
              className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]"
            >
              {modelOptions.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </label>
          <Field label="自动应用阈值">
            <TextInput name="auto_extract_threshold" type="number" min="0" max="1" step="0.01" defaultValue={String(settings.auto_extract_threshold ?? 0.85)} />
          </Field>
          <Field label="Obsidian 导出路径">
            <TextInput name="obsidian_export_path" defaultValue={settings.obsidian_export_path ?? ""} />
          </Field>
          <ActionButton icon={<Save size={16} />}>保存</ActionButton>
          <div className="flex flex-wrap gap-2 border-t border-[color:var(--dossier-line)] pt-4">
            <ActionButton type="button" variant="secondary" icon={<Upload size={16} />} onClick={exportObsidian}>
              导出到 Obsidian
            </ActionButton>
            <a
              href={apiUrl("/api/export/zip")}
              className="inline-flex min-h-9 items-center justify-center gap-2 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-1.5 text-sm font-semibold text-[color:var(--dossier-green)] transition hover:bg-[color:var(--dossier-green-soft)]"
            >
              <Download size={16} />
              <span>下载 ZIP</span>
            </a>
          </div>
        </form>

        <aside className="dossier-panel">
          <div className="dossier-panel-header">
            <h2 className="text-base font-semibold">模型 Provider</h2>
          </div>
          <div className="grid gap-3 p-4">
            {providers.map((provider) => (
              <div key={provider.provider} className="rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{providerLabel(provider.provider)}</p>
                  <span className={`rounded-[8px] px-2 py-1 text-xs ${provider.configured ? "bg-[color:var(--dossier-green-soft)] text-[color:var(--dossier-green)]" : "bg-[color:var(--dossier-panel-muted)] text-[color:var(--dossier-muted)]"}`}>
                    {provider.configured ? "可用" : "未配置"}
                  </span>
                </div>
                <p className="mt-2 break-words text-xs text-[color:var(--dossier-muted)]">{provider.models.join("，")}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </PageSection>
  );
}

function providerLabel(provider: string): string {
  const labels: Record<string, string> = {
    anthropic: "Anthropic",
    openai: "OpenAI",
    google: "Google",
    ollama: "Ollama"
  };
  return labels[provider] ?? provider;
}
