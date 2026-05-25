---
type: spec
status: draft-v1
created: 2026-05-23
updated: 2026-05-23
---

# Dossier — Software Design Specification

> 中国式人际沟通的 AI 顾问 + 用户拥有的关系记忆库。本文件是给 codex 的实施蓝本。

产品定位、价值主张、思考链路见 [README.md](README.md)。本 spec 只讲**怎么造**。

---

## 0. 实施原则（codex 必读）

1. **自用单机产品**：不做多租户、不做 SaaS 鉴权、监听 127.0.0.1。任何"为未来商业化"的过度设计都拒绝。
2. **数据主权归用户**：所有数据落本地文件 / SQLite。一键导出 markdown + JSON。文件结构对人可读。
3. **Docker Compose 是唯一启动方式**：`docker compose up` 起所有 web 端服务。例外是 MCP 桥接（见 §8）。
4. **模型可换**：通过 LiteLLM 抽象，chat 模型与抽取模型独立配置。
5. **中文优先**：UI / prompts / 默认数据都用中文。代码、log、commit message 用英文。
6. **激进抽取 + 事后审核**：聊天结束后自动抽实体进库，高风险变更进审核 inbox。
7. **写测试**：每个 API 端点和抽取流程都要有 pytest 用例。前端组件用 Playwright 跑关键 flow。
8. **暂不做的事**（明确）：多用户、云同步、移动端 App、付费、协作、E2E 加密（数据已经只在本地）。

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                       宿主机 (Mac/Win/Linux)                 │
│                                                              │
│   Claude Desktop ──stdio──> mcp_bridge.py (host Python)     │
│                                       │                      │
│                                       │ HTTP                 │
│                                       ▼                      │
│   ┌──────────── Docker Compose ──────────────────┐          │
│   │                                                │          │
│   │  ┌──────────┐    ┌──────────┐    ┌─────────┐ │          │
│   │  │ frontend │───▶│ backend  │───▶│ SQLite  │ │          │
│   │  │ Next.js  │    │ FastAPI  │    │ (volume)│ │          │
│   │  │ :3000    │    │ :8000    │    └─────────┘ │          │
│   │  └──────────┘    │          │                │          │
│   │                  │ LiteLLM  │──▶ Anthropic / │          │
│   │                  │          │    OpenAI /    │          │
│   │                  │          │    Google /    │          │
│   │                  │          │    Ollama      │          │
│   │                  └──────────┘                │          │
│   │                                                │          │
│   └────────────────────────────────────────────────┘          │
│                                                              │
│   ./data/  ──────▶  mounted as /data inside containers      │
│     ├── dossier.db                                           │
│     ├── uploads/                                             │
│     └── exports/                                             │
└─────────────────────────────────────────────────────────────┘
```

三层：
- **数据层**：SQLite + 本地文件
- **理解层**：FastAPI backend + LiteLLM
- **界面层**：Next.js web + MCP server（两张脸）

---

## 2. 技术栈

| 组件 | 选型 | 理由 |
|---|---|---|
| 后端语言 | Python 3.11+ | LLM 生态最强、MCP SDK 官方 |
| 后端框架 | FastAPI | 类型安全、async、自动 OpenAPI |
| ORM | SQLAlchemy 2.0 + Alembic | SQLite 支持成熟，迁移工具 |
| LLM 抽象 | LiteLLM | 一个接口覆盖 Anthropic/OpenAI/Google/Ollama |
| MCP | `mcp` (官方 Python SDK) | stdio + HTTP transport |
| 前端框架 | Next.js 15 App Router + TypeScript | 生态最广、chat UI 参考多 |
| UI 库 | Tailwind + shadcn/ui | 自用产品默认审美足够 |
| 图表 / 时间树 | visx 或 d3 | 时间树需要自定义渲染 |
| 文件解析 | `python-docx` (doc/docx), `markdown-it-py` (md) | 上传文档解析 |
| 容器化 | Docker Compose v2 | 跨平台一致 |
| 测试 | pytest (backend), Playwright (frontend) | 标配 |

---

## 3. 数据模型

完整 SQL schema 见 §3.2。先讲设计原则。

### 3.1 设计原则

- **"我" 是 root**：所有关系都从 `self_profile` 出发。单行表，id 固定为 1。
- **人生阶段是时间锚点**：`life_stage` 是你时间线的骨架（小学/初中/高中/大学/工作1/工作2/...）。每个 `person` 通过 `person_stage` 挂到一个或多个阶段。
- **关系是有方向的**：`from_*` → `to_*`，方便表达"我和老板"（self→person）和"老板和他老婆"（person→person）。
- **JSON 字段保留扩展性**：profile / payload 用 JSON 列，避免频繁 schema migration。
- **抽取走审核队列**：所有 LLM 抽出的变更先进 `extraction` 表，按规则 auto-apply 或留待审核。
- **FTS5 用于搜索**：人/实体/笔记都建全文索引。

### 3.2 SQL Schema

```sql
-- "我" (单行)
CREATE TABLE self_profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  bio TEXT,
  communication_style TEXT,          -- 我的沟通风格
  sensitivities JSON,                -- 敏感点列表
  goals JSON,                        -- 当下目标 / 价值观
  profile_json JSON,                 -- 其他字段
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 人生阶段（时间锚点）
CREATE TABLE life_stage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                -- '小学'/'清华大学'/'字节跳动'
  kind TEXT,                         -- '教育'/'工作'/'其他'
  location TEXT,
  started_at DATE,
  ended_at DATE,                     -- NULL = 进行中
  notes TEXT,
  sort_order INTEGER
);

-- 人
CREATE TABLE person (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,                -- 主要称呼
  aliases JSON,                      -- ['小张','张总','张三']
  bio TEXT,
  profile_json JSON,                 -- 性格/兴趣/职业/家庭/...
  photo_path TEXT,                   -- 相对 /data/uploads/photos/
  importance INTEGER DEFAULT 0,      -- 重要度（影响默认排序）
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 实体（公司/家庭/朋友圈/组织）
CREATE TABLE entity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,                -- 'company'/'family'/'friend_group'/'org'
  name TEXT NOT NULL,
  bio TEXT,
  profile_json JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 实体成员
CREATE TABLE entity_member (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id INTEGER NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
  person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  role TEXT,                         -- '老板'/'母亲'/'闺蜜'
  started_at DATE,
  ended_at DATE,
  UNIQUE(entity_id, person_id)
);

-- 关系
CREATE TABLE relationship (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_type TEXT NOT NULL,           -- 'self'/'person'
  from_id INTEGER,                   -- NULL 当 from_type='self'
  to_type TEXT NOT NULL,             -- 'person'/'entity'
  to_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL,       -- '上下级'/'家人'/'朋友'/'暧昧'/'同学'/'同事'/...
  role TEXT,                         -- 具体角色：'老板'/'下属'/'母亲'
  strength INTEGER,                  -- 1-5 强度
  status TEXT,                       -- '活跃'/'疏远'/'已结束'
  notes TEXT,
  started_at DATE,
  ended_at DATE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 人 ↔ 人生阶段
CREATE TABLE person_stage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  stage_id INTEGER NOT NULL REFERENCES life_stage(id) ON DELETE CASCADE,
  role_in_stage TEXT,                -- '同班同学'/'室友'/'师傅'
  started_at DATE,
  ended_at DATE,
  UNIQUE(person_id, stage_id)
);

-- 事件
CREATE TABLE event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at DATE,                  -- 日期级精度
  title TEXT NOT NULL,
  description TEXT,
  participants JSON,                 -- [{type:'person',id:1}, ...]
  source TEXT,                       -- 'chat'/'manual'/'import'/'upload'
  source_session_id INTEGER,
  importance INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 聊天会话
CREATE TABLE chat_session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  summary TEXT,
  chat_model TEXT,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ended_at TIMESTAMP
);

