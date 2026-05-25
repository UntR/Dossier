# AGENTS.md

本文件是 Dossier 仓库的项目级约束。进入本仓库工作时先读这里，再读 `SPEC.md`。

## 1. 事实来源

- `SPEC.md` 是实现蓝本和当前仓库内的事实来源。
- Obsidian 镜像文档位于 `/Users/rzhang15/Documents/Obsidian Vault/01-项目/Dossier/SPEC.md`；修改 durable 产品事实、阶段状态、验证缺口时，应同步更新两边。如果当前环境不能写 Obsidian 路径，明确报告这个缺口。
- 不要另起一份 competing spec。需求变化回写到 `SPEC.md`，不要散落在临时说明里。
- `README.md` 只放 quickstart 和面向用户的简介；实现细节、验收状态和边界放在 `SPEC.md`。

## 2. 产品边界

- Dossier 是自用、单机、local-first 产品，不做多租户、SaaS 鉴权、云同步、协作、付费或移动端 App。
- 所有用户数据默认落本地 SQLite / 本地文件；不要引入远端存储或遥测。
- UI、prompt、默认数据中文优先；代码、日志、测试名、commit message 用英文。
- Docker Compose 是 web 端默认启动方式；MCP bridge 是宿主机 Python 进程，通过 HTTP 调 backend，不直接读写 SQLite。
- 模型通过 LiteLLM 抽象；chat model 和 extraction model 是两条独立路径，不要把抽取悄悄改成 chat model。

## 3. 修改原则

- 手术式修改：只碰当前请求需要的文件，不顺手重构相邻代码。
- 简单优先：不为一次性逻辑加抽象，不做未要求的可配置性。
- 产品功能、技术选型、新依赖、架构变更先说明理由并等确认。
- 涉及数据结构、删除代码、跨多文件重构，先汇报范围和风险再动手。
- 发现死代码或旧缺口可以指出；未经要求不要主动删除。
- 文件读写显式使用 UTF-8。

## 4. 实现约定

- Backend：FastAPI + SQLAlchemy async + Alembic + SQLite。
- Frontend：Next.js 15 App Router + TypeScript + Tailwind。
- MCP：官方 Python SDK；tool 实现必须经 HTTP API 调 backend。
- 数据库并发保持 SQLite WAL 思路；不要绕过现有 session / migration 层。
- 前端类型从 OpenAPI 生成，避免手抄 API 类型。
- 本地 web 开发端口使用 20000-60000 的随机端口；不要默认占用 3000、5173、8000、8080，除非 SPEC 或现有脚本明确要求。

## 5. 验证

按修改范围选择最小但足够的验证。常用命令：

```bash
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m compileall backend/app mcp scripts
cd frontend && npm run build
cd frontend && npm run test:e2e
.venv/bin/python scripts/verify-mcp-stdio.py
```

- 改 backend API / extraction / MCP：至少跑相关 pytest；跨模块改动跑 `backend/tests` 全量。
- 改 Python import 或脚本：跑 `compileall`。
- 改 frontend：跑 `npm run build`；关键用户流改动跑对应 Playwright。
- 改 MCP Claude 配置或 tool：用 `scripts/verify-mcp-stdio.py` 做 host-side 验证；真实 Claude Desktop 验证需要明确记录后端是否在跑、是否只做一次性授权。
- Docker Compose 和真实 provider API key 如果当前机器不可用，不能宣称完成，只能记录为验证缺口。

## 6. 协作方式

- 多种解释并存时全部列出，不要默默选择。
- 成功标准模糊时先澄清；能从 `SPEC.md` 明确推出的，直接执行。
- 多步任务先写 `步骤 -> 验证方式`。
- 写完一个有意义单元就停下来给用户 review，不连续推进多个独立任务。
- 允许并鼓励反驳：如果请求会增加复杂度、违背 local-first、或和 SPEC 冲突，直接指出并给更简单方案。

## 7. Git

- 不要 revert 用户或其他 agent 的改动。
- 提交前确认变更范围只包含本次任务。
- commit message 必须说明原因或影响，不只写动作；示例：`fix: prevent MCP config from overwriting Claude preferences`。
