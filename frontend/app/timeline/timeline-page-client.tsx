"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import { ActionButton } from "@/components/action-button";
import { PageSection } from "@/components/page-section";
import { StatusMessage } from "@/components/status-message";
import { apiGet, LifeStage, Relationship, TimelineData, TimelineStage } from "@/lib/api";

type StageList = { items: LifeStage[] };
type RelationshipList = { items: Relationship[] };

export function TimelinePageClient() {
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [stageOptions, setStageOptions] = useState<LifeStage[]>([]);
  const [relationOptions, setRelationOptions] = useState<string[]>([]);
  const [stageId, setStageId] = useState("");
  const [relationType, setRelationType] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load(nextStageId = stageId, nextRelationType = relationType) {
    setError(null);
    const params = new URLSearchParams();
    if (nextStageId) params.set("stage_id", nextStageId);
    if (nextRelationType) params.set("relation_type", nextRelationType);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const data = await apiGet<TimelineData>(`/api/timeline${suffix}`);
    setTimeline(data);
  }

  async function loadOptions() {
    const [stages, relationships] = await Promise.all([
      apiGet<StageList>("/api/stages"),
      apiGet<RelationshipList>("/api/relationships")
    ]);
    setStageOptions(stages.items);
    setRelationOptions(uniqueRelationTypes(relationships.items));
  }

  useEffect(() => {
    Promise.all([loadOptions(), load("", "")]).catch((err: Error) => setError(err.message));
  }, []);

  const hasContent = useMemo(() => (timeline?.stages ?? []).some((stage) => stage.people.length > 0 || stage.events.length > 0), [timeline]);

  return (
    <PageSection
      title="时间树"
      description="以人生阶段为横轴，把人物轨道和事件点放在同一张时间视图里。"
      actions={
        <ActionButton type="button" variant="secondary" icon={<RefreshCw size={16} />} onClick={() => load().catch((err: Error) => setError(err.message))}>
          刷新
        </ActionButton>
      }
    >
      <StatusMessage error={error} />
      <div className="dossier-panel flex flex-wrap items-end gap-3 p-4">
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-[color:var(--dossier-muted)]">阶段过滤</span>
          <select
            value={stageId}
            onChange={(event) => {
              setStageId(event.target.value);
              load(event.target.value, relationType).catch((err: Error) => setError(err.message));
            }}
            className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]"
          >
            <option value="">全部阶段</option>
            {stageOptions.map((stage) => (
              <option key={stage.id} value={stage.id}>{stage.name}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-[color:var(--dossier-muted)]">关系类型过滤</span>
          <select
            value={relationType}
            onChange={(event) => {
              setRelationType(event.target.value);
              load(stageId, event.target.value).catch((err: Error) => setError(err.message));
            }}
            className="min-h-10 rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)] px-3 py-2 text-sm outline-none focus:border-[color:var(--dossier-green)]"
          >
            <option value="">全部关系</option>
            {relationOptions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="dossier-panel overflow-x-auto p-4">
        {timeline ? (
          <div className="min-w-[760px]">
            <div className="mb-4 flex items-center justify-between text-sm text-[color:var(--dossier-muted)]">
              <span>主体：{timeline.self.name}</span>
              <span className="dossier-chip">{timeline.stages.length} 个阶段</span>
            </div>
            {hasContent ? <TimelineBoard stages={timeline.stages} /> : <p className="text-sm text-[color:var(--dossier-muted)]">暂无时间树数据</p>}
          </div>
        ) : (
          <p className="text-sm text-[color:var(--dossier-muted)]">加载中</p>
        )}
      </div>
    </PageSection>
  );
}

function TimelineBoard({ stages }: { stages: TimelineStage[] }) {
  return (
    <div className="flex gap-4">
      {stages.map((stage) => (
        <section key={stage.id} className="min-w-72 flex-1 overflow-hidden rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel)]">
          <div className="border-b border-[color:var(--dossier-line)] bg-[color:var(--dossier-green)] px-4 py-3 text-[color:var(--dossier-panel)]">
            <div className="text-base font-semibold">{stage.name}</div>
            <div className="mt-1 text-xs opacity-80">{formatRange(stage.started_at, stage.ended_at)} · {stage.kind || "未分类"}</div>
          </div>
          <div className="space-y-4 p-4">
            <div className="space-y-2">
              <h2 className="text-sm font-medium text-[color:var(--dossier-muted)]">人物轨道</h2>
              {stage.people.map((person) => (
                <Link key={person.person_id} href={`/people/${person.person_id}`} className="block rounded-[8px] border border-[color:var(--dossier-line)] bg-[color:var(--dossier-panel-soft)] p-3 hover:bg-[color:var(--dossier-green-soft)]">
                  <div className="flex items-center gap-3">
                    <div className="h-1 flex-1 rounded bg-[color:var(--dossier-blue)]" />
                    <div className="min-w-28 text-right">
                      <div className="font-medium">{person.name}</div>
                      <div className="text-xs text-[color:var(--dossier-muted)]">{person.role_in_stage || "未设置角色"}</div>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-[color:var(--dossier-muted)]">{formatRange(person.started_at, person.ended_at)}</div>
                </Link>
              ))}
              {stage.people.length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">暂无人物轨道</p> : null}
            </div>
            <div className="space-y-2">
              <h2 className="text-sm font-medium text-[color:var(--dossier-muted)]">事件点</h2>
              {stage.events.map((event) => (
                <div key={event.id} className="rounded-[8px] border border-[#e5cf9f] bg-[#fbf2dc] p-3 text-sm">
                  <div className="font-medium">{event.title}</div>
                  <div className="mt-1 text-xs text-[color:var(--dossier-muted)]">{event.occurred_at}</div>
                </div>
              ))}
              {stage.events.length === 0 ? <p className="text-sm text-[color:var(--dossier-muted)]">暂无事件</p> : null}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}

function uniqueRelationTypes(items: Relationship[]): string[] {
  return Array.from(new Set(items.map((item) => item.relation_type).filter(Boolean))).sort();
}

function formatRange(start?: string | null, end?: string | null): string {
  return `${start || "未知"} - ${end || "至今"}`;
}