CREATE TABLE chat_message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
  role TEXT NOT NULL,                -- 'user'/'assistant'/'system'
  content TEXT NOT NULL,
  context_used JSON,                 -- 这条用了哪些 dossier 作为 context
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 抽取队列（待审核）
CREATE TABLE extraction (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER REFERENCES chat_session(id),
  kind TEXT NOT NULL,                -- 'person_new'/'person_update'/'event_new'/
                                     -- 'relationship_new'/'relationship_update'/'self_update'
  target_id INTEGER,                 -- 已有实体 ID（update 用）
  payload JSON NOT NULL,
  confidence REAL,                   -- 0.0-1.0
  status TEXT DEFAULT 'pending',     -- 'pending'/'accepted'/'rejected'/'auto_applied'
  applied_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 笔记（结构化前的原始文本）
CREATE TABLE note (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_type TEXT NOT NULL,         -- 'person'/'entity'/'self'
  target_id INTEGER,
  content TEXT NOT NULL,
  source TEXT,                       -- 'manual'/'upload_md'/'upload_doc'/'import_llm'
  source_file TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 设置
CREATE TABLE app_setting (
  key TEXT PRIMARY KEY,
  value JSON
);

-- FTS5 索引
CREATE VIRTUAL TABLE person_fts USING fts5(
  name, aliases, bio, profile_json, content=person, content_rowid=id
);
CREATE VIRTUAL TABLE entity_fts USING fts5(
  name, bio, profile_json, content=entity, content_rowid=id
);
CREATE VIRTUAL TABLE note_fts USING fts5(
  content, content=note, content_rowid=id
);

-- 触发器同步 FTS（INSERT/UPDATE/DELETE 三套）
```

### 3.3 默认设置项（app_setting 初始化）

| key | default | 说明 |
|---|---|---|
| `chat_model` | `anthropic/claude-sonnet-4-6` | 主对话模型 |
| `extraction_model` | `anthropic/claude-haiku-4-5-20251001` | 抽取/总结模型（便宜） |
| `auto_extract_threshold` | `0.85` | confidence ≥ 此值自动应用低风险变更 |
| `auto_extract_kinds` | `["event_new","person_new","note_new"]` | 哪些 kind 允许 auto-apply |
| `mcp_enabled` | `true` | |
| `language` | `zh-CN` | |
| `obsidian_export_path` | `null` | 设置后可同步导出 markdown 到 vault |

---

## 4. 后端 API

REST，所有路径前缀 `/api`。统一返回 `{ ok: bool, data?, error? }`。

### 4.1 Chat

- `POST /api/chat/sessions` — 新建会话，返回 `{ session_id }`
- `GET /api/chat/sessions` — 列出会话
- `GET /api/chat/sessions/:id` — 会话详情 + messages
- `POST /api/chat/sessions/:id/messages` — 发消息，server-sent events 流式返回
  - body: `{ content: str }`
  - 内部：先做 retrieval（见 §6），再调 chat model，返回 stream
- `POST /api/chat/sessions/:id/end` — 结束会话，触发抽取
- `DELETE /api/chat/sessions/:id`

### 4.2 People

- `GET /api/people` — list（query: `q`, `sort`, `limit`, `offset`）
- `POST /api/people` — 手动新建
- `GET /api/people/:id` — 详情（含 relationships, events, notes, stages）
- `PATCH /api/people/:id` — 更新
- `DELETE /api/people/:id`
- `POST /api/people/:id/photo` — 上传头像
- `POST /api/people/:id/merge` — 合并到另一个 person

### 4.3 Entities

同 people 的 CRUD，路径 `/api/entities`。额外：
- `POST /api/entities/:id/members` — 加成员
- `DELETE /api/entities/:id/members/:person_id`

### 4.4 Relationships

- `GET /api/relationships?from=...&to=...`
- `POST /api/relationships`
- `PATCH /api/relationships/:id`
- `DELETE /api/relationships/:id`

### 4.5 Events

- `GET /api/events?person_id=&since=&until=`
- `POST /api/events`
- `PATCH /api/events/:id`
- `DELETE /api/events/:id`

### 4.6 Life Stages

- `GET /api/stages`
- `POST /api/stages`
- `PATCH /api/stages/:id`
- `DELETE /api/stages/:id`

### 4.7 Self

- `GET /api/self`
- `PATCH /api/self`

### 4.8 Extraction (Inbox)

- `GET /api/extractions?status=pending`
- `POST /api/extractions/:id/accept` — 应用并标记 accepted
- `POST /api/extractions/:id/reject`
- `POST /api/extractions/bulk` — body: `{ accept: [ids], reject: [ids] }`

### 4.9 Import / Upload

- `POST /api/import/file` — multipart upload .md/.docx/.txt + target hint（person_id 或 entity_id 或新建）
  - 后端解析文本，调 extraction model，落 extraction 队列
- `POST /api/import/llm-memory` — body: `{ json: str }`（从 ChatGPT/Gemini 复制回来的 JSON）
  - 解析，进 extraction 队列
- `GET /api/import/llm-prompt-template` — 返回供用户复制到外部 LLM 的 prompt（见 §7.3）

### 4.10 Export

- `GET /api/export/zip` — 全量导出（DB + markdown + uploads）
- `POST /api/export/obsidian` — 同步到 `obsidian_export_path` 配置的目录

### 4.11 Settings

- `GET /api/settings`
- `PATCH /api/settings` — body: `{ key: value, ... }`
- `GET /api/settings/models` — 列出可用模型（探测各家 API key 配置 + ollama 本地模型）

### 4.12 Search

- `GET /api/search?q=...&type=...` — 跨 people/entities/notes/events 全文搜

### 4.13 Timeline

- `GET /api/timeline` — 返回完整时间树结构（见 §5.4 数据结构）

---

## 5. 前端页面

Next.js App Router。路由结构：

```
app/
├── layout.tsx                  # 全局导航
├── page.tsx                    # / -> 重定向到 /chat
├── chat/
│   ├── page.tsx               # 新会话
│   ├── [id]/page.tsx          # 历史会话
│   └── _components/
├── people/
│   ├── page.tsx               # 列表
│   ├── [id]/page.tsx          # 详情
│   └── new/page.tsx
├── entities/...
├── timeline/page.tsx
├── inbox/page.tsx
├── import/page.tsx
├── settings/page.tsx
├── self/page.tsx
└── search/page.tsx
```

### 5.1 `/chat` — 对话

- 左侧：会话列表
- 中间：消息流
- 右侧抽屉（可收起）：本次对话引用的 dossier（透明化 context，让用户看到 AI 在用什么）
- 输入框下方：模型切换器（快速切 chat_model）
- 会话结束时：弹出抽取摘要 → 进入 `/inbox` 审核或一键全部接受

### 5.2 `/people`

- 表格视图：头像 / 姓名 / 关系 / 最近接触 / 重要度
- 顶部搜索 + 过滤（关系类型、阶段、状态）
- 单个 detail 页：
  - Header：头像、姓名、别名、主关系、最近接触
  - Tabs：画像 / 关系 / 事件 / 笔记 / 时间线
  - 右上角：编辑、合并、删除
  - 画像 tab：profile_json 渲染为分块（性格/兴趣/职业/家庭...），支持手动编辑 + LLM 重新总结

### 5.3 `/entities`

类似 people，但 type 切换（公司/家庭/朋友圈/组织）。detail 多一个"成员"tab。

### 5.4 `/timeline` — 时间树

数据结构（API 返回）：

```typescript
type Timeline = {
  self: { name: string, birthday?: string };
  stages: Array<{
    id: number,
    name: string,        // '小学'
    kind: string,
    started_at: string,
    ended_at: string | null,
    people: Array<{
      person_id: number,
      name: string,
      role_in_stage: string,
      started_at: string,
      ended_at: string | null,
    }>,
    events: Array<{ id: number, title: string, occurred_at: string }>,
  }>;
};
```

渲染：
- **横向时间轴**为骨架（左→右，时间从早到晚）
- 阶段（life_stage）作为粗色块带
- 人作为**平行轨道**：每个人一条横线，从其 person_stage.started_at 起、到 ended_at 止
- 事件作为时间轴上的点（hover 展开）
- 鼠标悬停轨道 → 高亮该人在哪些阶段出现
- 点击轨道 → 跳 `/people/:id`
- 顶部 filter：按 stage 过滤、按 relation_type 过滤

实现库：visx 或 d3-timeline。

### 5.5 `/inbox` — 审核

- 列表：每条 extraction 一行，按 session 分组
- 卡片显示：
  - kind（人/事件/关系/画像）
  - confidence 进度条
  - payload 渲染（diff 形式：现状 → 新状）
  - 接受 / 拒绝 / 编辑后接受 三个按钮
- 顶部：全选 + 批量接受/拒绝
- auto_applied 的 extraction 也显示（标灰 + 可撤销）

### 5.6 `/import`

三个 tab：

**Tab 1: 文件上传**
- 拖拽区：支持 .md / .docx / .txt
- 选择目标：新建人 / 已有人 / 新建实体 / 已有实体
- 提交后：进 extraction 队列

**Tab 2: 跨 LLM 记忆导入**
- 显示 prompt template（带"复制"按钮）
- 文本框粘贴外部 LLM 的输出 JSON
- 解析 → 预览 → 提交到 extraction 队列

**Tab 3: 文本粘贴**
- 自由文本框 + 目标选择，等同 Tab 1 但不走文件

### 5.7 `/settings`

- 模型设置：chat_model / extraction_model（下拉，调 `/api/settings/models`）
- API keys：Anthropic / OpenAI / Google / Ollama base_url
- 抽取阈值：`auto_extract_threshold` 滑条
- Obsidian export 路径
- 备份/导出按钮
- 危险区：重置 / 删除全部数据

### 5.8 `/self` — 我的画像

- 编辑 self_profile 的所有字段
- 显示"由 AI 总结的画像"（来自抽取累积）vs "你手动填的"
- 一键"让 AI 根据近期会话重新总结我的画像"

---

## 6. Chat 流程（详细）

```
[user 输入] 
  → backend 接收
  → Retrieval：
      1. 用 extraction_model 对当前消息做 entity recognition
         （识别提到的人/公司/事件 → 解析为 ID）
      2. 加载相关 dossier（人画像 + 最近 30 天事件 + 相关关系）
      3. 加载 self_profile
  → 拼装 system prompt（见 §6.1）
  → 调 chat_model 流式生成
  → 边流式发回前端，边记录到 chat_message
  → 在 chat_message.context_used 记录用了哪些 dossier
```

### 6.1 Chat System Prompt 模板

```
你是用户的私人沟通顾问。用户名叫 {self.name}。

# 用户画像
{self_profile_rendered}

# 本次对话相关的人
{people_rendered}        # 每个人：姓名、关系、关键画像、最近事件

# 本次对话相关的实体
{entities_rendered}

# 回答要求
- 当用户问"XX 这条消息怎么回"时，输出格式严格按以下结构：
    1. 字面意思：他说了什么
    2. 可能的潜台词：列出 1-3 种解读，按概率
    3. 你想要的结果：基于用户画像和场景推测（或直接复述用户的明示）
    4. 备选回复：3 条，按风格不同（克制 / 中性 / 主动）
- 当用户是泛泛聊天时，正常对话即可
- 不要长篇说教
- 中文回答
```

### 6.2 抽取流程

会话结束触发（用户主动点"结束"或长时间无消息）：

```
1. 加载本会话所有 messages
2. 调 extraction_model，prompt 见 §6.3
3. 收到 JSON output
4. 每个抽出项：
   a. 计算 confidence
   b. 检查 kind 是否在 auto_extract_kinds 且 confidence ≥ auto_extract_threshold
   c. 若是 → 直接应用，extraction.status='auto_applied'
   d. 若否 → 落 extraction.status='pending'
5. 前端 toast: "抽取了 N 项，M 项已自动应用，K 项待审核"
```

### 6.3 Extraction Prompt 模板

```
你是用户的关系图谱抽取助手。

# 当前已知人物（避免重复创建）
{known_people_brief}     # id + name + aliases

# 当前已知实体
{known_entities_brief}

# 本次对话内容
{messages_rendered}

# 任务
识别本次对话中出现的：
1. 提及的人（链到已有 ID 或标记为新人）
2. 提及的实体（公司/家庭/朋友圈）
3. 发生的事件
4. 关系的新增或变化
5. 用户自身画像的更新

# 输出 JSON Schema
{
  "people": [
    {
      "name_used": "我老板",
      "matched_person_id": 5,        // null 若新人
      "is_new": false,
      "new_facts": { "profile_json": {...} },
      "confidence": 0.92
    }
  ],
  "entities": [...],
  "events": [
    {
      "occurred_at": "2026-05-22",
      "title": "...",
      "description": "...",
      "participants": [{"type":"person","matched_id":5}],
      "confidence": 0.88
    }
  ],
  "relationships": [
    {
      "from_type": "self",
      "to_type": "person",
      "to_id_or_name": 5,
      "relation_type": "上下级",
      "role": "老板",
      "change_kind": "update",       // 'new' 或 'update'
      "delta": {...},
      "confidence": 0.95
    }
  ],
  "self_updates": {
    "patches": {...},                // self_profile 字段更新
    "confidence": 0.7
  }
}

只输出 JSON，无任何解释。
```

### 6.4 Risk Tiers (auto-apply 判定)

| kind | risk | 默认 auto |
|---|---|---|
| `person_new` (only name + bio) | low | ✅ |
| `event_new` | low | ✅ |
| `note_new` | low | ✅ |
| `person_update` (only profile_json) | mid | ✅ if conf≥0.9 |
| `entity_new` | mid | ✅ if conf≥0.9 |
| `relationship_new` | high | ❌（强制审核） |
| `relationship_update` (type/status change) | high | ❌ |
| `self_update` | high | ❌ |

---

## 7. Import / Cross-LLM 同步

### 7.1 文件上传

- 接受 `.md`, `.docx`, `.txt`
- 解析为纯文本 → 切块（每块 ≤ 4K token）
- 对每块跑 extraction prompt（带 target hint）→ 落 extraction 队列
- UI 显示进度

### 7.2 Obsidian 同步导出

设置 `obsidian_export_path` 后：
- 触发 `POST /api/export/obsidian`，把每个 person 写为 markdown：

```markdown
---
type: person
name: 张三
aliases: [小张, 张总]
importance: 4
created: 2026-05-23
updated: 2026-05-23
---

# 张三

## 画像
{profile_json 渲染}

## 关系
- 上下级：我的老板（2024-至今）
- 同事：李四（同部门）

## 时间线
- 2024-03 入职字节，第一次见
- 2025-11 升职，开始管我

## 最近事件
- [[2026-05-22]] 周报会议批评加班不够

## 笔记
...
```

支持双向 link `[[]]`，可直接在 Obsidian 浏览。

### 7.3 跨 LLM 记忆导入 prompt

`GET /api/import/llm-prompt-template` 返回：

```
请回顾我们到目前为止的所有对话历史，梳理出其中提到的所有人、公司/组织、和重要事件。
我需要你按照下面的 JSON 格式输出，不要任何额外解释。

{
  "people": [
    {
      "name": "人名",
      "aliases": ["别名1"],
      "bio": "一句话简介",
      "profile": {
        "personality": "...",
        "occupation": "...",
        "relationship_to_user": "..."
      }
    }
  ],
  "entities": [
    {
      "type": "company|family|friend_group|org",
      "name": "...",
      "bio": "...",
      "members": ["人名1", "人名2"]
    }
  ],
  "events": [
    {
      "occurred_at": "YYYY-MM-DD 或 YYYY-MM 或 YYYY",
      "title": "...",
      "description": "...",
      "participants": ["人名"]
    }
  ],
  "self": {
    "communication_style": "...",
    "sensitivities": ["..."],
    "goals": ["..."]
  }
}

请尽可能完整。如果某些字段你不确定，留空字符串或空数组。
```

后端拿到 JSON 后：
- 对每个 person 做 fuzzy match（name + aliases）找 existing
- 全部包成 extraction 进队列，等用户审核

---

## 8. MCP Server

### 8.1 部署方式

**MCP server 不进 Docker**。原因是 Claude Desktop 通过 stdio 启动 MCP server，stdio 跨容器边界很麻烦。

方案：
- 仓库提供 `mcp/server.py`（依赖少：`mcp`, `httpx`, `pydantic`）
- 用户在 host 上 `pip install -r mcp/requirements.txt`（或用 `uv`）
- Claude Desktop 配置：

```json
{
  "mcpServers": {
    "dossier": {
      "command": "python",
      "args": ["/absolute/path/to/dossier/mcp/server.py"],
      "env": {
        "DOSSIER_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

- MCP server 内部用 httpx 调 backend HTTP API

### 8.2 MCP Tools

**意图级（高优先级，输出格式固定）**：

```python
@tool
async def interpret_message(
    message: str,
    from_hint: str | None = None,    # 发送者名字提示
    context_hint: str | None = None, # 场景：周报/吃饭/...
) -> InterpretResult:
    """解读一条收到的消息，给出潜台词分析和备选回复。"""
    # 内部：调 backend POST /api/mcp/interpret，backend 复用 chat 逻辑
```

返回结构：
```json
{
  "sender": { "matched_person": {...}, "confidence": 0.9 },
  "literal_meaning": "...",
  "possible_meanings": [
    { "interpretation": "...", "probability": "高" }
  ],
  "recommended_outcome": "...",
  "reply_options": [
    { "tone": "克制", "text": "...", "rationale": "..." },
    { "tone": "中性", "text": "...", "rationale": "..." },
    { "tone": "主动", "text": "...", "rationale": "..." }
  ]
}
```

```python
@tool
async def prepare_conversation(
    with_person: str,
    desired_outcome: str | None = None,
    scenario: str | None = None,
) -> PrepareResult: ...

@tool
async def stale_contacts(days: int = 30) -> list[StaleContact]: ...

@tool
async def recent_changes(person: str | None = None, days: int = 7) -> list[Change]: ...
```

**数据级（兜底）**：

```python
@tool
async def get_person(name_or_id: str) -> Person: ...

@tool
async def search_people(query: str, limit: int = 10) -> list[PersonBrief]: ...

@tool
async def get_relationship(person_a: str, person_b: str | None = None) -> list[Relationship]:
    """不传 person_b 则查 self↔person_a。"""

@tool
async def get_recent_events(
    person: str | None = None,
    days: int = 30,
) -> list[Event]: ...

@tool
async def get_self_profile() -> SelfProfile: ...

@tool
async def get_timeline(
    person: str | None = None,
    stage: str | None = None,
) -> Timeline: ...
```

### 8.3 Backend MCP Endpoints

为支持 MCP server，backend 新增：

- `POST /api/mcp/interpret` — body 同 `interpret_message` 参数
- `POST /api/mcp/prepare` — body 同 `prepare_conversation` 参数
- `GET /api/mcp/stale-contacts?days=`
- `GET /api/mcp/recent-changes?person=&days=`

数据级 tool 复用现有 REST endpoints。

---

## 9. Docker Compose 部署

### 9.1 `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/data
    environment:
      - DATABASE_URL=sqlite:////data/dossier.db
      - UPLOAD_DIR=/data/uploads
      - EXPORT_DIR=/data/exports
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - INTERNAL_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped
```

注意：
- 全部监听 `127.0.0.1`，外网访问不到（自用安全默认）
- SQLite 文件落 `./data/dossier.db`，备份只需 tar 这个目录
- Ollama 通过 `host.docker.internal` 访问宿主机服务（Mac/Win 原生支持，Linux 通过 `extra_hosts`）

### 9.2 `.env.example`

```
# 至少配一个 LLM provider
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### 9.3 启动 / 备份脚本

`scripts/start.sh`:
```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
[ ! -f .env ] && cp .env.example .env && echo "Filled .env first" && exit 1
mkdir -p data/uploads data/exports
docker compose up -d
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000/docs"
```

`scripts/backup.sh`:
```bash
#!/usr/bin/env bash
set -e
ts=$(date +%Y%m%d_%H%M%S)
tar -czf "backup_${ts}.tar.gz" data/
echo "Backup: backup_${ts}.tar.gz"
```

`scripts/reset.sh`（带确认）:
```bash
#!/usr/bin/env bash
read -p "This will DELETE all data. Type 'yes' to confirm: " c
[ "$c" != "yes" ] && exit 1
docker compose down -v
rm -rf data/
mkdir -p data
echo "Reset done. Run scripts/start.sh to start fresh."
```

---

## 10. 仓库结构

```
dossier/
├── README.md
├── SPEC.md                          # 本文件
├── docker-compose.yml
├── .env.example
├── .gitignore                       # data/, .env, node_modules, __pycache__
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # pydantic settings
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models.py            # SQLAlchemy models
│   │   ├── schemas/                 # Pydantic 输入输出 schema
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── people.py
│   │   │   ├── entities.py
│   │   │   ├── relationships.py
│   │   │   ├── events.py
│   │   │   ├── stages.py
│   │   │   ├── self_.py
│   │   │   ├── extractions.py
│   │   │   ├── importer.py
│   │   │   ├── export.py
│   │   │   ├── settings.py
│   │   │   ├── search.py
│   │   │   ├── timeline.py
│   │   │   └── mcp_intent.py        # POST /api/mcp/...
│   │   ├── llm/
│   │   │   ├── client.py            # LiteLLM 封装
│   │   │   ├── prompts/             # 各类 prompt template
│   │   │   │   ├── chat_system.py
│   │   │   │   ├── extraction.py
│   │   │   │   ├── interpret.py
│   │   │   │   └── prepare.py
│   │   │   └── streaming.py
│   │   ├── extraction/
│   │   │   ├── runner.py            # 抽取主逻辑
│   │   │   ├── matcher.py           # 人/实体 fuzzy match
│   │   │   ├── applier.py           # 应用 extraction 到 DB
│   │   │   └── risk.py              # auto-apply 判定
│   │   ├── chat/
│   │   │   ├── retrieval.py         # 取相关 dossier
│   │   │   ├── orchestrator.py
│   │   │   └── render.py            # dossier → prompt 渲染
│   │   ├── parsers/
│   │   │   ├── md.py
│   │   │   ├── docx.py
│   │   │   └── txt.py
│   │   └── utils/
│   └── tests/
│       ├── conftest.py
│       ├── test_chat.py
│       ├── test_extraction.py
│       └── test_mcp_intent.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── page.tsx                 # redirect /chat
│   │   ├── chat/
│   │   ├── people/
│   │   ├── entities/
│   │   ├── timeline/
│   │   ├── inbox/
│   │   ├── import/
│   │   ├── settings/
│   │   ├── self/
│   │   └── search/
│   ├── components/
│   │   ├── ui/                      # shadcn
│   │   ├── chat/
│   │   ├── people/
│   │   ├── timeline/                # Gantt-like
│   │   └── inbox/
│   ├── lib/
│   │   ├── api.ts                   # fetch 封装
│   │   ├── types.ts                 # 共享类型
│   │   └── utils.ts
│   └── tests/                       # Playwright
│
├── mcp/
│   ├── README.md                    # 安装说明 + Claude Desktop 配置示例
│   ├── requirements.txt
│   ├── server.py
│   └── tools/
│       ├── intent.py
│       └── data.py
│
├── data/                            # gitignored, mounted volume
│   ├── dossier.db
│   ├── uploads/
│   └── exports/
│
└── scripts/
    ├── start.sh
    ├── stop.sh
    ├── backup.sh
    ├── reset.sh
    └── install-mcp.sh               # 在 host 安装 MCP 依赖并打印 Claude Desktop 配置
```

---

## 11. 实施阶段（codex 按此顺序）

每个阶段结束有可见可用的能力，最后一阶段产品全量上线。

### Phase 1 — Scaffolding & Schema（1-2 天）
- 仓库结构、Docker Compose、`.env.example`、scripts
- Backend FastAPI 骨架 + healthcheck
- Alembic migrations 实现 §3.2 全部 schema + 默认 settings 种子
- Frontend Next.js 骨架 + 全局导航 + 空页面
- `docker compose up` 能起来，能访问 `http://localhost:3000`

### Phase 2 — CRUD & 基础页面（2-3 天）
- People / Entities / Relationships / Events / Life Stages / Self 全部 REST
- 对应前端 list + detail + edit 页面（不带 AI 抽取，纯手工录入）
- Search 端点 + 顶部搜索栏
- 此时已是一个可用的"手动版关系记录工具"

### Phase 3 — Chat & Retrieval（2-3 天）
- LLM client（LiteLLM）+ 模型探测端点
- `/api/chat/sessions` + streaming
- Retrieval：从消息识别提到的人 → 拉 dossier 进 system prompt
- 前端 chat 页面（消息流、流式、右侧 context 抽屉）
- Settings 页面（模型、API key）

### Phase 4 — Extraction Pipeline（2-3 天）
- Extraction runner + matcher + risk + applier
- `/api/chat/sessions/:id/end` 触发抽取
- `/inbox` 页面 + 接受/拒绝/批量操作
- Auto-apply 逻辑 + 撤销
- 此时已有完整的"对话进、关系出"闭环

### Phase 5 — Timeline（1-2 天）
- `/api/timeline` 拼装
- `/timeline` 页面（visx 实现横向时间轴 + 平行人轨道 + 事件点）
- 阶段过滤、关系类型过滤

### Phase 6 — Import / Export（2 天）
- `/import` 三个 tab（文件 / LLM 记忆 / 文本粘贴）
- 文件解析器（md / docx / txt）
- Cross-LLM prompt 模板 + JSON 解析进 extraction
- Export ZIP + Obsidian 同步

### Phase 7 — MCP Server（1-2 天）
- `mcp/server.py` 用官方 SDK
- 全部意图级 + 数据级 tool
- `scripts/install-mcp.sh` 打印 Claude Desktop 配置 JSON
- 端到端测试：从 Claude Desktop 调 `interpret_message` 跑通

### Phase 8 — 打磨与测试（持续）
- pytest 覆盖关键 backend 逻辑（特别是 extraction 和 retrieval）
- Playwright 跑核心 user flow（聊天 → 抽取 → 审核）
- 文档：README 加截图、quickstart
- 第一次自用 dogfooding，回流问题

---

## 12. 关键约束 / 易踩坑（codex 注意）

1. **流式响应必须真流式**：FastAPI 用 `StreamingResponse` + SSE。前端用 `EventSource` 或 `fetch+ReadableStream`。
2. **SQLite 并发**：开 WAL 模式。Alembic 初始化时执行 `PRAGMA journal_mode=WAL`。
3. **Person merge** 要级联更新：所有引用 source person_id 的表迁到 target，然后删 source。用事务。
4. **抽取 prompt 输出 JSON**：使用 model 的 JSON mode / structured output。LiteLLM 支持 `response_format={"type": "json_object"}`。
5. **fuzzy match 用 rapidfuzz**：name + aliases 都进 candidates pool，token_sort_ratio + threshold 80。
6. **MCP server 不要直接读 DB**：必须通过 HTTP API，避免双进程并发写 SQLite。
7. **前端类型用 OpenAPI 生成**：`openapi-typescript` 从 backend `/openapi.json` 生成 `lib/types.ts`，避免手抄。
8. **photo 上传**：存 `/data/uploads/photos/<sha1>.jpg`，DB 存路径。前端通过 `/api/files/photos/:filename` 取（backend 加白名单防穿越）。
9. **Docker for Mac 性能**：mount volume 用默认就行，self-use 流量不大。不要折腾 cached/delegated。
10. **不要在抽取里调 chat_model**：抽取专用 extraction_model（Haiku 价位）。混用会让单次会话成本飙升。

---

## 13. 验收标准

每个 phase 结束跑一遍对应验收，全过才算 done。

### Phase 1 验收
- [ ] `docker compose up` 起所有服务，无 error log
- [ ] `http://localhost:3000` 显示空导航
- [ ] `http://localhost:8000/health` 返回 ok
- [ ] DB 中所有表存在，settings 有默认行

### Phase 4 验收（最关键）
- [ ] 在 `/chat` 输入"我老板今天又说我加班不够"，AI 流式回复
- [ ] 回复结构符合 §6.1 中"如何回 XX 这条消息"的格式
- [ ] 结束会话后，`/inbox` 出现至少 1 条抽取（person/event/relationship 之一）
- [ ] 接受抽取后，`/people` 出现"老板"
- [ ] 再次开新对话提到"老板"，retrieval 命中已建档老板

### Phase 7 验收
- [ ] Claude Desktop 配置后，能看到 dossier MCP server
- [ ] 在 Claude Desktop 问"我老板这条消息怎么回：xxx"，能调用 `interpret_message`
- [ ] 返回格式符合 §8.2 的 `InterpretResult`

---

## 14. 后续 v2 候选（不在本次范围）

- 多语言（英文场景的 dossier）
- 多用户 / 协作
- 移动端 PWA
- E2E 加密 / 云同步
- 关系网络可视化（节点图，非时间轴）
- 主动提醒（cron-based "该联系 XX 了"）
- 接入微信/Slack/邮件等 IM 自动喂数据

---

## 15. 与 README 的关系

- [README.md](README.md) 是产品 brief（why / what / 战略选择）
- 本 SPEC.md 是工程蓝本（how）
- 实施过程中产品决策有调整 → 改 README；技术决策有调整 → 改本文件

---

## 16. 实施记录（living）

### 2026-05-23 — Phase 1 Scaffolding & Schema

- 仓库位置：`/Users/rzhang15/Documents/Dossier`。
- 已落地：FastAPI backend skeleton + `/health`、Alembic 初始 schema（含 §3.2 表、FTS5、默认 `app_setting`）、Next.js 15 App Router 空导航、`docker-compose.yml`、`.env.example`、启动/停止/备份/重置脚本、repo 内 `SPEC.md` 副本。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests -q` → `2 passed`
  - `npm run build` → Next.js production build 成功
  - `curl http://127.0.0.1:43261/health` → `{"ok":true}`
  - `curl http://127.0.0.1:43262` → `307 /chat`
  - `curl http://127.0.0.1:43262/chat` → `200`，页面含全局导航和 `/chat` 空状态
- 验证缺口：当前机器没有 `docker` 命令，尚未执行 `docker compose up`；Codex in-app browser 当前没有可用 `iab` target，因此本轮没有浏览器截图级 UI 验证。

### 2026-05-23 — Phase 2 Backend CRUD partial

- 已落地 backend REST：`/api/people`（CRUD、detail 聚合、merge、photo upload）、`/api/entities`（CRUD、members）、`/api/relationships`、`/api/events`、`/api/stages`、`/api/self`、`/api/search`。
- API 成功响应统一为 `{ ok: true, data }`；HTTPException 错误响应统一为 `{ ok: false, error }`。
- 新增 pytest 覆盖 people/entities/members/relationships/events/stages/self/search/merge/photo 的核心路径。
- 本地验证已通过：`.venv/bin/python -m pytest backend/tests -q` → `7 passed`。
- Phase 2 尚未完成：OpenAPI type generation、前端 CRUD 页面、relationship 双向显示 UI、merge/photo UI、顶部搜索栏和 `/search` 页面接入仍未实现。

### 2026-05-23 — Phase 2 Frontend CRUD partial

- 已落地 OpenAPI 类型生成：`scripts/export-openapi.py` + `frontend` 的 `npm run generate:types`，生成 `frontend/lib/openapi.json` 与 `frontend/lib/types.ts`。
- 已落地前端页面：全局搜索栏、`/people`、`/people/new`、`/people/:id`、`/entities`、`/entities/new`、`/entities/:id`、`/self`、`/search`。
- 前端已支持的手工维护能力：人物创建/搜索/删除/编辑/合并/头像上传、实体创建/搜索/删除/编辑/成员增删、自我画像编辑、人生阶段增删、人物详情中的 self→person 关系和事件新增、全局搜索结果展示。
- 后端补充：新增 `/api/files/photos/:filename` 头像读取；CORS 允许 `localhost` / `127.0.0.1` 的随机本地端口，兼容本地高位端口调试。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests -q` → `9 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
  - 高位端口本地 API 冒烟创建了人物、实体、成员并更新 self profile
- 验证缺口：Codex in-app browser 当前仍没有可用 target，本轮没有真实浏览器点击/截图级验证；Docker 仍未验证。
- Phase 2 尚未完成：端点仍是 dict payload，尚未按 spec 全面收敛为 Pydantic v2 schema；前端缺少 person↔person 关系创建、事件编辑/删除 UI、stage 编辑 UI、person_stage 维护入口；timeline 仍为空壳。

### 2026-05-23 — Phase 2 Pydantic schema contract

- 已将 Phase 2 主要写入端点从 `dict` payload 收敛为 Pydantic v2 schema：people、person merge、entities、entity members、relationships、events、life stages、self profile。
- OpenAPI 现在暴露具名 request schemas（如 `PersonCreate`、`RelationshipCreate`、`SelfProfileUpdate`），供 `openapi-typescript` 生成更可靠的前端类型。
- Request validation error 统一返回 `{ ok: false, error }`，与 REST envelope 约定一致。
- 已增加契约测试覆盖：缺少必填字段返回 422 envelope、OpenAPI request body 引用具名 schema、relationship `strength` 限制在 1-5。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests -q` → `12 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Phase 2 尚未完成：前端缺少 person↔person 关系创建、事件编辑/删除 UI、stage 编辑 UI、person_stage 维护入口；timeline 仍为空壳；真实浏览器点击验证与 Docker 验证仍缺。

### 2026-05-23 — Phase 2 Person detail graph maintenance

- 已新增 person↔life_stage nested API：`POST /api/people/:id/stages`、`DELETE /api/people/:id/stages/:stage_id`，并新增 `PersonStageCreate` Pydantic schema。
- `GET /api/people/:id` 的 `stages` 现在包含关联行和对应 `life_stage` 基本信息，方便前端直接展示。
- 人物详情页已补齐：
  - 关系 tab 支持 `self→person`、`person→person` 两种维护入口，并可删除关系。
  - 事件 tab 支持事件新增、编辑、删除。
  - 新增阶段 tab，支持把人物挂接到人生阶段和移除挂接。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests -q` → `13 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Phase 2 尚未完成：stage 编辑 UI 仍未实现；timeline 仍为空壳；真实浏览器点击验证与 Docker 验证仍缺。

### 2026-05-23 — Phase 2 browser verification and stage editing

- `/self` 的人生阶段列表现在支持行内编辑并保存 `name/kind/location/started_at/ended_at/sort_order/notes`，不再只支持新增/删除。
- 新增 Playwright e2e：`frontend/tests/phase2-crud.spec.ts`，通过高位随机端口启动 backend/frontend，覆盖手工维护主路径：创建人物、编辑 self、创建并编辑 stage、创建 person↔person 关系、挂接人物阶段、创建事件。
- Playwright 配置使用每次运行唯一 SQLite 文件：`.e2e-data/dossier-<run>.db`，避免测试互相污染。
- 修复真实浏览器验证发现的 React 表单 bug：异步提交后不能再直接使用 `event.currentTarget.reset()`，已改为 await 前保存 form element。
- 本地验证已通过：
  - `npm run test:e2e` → `1 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `13 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Docker 验证仍缺：当前机器执行 `docker --version` 返回 `command not found`。
- Phase 2 当前剩余：Docker Compose 实机验收仍无法执行；timeline 仍是空壳（Phase 5 才实现完整时间树）。

### 2026-05-23 — Phase 3 backend Chat & Retrieval partial

- 已落地 backend settings API：`GET/PATCH /api/settings` 和 `GET /api/settings/models`，模型探测按环境变量判断 Anthropic/OpenAI/Google，Ollama 默认可选。
- 已落地 backend chat API：`POST/GET /api/chat/sessions`、`GET /api/chat/sessions/:id`、`POST /api/chat/sessions/:id/messages` SSE streaming、`POST /api/chat/sessions/:id/end`、`DELETE /api/chat/sessions/:id`。
- 已落地最小 retrieval/render/orchestrator：消息按人物 name/aliases 命中 dossier，拉取 self profile、相关 person、relationship、event、entity 进入 system prompt，并把 context 记录到 user/assistant chat_message。
- LLM client 当前是本地 fallback 壳：未配置可用 provider 时返回“未配置可用模型”；真实 LiteLLM provider 调用仍未接入。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests -q` → `17 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Phase 3 尚未完成：真实 LiteLLM 调用、前端 `/chat` 消息流和 context 抽屉、前端 `/settings` 模型/API key UI 尚未实现；Docker Compose 实机验收仍无法执行。

### 2026-05-23 — Phase 3 frontend Chat & Settings partial

- `/chat` 已从空壳改为可用对话界面：左侧会话列表，中间消息流，右侧“本次引用”context 面板，输入区下方提供对话模型切换。
- `/chat` 现在会在首次发送时创建 chat session，通过 `fetch + ReadableStream` 消费 SSE，展示 user/assistant 消息，并把 retrieval context 中命中的人物、自我画像和事件展示给用户。
- `/settings` 已从空壳改为模型设置页：可保存 `chat_model`、`extraction_model`、`auto_extract_threshold`，并展示 Anthropic/OpenAI/Google/Ollama provider 配置状态和模型列表。
- 新增 Playwright e2e：`frontend/tests/phase3-chat-settings.spec.ts`，覆盖“建人物 + self profile → `/chat` 发送消息 → 看到 fallback 回复和引用 context”、以及“`/settings` 保存模型/阈值后刷新仍保留”。
- 本地验证已通过：
  - `npm run test:e2e -- phase3-chat-settings.spec.ts` → `2 passed`
  - `npm run test:e2e` → `3 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `17 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Browser 插件截图级验证缺口：本轮尝试连接 Codex in-app browser，返回 `Browser is not available: iab`；已用项目 Playwright e2e 覆盖交互验证。
- Phase 3 尚未完成：真实 LiteLLM provider 调用尚未接入；UI 暂不存储 API key，只展示环境配置状态；`/chat/:id` 独立历史路由和会话结束后的抽取摘要属于后续切片；Docker Compose 实机验收仍无法执行。

### 2026-05-23 — Phase 4 backend Extraction partial

- 已落地 backend extraction API：`GET /api/extractions?status=...`、`POST /api/extractions/:id/accept`、`POST /api/extractions/:id/reject`、`POST /api/extractions/bulk`。
- `POST /api/chat/sessions/:id/end` 现在会触发 extraction runner，并在响应中返回 `{ created, auto_applied, pending }` 摘要。
- 已落地最小 matcher/risk/applier：当前先用本地规则从 chat messages 和 retrieval context 识别已知人物、加班/进度类事件、老板/直属上级关系、自我敏感点更新；`event_new` 按 `auto_extract_kinds` + `auto_extract_threshold` 自动应用，`relationship_new` 和 `self_update` 强制进入 pending inbox。
- 已落地 applier 支持：`event_new`、`relationship_new`、`self_update`、`person_new`、`entity_new`、`note_new`，接受后写入对应业务表并标记 `accepted`，拒绝标记 `rejected`。
- 新增 pytest：`backend/tests/test_extractions.py`，覆盖 chat end 自动抽取/自动应用事件、pending relationship accept、self_update reject、bulk accept。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `19 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
  - `npm run test:e2e` → `3 passed`
- Phase 4 尚未完成：真实 LLM JSON extraction prompt 尚未接入；matcher 仍是规则型最小实现，不是 rapidfuzz/LLM 混合；`/inbox` 前端审核页仍为空壳；auto-apply 撤销未实现；会话结束后的前端抽取摘要 toast/入口尚未实现；Docker Compose 实机验收仍无法执行。

### 2026-05-23 — Phase 4 frontend Inbox review partial

- `/chat` 已新增“结束会话”操作：结束后调用 `POST /api/chat/sessions/:id/end`，展示“抽取了 N 项，M 项已自动应用，K 项待审核”的摘要，并在有待审核项时提供“去审核”入口。
- `/inbox` 已从空壳改为 pending extraction 审核页：展示 kind、摘要、confidence、status；支持单条接受、单条拒绝和全部接受。
- `/inbox` 接受 `relationship_new` 后会调用后端 applier 写入关系；拒绝 `self_update` 后不会修改 self profile。
- 修复并行浏览器验证发现的 `/api/self` 首次创建竞态：两个请求同时创建 `self_profile(id=1)` 时，现在捕获唯一约束冲突并回读已有记录。
- Playwright e2e 已扩展：覆盖“chat 结束会话 → 显示抽取摘要 → 进入 `/inbox` → 接受 relationship_new / 拒绝 self_update → 人物详情出现新关系”。
- 本地验证已通过：
  - `npm run test:e2e -- phase3-chat-settings.spec.ts` → `3 passed`
  - `npm run test:e2e` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `19 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Browser 插件截图级验证缺口：本轮再次尝试连接 Codex in-app browser，返回 `Browser is not available: iab`；已用项目 Playwright e2e 覆盖渲染交互。
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：真实 LLM JSON extraction prompt、rapidfuzz/LLM matcher、auto-apply 撤销、接受/拒绝后的审计详情页仍未实现。

### 2026-05-23 — Phase 5 Timeline partial

- 已落地 `GET /api/timeline`：聚合 self、life stages、person_stage 人物轨道和 stage 时间范围内的 event 点。
- `/api/timeline` 支持 `stage_id` 和 `relation_type` 查询过滤；`relation_type` 会按已有 relationship 筛选人物轨道和对应事件。
- `/timeline` 已从空壳改为可用时间树页面：顶部阶段过滤/关系类型过滤，主体为横向阶段带，每个阶段展示人物轨道、阶段角色、时间范围和事件点，人物轨道可点击跳转到 `/people/:id`。
- 本轮没有引入 visx/d3 新依赖；按项目约定，新依赖需要先说明理由并等待批准，所以当前使用 CSS 完成第一版横向时间轴。
- 新增测试：
  - `backend/tests/test_timeline.py` 覆盖 API 聚合、事件归档、stage/relation 过滤。
  - `frontend/tests/phase5-timeline.spec.ts` 覆盖 UI 创建数据、过滤 timeline、展示阶段/人物/事件并跳转人物详情。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_timeline.py -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `21 passed`
  - `npm run test:e2e -- phase5-timeline.spec.ts` → `1 passed`
  - `npm run test:e2e` → `5 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
- Browser 插件截图级验证缺口：本轮尝试连接 Codex in-app browser，返回 `Browser is not available: iab`；已用项目 Playwright e2e 覆盖渲染交互。
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 5 尚未完成：visx/d3 版本的真实比例轴、hover 高亮同一人物跨阶段轨道、事件 hover 展开详情仍未实现。

### 2026-05-23 — Phase 6 backend Import/Export partial

- 已落地 import API：`POST /api/import/file`、`POST /api/import/llm-memory`、`GET /api/import/llm-prompt-template`。
- 文件导入支持 `.txt`、`.md`、`.docx`：`.txt/.md` 按 UTF-8 解码，`.docx` 用标准库 `zipfile + ElementTree` 解析 `word/document.xml`，不新增依赖。
- 文件导入当前生成 `note_new` pending extraction，保留 `target_type`、`target_id`、`source_file` 和原文内容，等待用户在 `/inbox` 审核。
- 外部 LLM 记忆 JSON 导入当前会生成 pending extraction：`person_new`、`entity_new`、`event_new`、`self_update`。
- 已落地 export API：`GET /api/export/zip` 和 `POST /api/export/obsidian`。
- ZIP 导出包含 `dossier.json` 数据快照、`people/*.md` 人物 markdown、当前 SQLite 文件（若可定位）和 uploads 目录文件（若存在）。
- Obsidian 导出读取 `app_setting.obsidian_export_path`，把人物 markdown 写入 `<path>/people/*.md`，写文件显式使用 UTF-8。
- 新增测试：`backend/tests/test_import_export.py` 覆盖文件导入、跨 LLM JSON 导入、prompt template、ZIP 内容和 Obsidian markdown 文件写出。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `23 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run test:e2e` → `5 passed`
  - `npm run build` → Next.js production build 成功（单独运行）
- 验证注意：一次把 `npm run build` 与 `npm run test:e2e` 并行运行时，`next build` 与 `next dev` 争用 `.next`，出现 `Cannot find module for page`；e2e 结束后单独重跑 build 通过。
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 6 尚未完成：`/import` 前端三 tab、文件导入进度、外部 LLM JSON 预览、导出按钮 UI、导入抽取的 fuzzy match 去重、完整 `.docx` 复杂格式支持仍未实现。

### 2026-05-23 — Phase 6 frontend Import/Export partial

- `/import` 已从空壳改为三 tab 导入页：文件导入、外部 LLM 记忆 JSON 导入、文本粘贴导入。
- 文件导入和文本粘贴当前都复用 `POST /api/import/file`，可选择关联人物；未选择人物时落到 self，导入后生成 `note_new` pending extraction 并进入 `/inbox` 审核。
- LLM 记忆 tab 会读取并展示 `GET /api/import/llm-prompt-template`，提交 JSON 到 `POST /api/import/llm-memory`，生成 `person_new/event_new/self_update` 等 pending extraction。
- `/settings` 已补齐 `obsidian_export_path` 配置项，支持保存后点击“导出到 Obsidian”触发 `POST /api/export/obsidian`，并提供“下载 ZIP”入口到 `GET /api/export/zip`。
- 新增 Playwright e2e：`frontend/tests/phase6-import-export.spec.ts`，覆盖三类导入生成 pending extraction、Obsidian 导出写出 markdown、ZIP 下载文件名。
- 修正既有 Phase 3 e2e 的并行隔离假设：`self_update` 审核断言现在按本测试产生的“被催”行定位，不再要求全局 inbox 为空；原因是全量 e2e 多 worker 共享同一个临时 SQLite DB，其他测试可合法产生 pending extraction。
- 本地验证已通过：
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `23 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run test:e2e` → `7 passed`
  - `npm run build` → Next.js production build 成功（单独运行）
- Browser 插件截图级验证缺口：本轮尝试连接 Codex in-app browser，返回 `Browser is not available: iab`；已用项目 Playwright e2e 覆盖渲染交互。
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 6 尚未完成：导入进度条/批量进度、外部 LLM JSON 结构化预览与逐条确认、导入抽取的 fuzzy match 去重、完整 `.docx` 复杂格式支持仍未实现。

### 2026-05-23 — Phase 7 MCP Server partial

- 已落地 backend MCP intent endpoints：`POST /api/mcp/interpret`、`POST /api/mcp/prepare`、`GET /api/mcp/stale-contacts`、`GET /api/mcp/recent-changes`。
- `interpret` 当前复用 retrieval context 查找 sender/person/relationship/events，并返回 §8.2 要求的固定 JSON 结构：`sender`、`literal_meaning`、`possible_meanings`、`recommended_outcome`、`reply_options`、`context_used`。
- `prepare` 当前按人物姓名/别名/ID 查 dossier，返回 person、relationship summary、recent events、talking points、risks 和 suggested opening。
- 已落地 host-side MCP server：`mcp/server.py` 使用官方 Python SDK `FastMCP` 注册 §8.2 的 10 个 tool。
- 已落地 MCP tool modules：`mcp/tools/intent.py` 和 `mcp/tools/data.py`；所有 tool 均通过 `httpx` 调 backend HTTP API，不直接读 SQLite。
- 已落地 `mcp/requirements.txt`、`mcp/README.md` 和 `scripts/install-mcp.sh`；安装脚本会安装依赖并打印 Claude Desktop 配置 JSON。
- 新增测试：
  - `backend/tests/test_mcp_intent.py` 覆盖 interpret/prepare/stale/recent backend endpoints。
  - `backend/tests/test_mcp_tools.py` 覆盖 MCP tool wrapper 调用 HTTP helper、data tool 复用现有 REST API，以及 `mcp/server.py` 从文件路径导入时能找到本地 tools。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py backend/tests/test_mcp_tools.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `28 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip install -r mcp/requirements.txt` → 成功安装 `mcp-1.27.1`
  - `mcp/server.py` import 级验证 → 输出 `Dossier`
  - `bash -n scripts/install-mcp.sh && test -x scripts/install-mcp.sh` → 成功
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
  - `npm run test:e2e` → `7 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `interpret_message`；`interpret` 当前是结构化本地 fallback，尚未接入真实 `chat_model` LLM JSON 输出。

### 2026-05-23 — Phase 6 Import/Export hardening partial

- `/api/import/file` 已增加 10MB 上传限制，超过返回 `413` 和清晰错误 `file exceeds 10MB limit`。
- 文件导入已增加文本切块：每块最多 4000 字符，长文件会生成多条 `note_new` pending extraction；payload 记录 `source_chunk_index` 和 `source_chunk_total`，方便审核时识别来源顺序。
- `/api/export/zip` 已加入 `schema.sql`，内容来自 SQLite `sqlite_master`，包含普通表、FTS virtual table 和 trigger 定义，便于未来单独恢复 DB 结构。
- 人物 markdown 的关系区已为 person↔person 关系写出 Obsidian 双链，例如 `[[同事]]`；self↔person 关系仍显示为“我”。
- Obsidian 导出的人物 markdown 在同一份数据下重复导出结果保持一致；测试已覆盖同一路径重复导出后的文件内容不变。
- 新增/扩展测试：`backend/tests/test_import_export.py` 覆盖大文件 413、长文本切块、ZIP `schema.sql`、人物关系双链、Obsidian 导出幂等。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `3 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `29 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
  - `npm run test:e2e` → `7 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 6 尚未完成：文件导入仍未真正对每块调用 extraction prompt/LLM，只先落 `note_new` 审核；导入进度条、外部 LLM JSON 结构化预览与逐条确认、fuzzy match 去重、复杂 `.docx` 格式支持仍未实现。

### 2026-05-23 — Phase 4 Inbox edit and undo partial

- 后端新增 `PATCH /api/extractions/{id}`：只允许编辑 `pending` extraction 的 `payload` 和 `confidence`，用于接受前修正抽取结果。
- 后端新增 `POST /api/extractions/{id}/undo`：可撤销已接受/自动应用且由 extraction 新建的 `event_new`、`relationship_new`、`person_new`、`entity_new`、`note_new` 记录；撤销后删除对应 `target_id` 行，并将 extraction 标记为 `rejected`。
- `self_update` 等会修改既有记录状态的 extraction 尚未支持真正撤销，因为当前表结构没有保存 before-state；未在本轮为此增加审计快照字段。
- `/inbox` 已增加状态筛选、pending extraction 的 JSON payload 编辑、保存并接受、以及 `auto_applied` extraction 撤销入口。
- 新增/扩展测试：`backend/tests/test_extractions.py` 覆盖 pending 编辑后接受、auto-applied event 撤销删除目标记录；`frontend/tests/phase3-chat-settings.spec.ts` 覆盖 UI 编辑关系后接受、撤销自动应用事件。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `31 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `npm run test:e2e -- phase3-chat-settings.spec.ts` → `4 passed`
  - `npm run generate:types` → 成功生成类型
  - `npm run build` → Next.js production build 成功
  - `npm run test:e2e` → `8 passed`
- Codex Browser 插件验证未执行：`Browser is not available: iab`；已用 Playwright E2E 作为浏览器行为回归验证。
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：真实 LLM JSON extraction prompt、rapidfuzz/LLM matcher、结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 4 unknown boss seed partial

- 后端 extraction runner 已补一个最小 fallback：当会话文本提到“老板/直属上级”但当前没有匹配到已知人物时，生成 `person_new` pending extraction，payload 使用 `name="老板"`、`aliases=["我老板"]`、`bio="从聊天内容抽取，需人工确认。"`。
- 该 fallback 的 confidence 为 `0.8`，在默认 `auto_extract_threshold=0.85` 下不会自动应用，保留人工审核；接受后由既有 applier 创建 `person`。
- 新增测试覆盖 Phase 4 验收闭环的后半段：未预建人物时聊天提到“我老板” → 结束会话生成 `person_new` → 接受后 `/people?q=老板` 能查到 → 后续聊天提到“老板”时 retrieval context 命中该人物。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `32 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：上述仍是规则 fallback，不是真实 extraction_model JSON 输出；rapidfuzz matcher、结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 4 rapidfuzz matcher partial

- 后端依赖已加入 `rapidfuzz>=3.9,<4`，符合 §12 “fuzzy match 用 rapidfuzz”的技术约束；当前本地虚拟环境安装版本为 `3.14.5`。
- 新增 `app.matching.person_matches_text`：候选池包含 `person.name` 与 `person.aliases`，用 `fuzz.token_sort_ratio` 和阈值 `80` 判断；保留精确子串命中以覆盖中文姓名/别名。
- chat retrieval 与 extraction runner 已统一接入该 matcher，避免两处维护不同的人物匹配规则。
- matcher 对包含空格的多 token 候选会额外按消息 token window 比较，支持 `Alice Zhang` 与 `Zhang Alice` 这类顺序变化在句子中命中。
- 新增测试覆盖：retrieval 通过 alias token-sort 命中人物；extraction runner 通过同一 alias 匹配生成 auto-applied event，并写入正确 participant id。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_chat.py backend/tests/test_extractions.py -q` → `10 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `34 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：真实 extraction_model JSON 输出、结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 3/4 LiteLLM client and extraction JSON partial

- 后端依赖已加入 `litellm>=1.73,<2`，当前本地虚拟环境安装版本为 `1.85.1`；保留 `rapidfuzz` 依赖。
- `LLMClient.stream_chat()` 在 provider 已配置时会通过 LiteLLM `completion(..., stream=True)` 返回增量文本；未配置 provider 时仍返回原来的“未配置可用模型”本地提示。
- `LLMClient.complete_json()` 已支持 LiteLLM JSON mode：调用 `completion(..., response_format={"type": "json_object"})` 并解析 message content 为 JSON dict。
- LiteLLM 采用惰性导入：无 key/无模型调用的本地启动不会加载 LiteLLM，也避免其可选 Bedrock/SageMaker 预加载 warning 污染普通 E2E 日志。
- extraction runner 在 `extraction_model` 可用且返回 JSON 时，会优先消费模型输出；本轮先落地 `events[]` → `event_new` extraction 的映射，participants 的 `matched_id` 转为内部 `id`。模型不可用时继续走现有规则 fallback。
- 新增测试覆盖：LiteLLM stream 参数、JSON mode 参数、惰性导入、runner 消费模型 JSON 后自动应用 event。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_llm_client.py backend/tests/test_extractions.py -q` → `10 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `38 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run build` → Next.js production build 成功
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 3/4 尚未完成：尚未用真实 provider API key 做外部模型端到端调用；extraction JSON 目前只映射 `events[]`，`people/entities/relationships/self_updates` 的模型输出映射仍未完成；结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 4 extraction JSON mapping partial

- extraction runner 的模型 JSON 映射已从仅支持 `events[]` 扩展到：`people[]` 新人物、`entities[]` 新实体、`relationships[]` 新关系、`self_updates` 自我画像更新。
- `people[]` 当前只处理 `is_new=true` 且 `matched_person_id=null` 的新人物，映射为 `person_new` pending extraction；`new_facts.bio/profile_json` 会进入 payload。
- `entities[]` 映射为 `entity_new` pending extraction，保留 `type/name/bio/profile_json`。
- `relationships[]` 当前只处理 `change_kind="new"` 且 `to_id_or_name` 是已知整数 ID 的关系，映射为 `relationship_new` pending extraction；`delta.notes` 会进入 payload notes。名称型目标和 update 类关系仍不直接写入，避免生成不可接受的关系 payload。
- `self_updates.patches` 映射为 `self_update` pending extraction。
- 新增测试覆盖模型一次返回新人物、新实体、新关系、自我更新时，生成 4 条 pending extraction，并校验关键 payload 字段。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `8 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `39 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：尚未用真实 provider API key 做模型抽取端到端；人物/关系 update 类输出尚未映射；relationships 的名称型目标仍需先做 matcher/解析；结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 4 relationship target name resolution partial

- 模型 JSON 的 `relationships[].to_id_or_name` 现在支持名称/alias 字符串目标：runner 会加载现有人物候选，并复用 rapidfuzz matcher 解析到 `person.id` 后生成 `relationship_new` pending extraction。
- 名称解析支持 alias token 顺序变化，例如已有 alias `Alice Zhang`、模型输出 `Zhang Alice` 时仍能解析到对应人物。
- 无法解析到已有 person 的名称型目标仍会跳过，不生成缺少 `to_id` 的关系 payload。
- 新增测试覆盖模型返回 `to_id_or_name="Zhang Alice"` 时，能解析到 alias 为 `Alice Zhang` 的既有人物并生成关系审核项。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `9 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `40 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：尚未用真实 provider API key 做模型抽取端到端；人物/关系 update 类输出尚未映射；结构化 diff 编辑器、`self_update`/update 类 before-state 撤销仍未实现。

### 2026-05-23 — Phase 4 person_update profile_json partial

- 模型 JSON 的 `people[]` 现在支持既有人物画像更新：当 `matched_person_id` 存在且 `new_facts.profile_json` 存在时，生成 `person_update` extraction，payload 只包含 `person_id` 与新的 `profile_json`。
- applier 已支持接受 `person_update`，只更新对应 `person.profile_json`，不修改 name/aliases/bio 等其他字段。
- `person_update` 已加入自动应用候选集合，但仍要求 `auto_extract_kinds` 显式包含 `person_update` 且 confidence 达到阈值；默认设置不包含时仍进入 pending 审核。这是对 §3.3 与 §6.4 冲突的保守处理。
- 新增测试覆盖：默认设置下 `person_update` 进入 pending，人工接受后更新 `profile_json`；显式把 `person_update` 加入 `auto_extract_kinds` 后，高置信度更新会自动应用。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `10 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `41 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：尚未用真实 provider API key 做模型抽取端到端；`relationship_update` 尚未映射；`person_update`/`self_update` 等 update 类撤销仍缺 before-state；结构化 diff 编辑器仍未实现。

### 2026-05-23 — Phase 4 relationship_update partial

- 模型 JSON 的 `relationships[]` 现在支持 `change_kind="update"`：runner 会用 `from_type/from_id + to_type/to_id + relation_type` 唯一匹配既有 relationship，匹配成功后生成 `relationship_update` pending extraction。
- `relationship_update` payload 当前只保留允许更新的 `delta` 字段：`relation_type`、`role`、`strength`、`status`、`notes`、`started_at`、`ended_at`。
- applier 已支持人工接受 `relationship_update`，会更新既有 relationship 的上述字段；该 kind 不加入自动应用集合，仍强制审核。
- 如果无法唯一匹配既有 relationship，runner 会跳过该 update，不生成不可靠的审核项。
- 新增测试覆盖模型返回 `relationship_update` 后生成 pending extraction，人工接受后更新 relationship 的 `status/notes`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_extractions.py -q` → `11 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `42 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e` → `8 passed`
- Docker 验证仍缺：当前机器执行 `docker --version` 仍返回 `command not found`。
- Phase 4 尚未完成：尚未用真实 provider API key 做模型抽取端到端；`relationship_update` 和其他 update 类撤销仍缺 before-state；结构化 diff 编辑器仍未实现。

### 2026-05-23 — Phase 4 inbox diff rendering partial

- `/inbox` 的 update 类 extraction 现在使用结构化 payload 展示：`self_update`、`person_update`、`relationship_update` 会按字段显示“现状 / 新值”，原 JSON 编辑入口仍保留。
- 由于 extraction payload 还没有保存 before-state，也没有在列表页加载当前业务记录，UI 不伪造现状值；当前统一显示“现状：待比对”，只把 payload 中的新值明确展示出来。
- Phase 3 e2e 已扩展：结束会话生成 `self_update` 后，审核行必须展示 `sensitivities`、`现状`、`新值`。
- 渲染验证已做：Browser 插件可被发现，但当前没有可用 `iab` 客户端（`agent.browsers.list()` 返回空数组）；已用普通 Playwright fallback 打开 `http://127.0.0.1:45732/inbox`，确认页面非空、无框架错误 overlay、控制台无 error/warn，点击“刷新”后 diff 文案仍存在，截图位于 `/tmp/dossier-inbox-diff.png`。
- 本地验证已通过：
  - `npm run test:e2e -- phase3-chat-settings.spec.ts -g "ending chat sends pending extractions to inbox review"` → `1 passed`
- Docker 验证仍缺：当前环境没有 `docker` 命令。
- Phase 4 尚未完成：真实 provider API key 端到端抽取、update 类 before-state 撤销、真正“当前值 → 新值”的结构化编辑器仍未完成。

### 2026-05-23 — Phase 4 inbox current-value diff partial

- `/inbox` 的 update 类 diff 现在会用现有 API 读取当前业务记录，并在审核行展示真实当前值：
  - `self_update` 读取 `/api/self`，按 patch 字段显示当前 self profile 值。
  - `person_update` 读取 `/api/people/:id`，按新的 `profile_json` 字段显示当前人物 `profile_json` 中对应值。
  - `relationship_update` 读取 `/api/relationships/:id`，按 delta 字段显示当前关系值。
- 这没有改变 extraction 表结构，也没有增加 before-state 快照；因此只能展示“当前页面加载时的当前值 → payload 新值”，不能证明历史接受/撤销时的 before-state。
- Phase 3 e2e 已扩展：先保存当前 self 敏感点“被否定”，再生成 `self_update` 新值“被催”，审核行必须同时展示旧值和新值。
- 渲染验证已做：Browser 插件可被发现，但当前没有可用 `iab` 客户端（`agent.browsers.list()` 返回空数组）；已用普通 Playwright fallback 打开 `http://127.0.0.1:45742/inbox`，确认页面非空、无框架错误 overlay、控制台无 error/warn，点击“刷新”后仍显示 `现状：["被否定"]` 与 `新值：["被催"]`，截图位于 `/tmp/dossier-inbox-current-diff.png`。
- 本地验证已通过：
  - `npm run test:e2e -- phase3-chat-settings.spec.ts -g "ending chat sends pending extractions to inbox review"` → `1 passed`
  - `npm run build` → 成功
- Phase 4 尚未完成：真实 provider API key 端到端抽取、update 类 before-state 撤销、可编辑的结构化 diff 表单仍未完成。

### 2026-05-23 — Phase 4 structured diff edit partial

- `/inbox` 的 update 类 pending extraction 编辑态现在支持字段级“新值”输入：
  - `self_update` 编辑 `payload.patches[field]`。
  - `person_update` 编辑 `payload.profile_json[field]`。
  - `relationship_update` 编辑 payload 中除 `relationship_id` 外的字段。
- 字段级输入会同步更新底下保留的 `Payload JSON` textarea；用户仍可直接编辑 JSON。字段输入按 JSON 解析，失败时按字符串写入。
- Phase 3 e2e 已扩展：`self_update` 审核行点击“编辑”后，通过“新值 sensitivities”输入把 payload 改为 `["被催","临时改需求"]`，保存并接受后 `/self` 的敏感点必须显示 `被催，临时改需求`。
- 渲染验证已做：Browser 插件可被发现，但当前没有可用 `iab` 客户端（`agent.browsers.list()` 返回空数组）；已用普通 Playwright fallback 打开 `http://127.0.0.1:45752/inbox`，确认字段级输入、保存并接受、跳转 `/self` 后真实状态更新均可用，页面无框架错误 overlay，控制台无 error/warn，截图位于 `/tmp/dossier-inbox-structured-edit.png`。
- 本地验证已通过：
  - `npm run test:e2e -- phase3-chat-settings.spec.ts -g "ending chat sends pending extractions to inbox review"` → `1 passed`
  - `npm run build` → 成功
- Phase 4 尚未完成：真实 provider API key 端到端抽取、update 类 before-state 撤销、批量审核时的逐项 diff 编辑仍未完成。

### 2026-05-23 — Phase 6 LLM memory import person dedupe partial

- `POST /api/import/llm-memory` 现在会在导入 `people[]` 前加载现有人物，并复用 rapidfuzz matcher 通过 name/aliases 做匹配。
- 匹配到既有人物时，不再生成重复 `person_new`；会生成 `person_update` pending extraction，payload 为 `{person_id, profile_json}`，等待用户在 `/inbox` 审核。
- 未匹配到的人物仍按原逻辑生成 `person_new` pending extraction。
- 新增测试覆盖：已有 `张总`、alias `Alice Zhang` 时，导入 JSON 人物 `Zhang Alice` / alias `张总` 会生成 `person_update`，且不生成 `person_new`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `43 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `2 passed`
- Phase 6 尚未完成：文件导入仍未对每块调用 extraction prompt/LLM；导入进度条/批量进度、外部 LLM JSON 结构化预览与逐条确认、复杂 `.docx` 格式支持仍未完成。

### 2026-05-23 — Phase 6 file import extraction_model partial

- `/api/import/file` 现在会对每个文本块优先调用 `extraction_model`，prompt 使用聊天抽取同格式 JSON：`people/entities/events/relationships/self_updates`。
- 当模型返回可映射的结构化结果时，文件导入会直接生成对应 pending extraction；`event_new` 会标记 `source="file_import"`、`source_file`、`source_chunk_index`、`source_chunk_total`。
- 当模型不可用、未配置 provider、返回 `None` 或该块没有可映射结果时，仍保留原来的 `note_new` pending fallback，确保离线导入不丢原文。
- 新增测试覆盖 mocked `extraction_model` 场景：导入文本触发模型 prompt，生成 `event_new` + `self_update`，且不再为该块生成 `note_new`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `44 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `2 passed`
- Phase 6 尚未完成：导入进度条/批量进度、外部 LLM JSON 结构化预览与逐条确认、复杂 `.docx` 格式支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 LLM memory event participant matching partial

- `POST /api/import/llm-memory` 现在会在导入 `events[].participants` 时复用既有人物的 name/aliases matcher。
- 命中已有人物的参与者会写成 `{type:"person", id}`，让事件能直接挂到人物详情、timeline 和导出链路；未命中的参与者仍保留 `{type:"name", name}`，不丢外部 LLM 给出的名字。
- 新增测试覆盖：已有 `张总`、alias `Alice Zhang` 时，LLM memory 事件 participant `Alice Zhang` 会解析为该人物 id，同时未知 `新同事` 仍保留 name participant。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py::test_llm_memory_import_resolves_event_participants_to_existing_people -q` → `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `6 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `45 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `2 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `8 passed`
- Phase 6 尚未完成：导入进度条/批量进度、外部 LLM JSON 结构化预览与逐条确认、复杂 `.docx` 格式支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 LLM JSON preview and per-item confirmation partial

- `/import` 的 LLM 记忆 tab 现在会在 textarea 中的 JSON 可解析时显示结构化预览，覆盖 `people[]`、`entities[]`、`events[]` 和 `self`。
- 预览项默认全选；用户可以逐条取消勾选。提交时前端只把仍勾选的条目重新组装为 JSON 发送给 `POST /api/import/llm-memory`，未选条目不会生成 pending extraction。
- JSON 解析失败时会在表单内显示 `LLM JSON 无法解析`，空内容提交会提示 `请填写 LLM JSON`，全取消提交会提示 `请选择至少一条要导入的内容`。
- Phase 6 e2e 已扩展：LLM JSON 包含 2 个人物、1 个事件和 self update；取消 1 个人物和 self 后只导入 2 条，并在 `/inbox` 中确认被取消的人物和 `self_update` 不存在。
- 渲染验证已做：Browser 插件可被发现，但当前没有可用 `iab` 客户端（`agent.browsers.list()` 返回空数组）；已用普通 Playwright fallback 打开 `http://127.0.0.1:48232/import`，完成桌面端预览、取消勾选、提交、跳转 `/inbox` 验证，以及移动端预览检查。控制台无相关 error/warn，截图位于：
  - `/tmp/dossier-import-llm-preview-desktop.png`
  - `/tmp/dossier-import-llm-inbox-after-submit.png`
  - `/tmp/dossier-import-llm-preview-mobile.png`
- 本地验证已通过：
  - `npm run test:e2e -- phase6-import-export.spec.ts -g "import page creates pending"`：先在预览缺失处失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `6 passed`
  - `npm run build` → 成功
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `2 passed`
  - `npm run test:e2e` → `8 passed`
- Phase 6 尚未完成：导入进度条/批量进度、复杂 `.docx` 格式支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 import progress and batch progress partial

- `/import` 的文件导入现在支持一次选择多个 `.txt/.md/.docx` 文件；前端按文件顺序逐个调用现有 `POST /api/import/file`，不改后端 API 和数据结构。
- 文件、文本粘贴、LLM 记忆三类导入共用前端导入进度状态。导入期间页面显示 `导入进度` 状态块、当前项 `current / total`、当前文件/来源名称和进度条，并禁用当前提交按钮避免重复提交。
- 多文件导入完成后汇总显示 `已导入 N 条，处理 M 个文件`；单文件、文本粘贴、LLM 记忆仍保持原有 `已导入 N 条` 反馈。
- Phase 6 e2e 已新增批量导入进度测试：选择两个文本文件，暂停网络请求验证 `正在导入 1 / 2`、按钮禁用、`正在导入 2 / 2`、完成汇总，并在 `/inbox` 确认两条 `note_new` 均存在。
- 渲染验证已做：Browser 插件可加载，但当前没有可用 `iab` 客户端（`agent.browsers.list()` 返回空数组）；已用普通 Playwright fallback 打开 `http://127.0.0.1:48342/import`，验证桌面端双文件进度、完成后 `/inbox` 状态，以及移动端文件导入页面。控制台无相关 error/warn，截图位于：
  - `/tmp/dossier-import-file-progress-desktop.png`
  - `/tmp/dossier-import-file-progress-second.png`
  - `/tmp/dossier-import-file-progress-inbox.png`
  - `/tmp/dossier-import-file-progress-mobile.png`
- 本地验证已通过：
  - `npm run test:e2e -- phase6-import-export.spec.ts -g "file import shows batch progress"`：先因非 multiple file input 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `6 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `45 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run build` → 成功
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run test:e2e` → `9 passed`
- Phase 6 尚未完成：复杂 `.docx` 格式支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 docx inline formatting parser partial

- `.docx` 标准库解析器现在会保留 Word 段落内的 `w:br` 手动换行和 `w:tab` 制表符，不再只拼接 `w:t` 文本导致内容被压扁。
- 这仍沿用现有 `zipfile + ElementTree` 方案，不新增 `python-docx` 等依赖；因此不是完整复杂 `.docx` 支持，页眉页脚、脚注、文本框、图片 OCR 等仍不覆盖。
- 新增测试构造最小 `.docx` zip：`第一行 + w:br + 第二行 + w:tab + 标签值` 必须解析为 `第一行\n第二行\t标签值`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py::test_docx_parser_preserves_inline_breaks_and_tabs -q`：先因输出 `第一行第二行标签值` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `7 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `46 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 6 尚未完成：完整复杂 `.docx` 支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 docx comments parser partial

- `.docx` 标准库解析器现在会额外读取 `word/comments.xml` 中的批注段落文本，并接在正文、页眉、页脚、脚注、尾注之后进入导入内容。
- 这仍不解析 `.rels` 关系，不新增 `python-docx`，也不覆盖批注回复/解决状态、文本框、修订痕迹、图片 OCR 等完整复杂 Word 语义。
- 新增测试构造最小 `.docx` zip，包含正文和 `word/comments.xml`；实现前只输出正文，完成后必须输出正文与批注文本。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py::test_docx_parser_includes_comments -q`：先因只输出 `正文内容` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `9 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `48 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 6 尚未完成：完整复杂 `.docx` 支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 6 docx headers footers notes parser partial

- `.docx` 标准库解析器现在除 `word/document.xml` 正文外，也会读取 `word/header*.xml`、`word/footer*.xml`、`word/footnotes.xml` 和 `word/endnotes.xml` 中的段落文本。
- 解析顺序固定为正文 → 页眉 → 页脚 → 脚注 → 尾注；各部件继续复用现有 `w:t` / `w:br` / `w:tab` 文本提取逻辑。
- 这仍不解析 `.rels` 关系，不新增 `python-docx`，也不覆盖文本框、批注、修订痕迹、图片 OCR 等完整复杂 Word 语义。
- 新增测试构造最小 `.docx` zip，包含正文、页眉、页脚、脚注、尾注；实现前只输出正文，完成后必须输出全部五段文本。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py::test_docx_parser_includes_headers_footers_and_notes -q`：先因只输出 `正文内容` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `8 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `47 passed`
  - `.venv/bin/python -m compileall backend/app mcp` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 6 尚未完成：完整复杂 `.docx` 支持仍未完成；真实 provider API key 文件导入端到端仍未验证。

### 2026-05-23 — Phase 7 MCP stdio verification partial

- 新增 `scripts/verify-mcp-stdio.py`：使用当前 Python 作为 MCP client，经 stdio 启动 `mcp/server.py`，完成 `initialize` 后调用 `list_tools`。
- 验证脚本检查 §8.2 的 10 个 MCP tool 均已注册：`interpret_message`、`prepare_conversation`、`stale_contacts`、`recent_changes`、`get_person`、`search_people`、`get_relationship`、`get_recent_events`、`get_self_profile`、`get_timeline`。
- `mcp/README.md` 增加本地 stdio tool registration 验证命令：`python scripts/verify-mcp-stdio.py`。
- 这只证明 host-side MCP server 可以通过真实 stdio MCP 握手列出工具；仍未证明 Claude Desktop 已配置并能从真实客户端调用 `interpret_message`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_lists_registered_tools -q`：先因脚本不存在失败，完成实现后 `1 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py` → 列出 10 个预期工具
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `49 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `interpret_message`。

### 2026-05-23 — Phase 7 MCP interpret chat_model JSON partial

- `POST /api/mcp/interpret` 现在会读取 `chat_model` 设置，并尝试通过 `LLMClient.complete_json()` 生成模型版 `possible_meanings`、`recommended_outcome`、`reply_options`。
- 本地检索出的 `sender`、`literal_meaning` 和 `context_used` 仍由后端确定；模型 JSON 只允许覆盖解读和回复建议字段，避免模型覆盖已匹配的人物与上下文证据。
- 模型不可用、provider 未配置或返回 `None` 时，仍保留原来的结构化本地 fallback。
- 新增测试用 monkeypatch 模拟 `chat_model` JSON 返回，验证 `/api/mcp/interpret` 使用模型字段，同时仍保留本地匹配到的 `老板` 和 context。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py::test_mcp_interpret_uses_chat_model_json_when_available -q`：先因未调用 `LLMClient` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `3 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `51 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool interpret_message` → 返回 `MCP stdio call OK: interpret_message`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未用真实 provider API key 验证 `interpret_message` 的外部模型端到端调用。

### 2026-05-23 — Phase 7 MCP prepare chat_model JSON partial

- `POST /api/mcp/prepare` 现在会读取 `chat_model` 设置，并尝试通过 `LLMClient.complete_json()` 生成模型版 `talking_points`、`risks`、`suggested_opening`。
- 本地匹配出的 `person`、`scenario`、`desired_outcome`、`relationship_summary`、`recent_events` 仍由后端确定；模型 JSON 只允许覆盖沟通建议字段，避免模型覆盖关系和事件证据。
- 模型不可用、provider 未配置或返回 `None` 时，仍保留原来的结构化本地模板。
- 新增测试用 monkeypatch 模拟 `chat_model` JSON 返回，验证 `/api/mcp/prepare` 使用模型建议字段，同时仍保留本地匹配到的 `老板` 和最近事件。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py::test_mcp_prepare_uses_chat_model_json_when_available -q`：先因未调用 `LLMClient` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `52 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool interpret_message` → 返回 `MCP stdio call OK: interpret_message`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未用真实 provider API key 验证 `prepare_conversation` 的外部模型端到端调用。

### 2026-05-23 — Phase 7 MCP stdio prepare_conversation call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `prepare_conversation`，除原有 `interpret_message` 外，也能经 stdio 调用准备沟通工具。
- 验证脚本会为 `prepare_conversation` 传入固定参数：`with_person=老板`、`desired_outcome=推进项目`、`scenario=周会前`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，再运行验证脚本调用 `prepare_conversation`，并确认返回内容包含 `suggested_opening`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_prepare_conversation -q`：先因 `--call-tool prepare_conversation` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_interpret_message -q` → `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `6 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `53 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool prepare_conversation` → 返回 `MCP stdio call OK: prepare_conversation` 且包含 `suggested_opening`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `prepare_conversation`。

### 2026-05-23 — Phase 7 MCP stdio interpret_message call partial

- `scripts/verify-mcp-stdio.py` 增加可选参数 `--call-tool interpret_message`：在确认工具注册后，经 MCP stdio 调用 `interpret_message`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，再运行验证脚本调用 MCP tool。
- `mcp/README.md` 增加对运行中后端执行 stdio tool invocation 验证的命令示例。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端并返回 `reply_options`；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_interpret_message -q`：先因脚本不支持 `--call-tool` 失败，完成实现后 `1 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool interpret_message` → 返回 `MCP stdio call OK: interpret_message` 且包含 `reply_options`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `5 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `50 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `interpret_message`。

### 2026-05-23 — Phase 7 MCP stdio search_people call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `search_people`，可在确认工具注册后经 MCP stdio 调用人物搜索工具。
- 验证脚本会为 `search_people` 传入固定参数：`query=老板`、`limit=5`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，再运行验证脚本调用 `search_people`，并确认 stdout 包含 `MCP stdio call OK: search_people` 和 `老板`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 REST 搜索并返回人物数据；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_search_people -q`：先因 `--call-tool search_people` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_prepare_conversation backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_interpret_message -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `7 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `54 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool search_people` → 返回 `MCP stdio call OK: search_people` 且包含 `老板`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `search_people`。

### 2026-05-23 — Phase 7 MCP stdio get_person call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `get_person`，可在确认工具注册后经 MCP stdio 调用人物详情查询工具。
- 验证脚本会为 `get_person` 传入固定参数：`name_or_id=老板`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，再运行验证脚本调用 `get_person`，并确认 stdout 包含 `MCP stdio call OK: get_person` 和 `老板`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 REST 搜索并读取人物详情；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_get_person -q`：先因 `--call-tool get_person` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `8 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `55 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool get_person` → 返回 `MCP stdio call OK: get_person` 且包含 `老板`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `get_person`。

### 2026-05-23 — Phase 7 MCP stdio get_relationship call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `get_relationship`，可在确认工具注册后经 MCP stdio 调用关系查询工具。
- 验证脚本会为 `get_relationship` 传入固定参数：`person_a=老板`，即查询 self 与该人物的关系。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，再通过 `POST /api/relationships` 种入 self → 老板 的 `上下级` 关系，随后运行验证脚本调用 `get_relationship`，并确认 stdout 包含 `MCP stdio call OK: get_relationship` 和 `上下级`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 REST 搜索人物、读取人物详情并查询关系；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_get_relationship -q`：先因 `--call-tool get_relationship` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `9 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `56 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool get_relationship` → 返回 `MCP stdio call OK: get_relationship` 且包含 `上下级`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `get_relationship`。

### 2026-05-23 — Phase 7 MCP stdio get_recent_events call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `get_recent_events`，可在确认工具注册后经 MCP stdio 调用最近事件查询工具。
- 验证脚本会为 `get_recent_events` 传入固定参数：`person=老板`、`days=30`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，再通过 `POST /api/events` 种入当天的 `一起复盘项目` 事件并把参与者指向老板，随后运行验证脚本调用 `get_recent_events`，并确认 stdout 包含 `MCP stdio call OK: get_recent_events` 和 `一起复盘项目`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 REST 搜索人物、读取人物详情并按 `person_id` 查询最近事件；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_get_recent_events -q`：先因 `--call-tool get_recent_events` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `10 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `57 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool get_recent_events` → 返回 `MCP stdio call OK: get_recent_events` 且包含 `一起复盘项目`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `get_recent_events`。

### 2026-05-23 — Phase 7 MCP stdio get_self_profile call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `get_self_profile`，可在确认工具注册后经 MCP stdio 调用自我画像查询工具。
- 验证脚本会为 `get_self_profile` 传入空参数 `{}`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `PATCH /api/self` 写入 `communication_style=直接` 和 `goals=[减少误解]`，随后运行验证脚本调用 `get_self_profile`，并确认 stdout 包含 `MCP stdio call OK: get_self_profile` 和 `直接`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 `/api/self` 并返回自我画像；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_get_self_profile -q`：先因 `--call-tool get_self_profile` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `11 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `58 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool get_self_profile` → 返回 `MCP stdio call OK: get_self_profile` 且包含 `直接`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `get_self_profile`。

### 2026-05-23 — Phase 7 MCP stdio get_timeline call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `get_timeline`，可在确认工具注册后经 MCP stdio 调用时间树查询工具。
- 验证脚本会为 `get_timeline` 传入固定参数：`person=老板`、`stage=工作`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，通过 `POST /api/stages` 种入 `工作` 阶段，通过 `POST /api/people/{id}/stages` 种入 `直属上级` 阶段归属，再通过 `POST /api/events` 种入 `周会被提醒进度` 事件，随后运行验证脚本调用 `get_timeline`，并确认 stdout 包含 `MCP stdio call OK: get_timeline`、`直属上级` 和 `周会被提醒进度`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 `/api/stages` 和 `/api/timeline?stage_id=...`，并返回过滤后的时间树数据；至此 §8.2 的 6 个数据级 tool 均已有本机 stdio 调用级验证。它仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_get_timeline -q`：先因 `--call-tool get_timeline` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `12 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `59 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool get_timeline` → 返回 `MCP stdio call OK: get_timeline` 且包含 `直属上级` 和 `周会被提醒进度`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `get_timeline`。

### 2026-05-23 — Phase 7 MCP stdio stale_contacts call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `stale_contacts`，可在确认工具注册后经 MCP stdio 调用久未联系提醒工具。
- 验证脚本会为 `stale_contacts` 传入固定参数：`days=30`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入没有事件记录的 `旧同事`，随后运行验证脚本调用 `stale_contacts`，并确认 stdout 包含 `MCP stdio call OK: stale_contacts` 和 `旧同事`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 `/api/mcp/stale-contacts?days=30` 并返回久未联系人物；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_stale_contacts -q`：先因 `--call-tool stale_contacts` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `13 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `60 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool stale_contacts` → 返回 `MCP stdio call OK: stale_contacts` 且包含 `旧同事`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `stale_contacts`。

### 2026-05-23 — Phase 7 MCP stdio recent_changes call partial

- `scripts/verify-mcp-stdio.py` 的 `--call-tool` 现在支持 `recent_changes`，可在确认工具注册后经 MCP stdio 调用最近变化查询工具。
- 验证脚本会为 `recent_changes` 传入固定参数：`person=老板`、`days=7`。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，先通过 `POST /api/people` 种入 `老板` / `张总`，再通过 `POST /api/events` 种入当天的 `合同范围变更` 事件并把参与者指向老板，随后运行验证脚本调用 `recent_changes`，并确认 stdout 包含 `MCP stdio call OK: recent_changes` 和 `合同范围变更`。
- 这证明 host-side MCP server 可以通过真实 stdio MCP `call_tool` 命中本地后端 `/api/mcp/recent-changes?days=7&person=老板` 并返回最近变化；至此 §8.2 的 10 个 MCP tool 均已有本机 stdio 调用级验证。它仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_recent_changes -q`：先因 `--call-tool recent_changes` 不是合法 choice 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `14 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `61 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-tool recent_changes` → 返回 `MCP stdio call OK: recent_changes` 且包含 `合同范围变更`
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用 `recent_changes`。

### 2026-05-23 — Phase 7 MCP stdio call-all smoke partial

- `scripts/verify-mcp-stdio.py` 新增 `--call-all`：在原有 MCP stdio `list_tools` 注册检查通过后，按 `TOOL_ARGUMENTS` 顺序逐个调用 §8.2 的 10 个 tool。
- 新增集成测试会创建临时 SQLite DB、跑 Alembic migration、在 20000-60000 范围内选择随机本地端口启动 FastAPI 后端，种入自我画像、`老板`、`旧同事`、self → 老板关系、`工作` 阶段、阶段归属和当天 `合同范围变更` 事件，随后运行 `--call-all`。
- 测试确认 stdout 包含 10 个 `MCP stdio call OK: ...` 标记，并包含 `合同范围变更`、`旧同事`、`直属上级` 等数据标记；独立 smoke 额外确认 `老板`、`直接`、`reply_options`、`suggested_opening`。
- 这证明 host-side MCP server 有一条一键本机 stdio smoke 路径，可调用全部 10 个 MCP tool 并命中本地后端；仍不是 Claude Desktop 客户端内的真实端到端验收。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_mcp_stdio_verify_script_can_call_all_tools -q`：先因 `--call-all` 不是合法参数失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `15 passed`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_intent.py -q` → `4 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `62 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --api-url <local test backend> --call-all` → 全部 10 个 `MCP stdio call OK: ...` 标记均出现，且包含预期数据标记
  - `npm run test:e2e -- phase6-import-export.spec.ts` → `3 passed`
  - `npm run build` → 成功
  - `npm run test:e2e` → `9 passed`
- Phase 7 尚未完成/未证明：尚未在真实 Claude Desktop 配置里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用任一 tool；尚未用真实 provider API key 验证外部模型路径；本机仍未证明 Docker Compose。

### 2026-05-23 — Phase 7 MCP install Python pin partial

- `scripts/install-mcp.sh` 不再依赖 shell 里存在 `python` 命令；安装 MCP 依赖时优先使用项目 `.venv/bin/python`，否则回退到 `python3` / `python`，找不到解释器时明确报错。
- 安装脚本打印给 Claude Desktop 的 JSON 现在使用同一个 Python 解释器作为 `command`，避免依赖安装到一个环境、Claude Desktop 启动另一个环境导致找不到 `mcp` 包。
- `mcp/README.md` 的本地验证命令和 Claude Desktop 示例同步改为 `.venv/bin/python` 口径。
- 新增测试在临时项目里只提供假的 `.venv/bin/python`，确认脚本用它执行 `-m pip install -r mcp/requirements.txt`，并确认输出 JSON 的 `command` 与 `args` 是可复制的绝对路径。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_install_mcp_uses_project_venv_python_for_install_and_config -q`：先因脚本调用不存在的 `python` 失败，完成实现后 `1 passed`
  - `bash -n scripts/install-mcp.sh` → 成功
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `16 passed`
  - `scripts/install-mcp.sh` → 依赖已在 `.venv` 中满足，并打印 `"command": "/Users/rzhang15/Documents/Dossier/.venv/bin/python"`
  - `.venv/bin/python -m pytest backend/tests -q` → `63 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py` → 列出 10 个预期 MCP tool
- Phase 7 尚未完成/未证明：尚未把该 JSON 写入真实 Claude Desktop 配置；尚未在 Claude Desktop 里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用任一 tool；本机仍未证明 Docker Compose。

### 2026-05-24 — Phase 7 MCP Claude config merge partial

- 只读审计确认本机存在 `/Applications/Claude.app`，Claude Desktop 正在运行，真实配置位于 `~/Library/Application Support/Claude/claude_desktop_config.json`。
- 当前真实配置文件已有 `preferences`，但没有 `mcpServers`；因此不能建议用户用脚本打印的完整 JSON 直接覆盖配置，否则会丢掉现有偏好。
- `scripts/install-mcp.sh` 新增 `--write-claude-config`：安装依赖后会合并写入 `mcpServers.dossier`，保留已有顶层配置，并在覆盖前写出 `claude_desktop_config.json.bak`。
- 合并写入使用项目 `.venv/bin/python` 执行 Python JSON 读写，所有文件读写显式使用 UTF-8。
- `mcp/README.md` 补充 `scripts/install-mcp.sh --write-claude-config` 用法。
- 新增测试在临时 HOME 中预置只有 `preferences` 的 Claude 配置，运行 `--write-claude-config` 后确认 `preferences` 保留、`mcpServers.dossier` 写入、备份文件存在且内容是原配置。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_install_mcp_can_merge_dossier_into_existing_claude_config -q`：先因配置没有写入 `mcpServers` 失败，完成实现后 `1 passed`
  - `bash -n scripts/install-mcp.sh` → 成功
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q` → `17 passed`
  - `HOME=<temp> scripts/install-mcp.sh --write-claude-config` → 临时 Claude 配置保留 `preferences` 并新增 `mcpServers.dossier`
  - `.venv/bin/python -m pytest backend/tests -q` → `64 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
  - `.venv/bin/python scripts/verify-mcp-stdio.py` → 列出 10 个预期 MCP tool
- Phase 7 尚未完成/未证明：尚未对真实 Claude Desktop 配置执行 `--write-claude-config`；尚未重启 Claude Desktop；尚未在 Claude Desktop 里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用任一 tool；本机仍未证明 Docker Compose。

### 2026-05-24 — Phase 7 real Claude config write partial

- 已对真实 Claude Desktop 配置执行 `scripts/install-mcp.sh --write-claude-config`。
- 写入目标：`~/Library/Application Support/Claude/claude_desktop_config.json`。
- 自动备份：`~/Library/Application Support/Claude/claude_desktop_config.json.bak`；备份文件确认不含 `mcpServers`，可用于回退写入前状态。
- 写入后真实配置仍保留原 `preferences`，并新增：
  - `mcpServers.dossier.command=/Users/rzhang15/Documents/Dossier/.venv/bin/python`
  - `mcpServers.dossier.args=["/Users/rzhang15/Documents/Dossier/mcp/server.py"]`
  - `mcpServers.dossier.env.DOSSIER_API_URL=http://localhost:8000`
- 这证明 Phase 7 的 Claude Desktop 配置文件已经真实落盘，且没有覆盖掉既有偏好；仍未证明 Claude Desktop 重启后已加载该 server。
- 本地验证已通过：
  - `.venv/bin/python - <<'PY' ...` 读取真实 Claude 配置 → `preferences_preserved=True`、`backup_has_mcpServers=False`，并确认 dossier command/args/env 为预期值
  - `.venv/bin/python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json` → JSON 可解析
  - `.venv/bin/python scripts/verify-mcp-stdio.py` → 列出 10 个预期 MCP tool
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py::test_install_mcp_uses_project_venv_python_for_install_and_config backend/tests/test_mcp_tools.py::test_install_mcp_can_merge_dossier_into_existing_claude_config -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests -q` → `64 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `.venv/bin/python -m pip check` → `No broken requirements found.`
- Phase 7 尚未完成/未证明：Claude Desktop 仍需重启以加载新配置；尚未在 Claude Desktop 里看到 dossier MCP server；尚未从 Claude Desktop 端到端调用任一 tool；本机仍未证明 Docker Compose。

### 2026-05-24 — Phase 7 Claude Desktop MCP E2E verified

- 已重启 Claude Desktop，并确认真实配置加载到 Claude 进程下的 Dossier MCP server：
  - Claude 主进程：`/Applications/Claude.app/Contents/MacOS/Claude`
  - MCP wrapper：`/Applications/Claude.app/Contents/Helpers/disclaimer /Users/rzhang15/Documents/Dossier/.venv/bin/python /Users/rzhang15/Documents/Dossier/mcp/server.py`
  - MCP Python 子进程：`/Users/rzhang15/Documents/Dossier/.venv/bin/python /Users/rzhang15/Documents/Dossier/mcp/server.py`
- `~/Library/Logs/Claude/mcp-server-dossier.log` 记录到真实 Claude Desktop 客户端握手：
  - `initialize` → server 返回 `serverInfo.name="Dossier"`、`version="1.27.1"`
  - `notifications/initialized`
  - `tools/list` / `prompts/list` / `resources/list`
  - `tools/list` 响应包含 `interpret_message` 等 Dossier MCP tools。
- 首次重启曾出现一次 `initialize` 60 秒超时；用相同 payload 直连 `mcp/server.py`、以及通过 Claude 的 `disclaimer` wrapper 启动均可立即返回 initialize result。第二次重新打开 Claude Desktop 后完成握手并稳定列出 tools，因此当前结论是首次加载时的客户端侧瞬态问题，不是 server 启动或 stdio 协议实现缺陷。
- 在 Claude Desktop Chat 模式创建真实会话 `Dossier MCP 消息解析测试`，发送虚构 smoke prompt：`请调用 Dossier MCP 的 interpret_message 工具分析这条虚构测试消息：“老板说今天辛苦了”。这是本地 MCP smoke test。`
- Claude 请求调用 `dossier` 的 `Interpret message`；本次只点选一次性授权 `Allow once`，没有授予永久 `Always allow`。
- Claude MCP 日志记录到真实端到端调用：
  - `tools/call` name=`interpret_message`
  - arguments 包含 `message="老板说今天辛苦了"`、`from_hint="老板"`、`context_hint="本地 MCP smoke test，虚构测试消息"`
  - MCP server 发起 `POST http://localhost:8000/api/mcp/interpret`，后端返回 `HTTP/1.1 200 OK`
  - server 返回 `isError=false`，`structuredContent` 包含 `literal_meaning`、`possible_meanings`、`recommended_outcome`、`reply_options`、`context_used`
- Claude UI 随后展示 `Smoke test 通过，dossier:interpret_message 返回了结构化结果。`
- 这证明：真实 Claude Desktop 配置、Claude MCP host、Dossier stdio server、本地 FastAPI 后端、`interpret_message` 工具调用链已经完成端到端验证。
- 仍未证明/不在本次闭环内：真实外部 provider API key 路径；Docker Compose 本机运行。

### 2026-05-25 — Phase 7 Claude Desktop MCP E2E reverified

- 重新执行 `scripts/install-mcp.sh --write-claude-config` 写入真实 Claude Desktop 配置，并重启 Claude Desktop。
- 将 MCP 默认后端地址从 `http://localhost:8000` 收紧为 `http://127.0.0.1:8000`：
  - 原因：本机验收中 `curl http://localhost:8000/health` 可通，但 Python/httpx 经 MCP tool 调用 `localhost` 时出现 `All connection attempts failed`；改用 IPv4 loopback 后 stdio 与真实 Claude Desktop 均正常。
  - 同步范围：`scripts/install-mcp.sh`、`scripts/verify-mcp-stdio.py`、`mcp/tools/client.py`、`mcp/README.md`、`backend/tests/test_mcp_tools.py`。
- 重启后确认 Claude Desktop 已加载 Dossier MCP server：
  - Claude 主进程：`/Applications/Claude.app/Contents/MacOS/Claude`
  - MCP wrapper：`/Applications/Claude.app/Contents/Helpers/disclaimer /Users/rzhang15/Documents/Dossier/.venv/bin/python /Users/rzhang15/Documents/Dossier/mcp/server.py`
  - MCP Python 子进程：`/Users/rzhang15/Documents/Dossier/.venv/bin/python /Users/rzhang15/Documents/Dossier/mcp/server.py`
- 真实 Claude Desktop Chat 会话 `Dossier MCP smoke test search` 中发送虚构 smoke prompt，要求调用 `search_people` 搜索 `__dossier_smoke_no_match_20260525__`。
- Claude 端只点选一次性授权 `Allow once`，没有授予永久 `Always allow`。
- Claude MCP 日志记录到真实端到端调用：
  - `tools/call` name=`search_people`
  - arguments 包含 `query="__dossier_smoke_no_match_20260525__"`
  - MCP server 发起 `GET http://127.0.0.1:8000/api/search?q=__dossier_smoke_no_match_20260525__&type=people`，后端返回 `HTTP/1.1 200 OK`
  - server 返回 `isError=false`，`structuredContent={"result":[]}`
- Claude UI 展示 `Smoke test 通过`，并显示工具 `dossier:search_people`、query 和空数组结果。
- 本地验证已通过：
  - `curl -fsS http://localhost:8000/health` → `{"ok":true}`
  - `.venv/bin/python -m pytest backend/tests/test_mcp_tools.py -q`（提升权限，因沙箱内高位端口 bind 被拒绝）→ `17 passed`
  - `.venv/bin/python scripts/verify-mcp-stdio.py --call-all`（提升权限，因沙箱内 Python/httpx 访问本机端口被拒绝）→ 10 个 MCP tool 均 `isError=False`，并命中 `http://127.0.0.1:8000`
  - `.venv/bin/python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json` → JSON 可解析，`mcpServers.dossier.env.DOSSIER_API_URL=http://127.0.0.1:8000`
- 仍未证明/不在本次闭环内：Docker Compose 本机运行；真实外部 provider API key 路径。

### 2026-05-25 — Claude Desktop MCP load recheck

- 在用户明确授权后，重新执行 `scripts/install-mcp.sh --write-claude-config` 写入真实 Claude Desktop 配置。
- 写入后配置 JSON 可解析，且 `mcpServers.dossier` 指向：
  - `command=/Users/rzhang15/Documents/Dossier/.venv/bin/python`
  - `args=["/Users/rzhang15/Documents/Dossier/mcp/server.py"]`
  - `env.DOSSIER_API_URL=http://127.0.0.1:8000`
- 通过 bundle id `com.anthropic.claudefordesktop` 重启 Claude Desktop 后，进程检查确认：
  - Claude 主进程正在运行；
  - Claude `disclaimer` wrapper 已拉起；
  - Dossier MCP Python 子进程已拉起。
- `~/Library/Logs/Claude/mcp-server-dossier.log` 记录到本次重启后的真实 Claude Desktop MCP 握手：`initialize`、`notifications/initialized`、`tools/list`、`prompts/list`、`resources/list` 均完成，`tools/list` 返回 Dossier tools。
- 本机提升权限 stdio smoke 通过：`.venv/bin/python scripts/verify-mcp-stdio.py --call-all` 调用 10 个 MCP tool，均 `isError=False`，并命中 `http://127.0.0.1:8000`。
- 本次未完成 Claude Desktop GUI 内 prompt tool-call：Claude 进程存在且 MCP 已加载，但当前会话中 macOS Accessibility / Computer Use 无法取得 Claude key window；`Show Main Window`、`New Conversation` 菜单项和 `claude://` URL scheme 均未暴露可交互窗口。因此本次验收只证明真实 Claude Desktop 已加载 MCP server，未新增一次 GUI 内 tool-call 证据。
- Obsidian 镜像未同步：当前授权仅覆盖 Claude Desktop 配置写入与重启，未覆盖 `/Users/rzhang15/Documents/Obsidian Vault/01-项目/Dossier/SPEC.md` 写入。

### 2026-05-25 — Phase 8 ZIP export restore partial

- `GET /api/export/zip` 现在除 `dossier.json`、`schema.sql`、人物 Markdown 外，会加入完整数据根目录快照：
  - SQLite 数据库按 `data/dossier.db` 归档；
  - `uploads/`、`imports/`、以及同一数据根下的其他文件会以 `data/<relative path>` 归档；
  - 导出前会尝试执行 `PRAGMA wal_checkpoint(FULL)`，降低 SQLite 主库文件缺失最新 WAL 内容的恢复风险。
- ZIP 现在包含 `config.redacted.json`：
  - 记录 `DATABASE_URL`、`UPLOAD_DIR`、`EXPORT_DIR`、provider API key、`OLLAMA_BASE_URL` 和 DB 中的 app settings；
  - key 名包含 `api_key`、`token`、`secret`、`password` 的值会脱敏为 `***REDACTED***`。
- 新增恢复级测试：创建人物与上传目录文件后导出 ZIP，解压 `data/dossier.db` 到新目录并用 SQLite 查询确认人物数据一致，同时确认 `config.redacted.json` 不泄露 `OPENAI_API_KEY` 原文。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py::test_export_zip_contains_restorable_data_dir_and_redacted_config -q`：先因缺少 `data/dossier.db` 失败，完成实现后 `1 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `11 passed`
- Phase 8 尚未完成/未证明：README 3 步 quickstart、截图、person/entity name sqlite index、retrieval LRU cache、02:00 cron 备份验证仍未在当前仓库完成；Docker Compose 本机运行仍未证明。

### 2026-05-25 — Phase 8 performance polish partial

- 新增 Alembic migration `20260525_0002_name_indexes`：
  - `ix_person_name` on `person(name)`
  - `ix_entity_name` on `entity(name)`
- SQLAlchemy model 同步声明 `Person.name` 和 `Entity.name` 为 indexed column。
- 已对真实本地 `data/dossier.db` 执行 `alembic upgrade head`，确认 `PRAGMA index_list('person')` / `PRAGMA index_list('entity')` 可看到 `ix_person_name` 和 `ix_entity_name`。
- `retrieve_context` 增加进程内 LRU cache：
  - cache 上限 128 条；
  - 仅对带 `session_id` 的 chat 检索启用；
  - key 为 `(database_url, session_id, matched_person_ids)`，因此同一 chat session 中再次提到同一批人物时复用上下文；
  - MCP intent 未传 session_id，仍走即时检索，避免跨工具调用复用过期上下文。
- `POST /api/chat/sessions/{session_id}/messages` 现在把 `session_id` 传入 `stream_chat_response` / `retrieve_context`，使 chat 会话内缓存生效。
- 新增测试：
  - migration 后 `PRAGMA index_list` 必须包含两个 name index；
  - 同一 session 再次检索同一人物时，第二次 SQL 查询数不超过 1。
- 顺手修复一个日期漂移测试：`seed_boss_context` 不再固定 `2026-05-23`，改用 `date.today()`，否则 `stale_contacts(days=1)` 会随当前日期变成错误断言。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_schema.py::test_initial_migration_creates_schema_and_default_settings backend/tests/test_chat.py::test_retrieval_caches_same_session_person_context -q`：先因缺少 index 和 `session_id` 参数失败，完成实现后 `2 passed`
  - `.venv/bin/python -m pytest backend/tests/test_schema.py backend/tests/test_chat.py -q` → `6 passed`
  - `.venv/bin/python -m pytest backend/tests -q`（提升权限，因 MCP stdio 测试需绑定本地高位端口）→ `72 passed`
  - `.venv/bin/python -m compileall backend/app backend/alembic` → 成功
- Phase 8 尚未完成/未证明：README 3 步 quickstart、截图、02:00 cron 备份验证仍未在当前仓库完成；Docker Compose 本机运行仍未证明。

### 2026-05-25 — Phase 8 backup script partial

- `scripts/backup.sh` 现在支持 dogfood 备份路径：
  - 默认数据目录：仓库内 `data/`；
  - 默认备份目录：`~/Library/Application Support/Dossier/backups`；
  - 可用 `DOSSIER_DATA_DIR` 和 `DOSSIER_BACKUP_DIR` 覆盖；
  - 生成 `dossier-backup-YYYYMMDD_HHMMSS.tar.gz`；
  - 每次运行后只保留最近 7 个 `dossier-backup-*.tar.gz`。
- 新增 `scripts/install-backup-cron.sh`：
  - `--dry-run` 输出实际 cron 行；
  - cron 时间为每天 `02:00`；
  - cron 命令调用 `/bin/bash <repo>/scripts/backup.sh`，日志追加到 `<repo>/backup.log`；
  - 非 dry-run 会替换 crontab 中旧的 `scripts/backup.sh` 行并安装新行。
- 新增测试 `backend/tests/test_backup_scripts.py`：
  - 用临时 `DOSSIER_DATA_DIR` / `DOSSIER_BACKUP_DIR` 验证备份 tar 包包含 `data/dossier.db`，且旧备份被裁剪到 7 个；
  - 验证 cron dry-run 输出包含 `0 2 * * *` 和 `scripts/backup.sh`。
- 本地验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_backup_scripts.py -q`：先因不裁剪和缺少 cron 脚本失败，完成实现后 `2 passed`
  - `bash -n scripts/backup.sh` → 成功
  - `bash -n scripts/install-backup-cron.sh` → 成功
  - `scripts/install-backup-cron.sh --dry-run` → 输出 `0 2 * * * ... scripts/backup.sh ...`
  - 临时目录 smoke：`DOSSIER_DATA_DIR=<tmp>/data DOSSIER_BACKUP_DIR=<tmp>/backups /bin/bash scripts/backup.sh` → 生成 tar.gz 成功
- 真实 crontab 尚未安装；这是仓库外持久系统改动，需要用户明确批准后执行。
- Phase 8 尚未完成/未证明：README 3 步 quickstart、截图、真实 02:00 crontab 安装/验证仍未完成；Docker Compose 本机运行仍未证明。

### 2026-05-24 — Development paused for architecture review

- 当前开发计划暂停，不继续按原 Phase 路线推进；后续可能需要较大产品/架构调整，正在与 Claude 另行沟通方向。
- 已明确暴露的核心问题：现有 `JSON extraction -> DB schema -> /inbox accept` 路径过硬，模型输出稍有自然语言或格式漂移就会造成导入/审核体验中断。例如事件日期输出为 `近期` 时，`event.occurred_at` 只能接受 ISO 日期，接受审核会失败。
- 已做过的 `repair` API / “修正格式”按钮属于战术补丁，只能缓解单条 payload 格式错误；它不能从根上解决模型能力不稳定、schema 约束不清、导入材料丢失感和用户需要反复修 JSON 的体验问题。
- 已开始验证的替代方向：导入内容先落明文 Markdown 源文件，再把 SQLite/JSON extraction 作为可重建索引或结构化建议，而不是唯一事实来源。该方向需要重新设计事实源、索引重建、审核语义和导出/同步边界，不能在现有实现上继续零散堆补丁。
- `ubuntu-home` 上此前的 Dossier Docker 部署已按要求全部删除，包括容器、镜像、网络、`/home/rzhang15/dossier` 目录和远端数据；当前没有远端运行实例。
- 本地仓库仍保留当前实验性实现状态，作为后续评估材料；在新架构确认前，不应继续新增功能或扩大部署。

### 2026-05-25 — Phase 8 docs and verification recheck

- 用户恢复 Phase 8 目标后，继续补齐 Import / Export / 打磨验收，而不是沿用上一条暂停状态。
- README quickstart 已收敛为 3 步：
  - `git clone https://github.com/UntR/TencentDB-Agent-Memory.git dossier`
  - `cd dossier && npm install`
  - `npm start`
- README troubleshooting 已覆盖：路径校验失败、API key 不识别、MCP 装不上。
- 新增真实页面截图：
  - `docs/screenshots/chat.png`
  - `docs/screenshots/inbox.png`
  - `docs/screenshots/timeline.png`
  - 三张均由当前本地 `http://127.0.0.1:3000` 页面生成，尺寸为 `1440 x 1000` PNG。
- 新增直接验收测试 `test_import_docx_file_creates_pending_extraction`：构造 `.docx` 后经 `POST /api/import/file` 上传，并确认 `/api/extractions` 中出现包含文档内容的 pending `note_new`。
- 当前验证已通过：
  - `.venv/bin/python -m pytest backend/tests/test_quickstart_docs.py -q` → `2 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py -q` → `12 passed`
  - `.venv/bin/python -m pytest backend/tests/test_import_export.py backend/tests/test_backup_scripts.py backend/tests/test_schema.py backend/tests/test_chat.py backend/tests/test_quickstart_docs.py -q` → `21 passed`
  - `.venv/bin/python -m pytest backend/tests -q`（提升权限，因 MCP/stdout 集成测试需本地端口）→ `77 passed`
  - `.venv/bin/python -m compileall backend/app mcp scripts` → 成功
  - `npm install` → 成功，`postinstall` 完成
  - `npm run build` → 成功
  - `npm --prefix frontend run test:e2e`（提升权限，因 Chromium 启动需 macOS Mach port 权限）→ `11 passed`
  - `bash -n scripts/backup.sh && bash -n scripts/install-backup-cron.sh && scripts/install-backup-cron.sh --dry-run` → 输出每天 `02:00` 的 `scripts/backup.sh` cron 行
  - `sqlite3 data/dossier.db "PRAGMA index_list('person'); PRAGMA index_list('entity');"` → 可见 `ix_person_name` 和 `ix_entity_name`
- 当前仍未完成/未证明：
  - 真实 crontab 尚未安装；`crontab -l` 返回 `no crontab for rzhang15`。执行 `scripts/install-backup-cron.sh` 的提升权限请求被权限审查拒绝，原因是缺少对“写入实际用户 crontab”的单独明确授权。
  - Docker Compose 本机运行仍未证明；当前环境 `command -v docker` 没有返回 docker 可执行文件。
  - Obsidian 镜像 SPEC 未同步；当前授权仍未覆盖 `/Users/rzhang15/Documents/Obsidian Vault/01-项目/Dossier/SPEC.md` 写入。
