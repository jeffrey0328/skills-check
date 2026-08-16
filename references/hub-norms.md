# Hub norms & file index

**读法:** § File index when locating assets; § Must / Must not when unsure; § Definition of Done before closing a create/update.

| Need | Section |
|------|---------|
| Where is X? | § File index |
| Standing rules | § Must / § Must not |
| Finish checklist | § Definition of Done |
| Who references a file before I edit it? | `references/cross-reference.md` |

## File index

| Path | Audience | When to read |
|------|----------|--------------|
| `SKILL.md` | Agent | Thin hub; pasted on `/` or `@` |
| `README.md` | Human | English README：简介 → `## Install`（英文 Agent 提示词：仓库 + Steps）→ `## Features` → `## How to use` → `## Common changes`；链到 `README.zh.md` |
| `README.zh.md` | Human | Chinese README：简介 → `## 安装`（中文 Agent 提示词：仓库 + 步骤）→ 功能介绍 → 怎么用 → 常见改动；链到 `README.md` |
| `review-intro.md` | Human | Feishu Review 简介（中文纯文本，无 Markdown 标记） |
| `review-body.md` | Human | 能做什么 / 执行步骤（中文；执行步骤在页面最下；每项有 `###`） |
| `review-usage.md` | Human | 使用方法（一句话）/ 功能（只挂命令、参数、脚本、工具） |
| `references/hub-norms.md` | Agent | This file |
| `references/cross-reference.md` | Agent | 关联记录 |
| `references/open-review.md` | Agent | Preflight + open overview vs single page |
| `references/adopt-review.md` | Agent | Retrofit a regular skill |
| `references/sync-on-update.md` | Agent | Sync after a skill update |
| `references/skill-authoring.md` | Agent | Create/update any Agent Skill (shape, layers, companions) |
| `tag-vocab.txt` | Human / Review | 全套 skill 共用的标签词表（总览编辑标签时的候选，一行一个） |
| `scripts/skills-check-viewer.py` | Agent / local | Local HTTP Review viewer（含 `POST /api/tag` 写 `tag.txt`） |
| `scripts/open-review.ps1` | Agent | This skill’s `-review` |
| `examples/adopt-checklist.md` | Both | Adopt checklist |

**Human entry:** `README.md` + `README.zh.md`（互相入口；简介 → 安装提示词 → 功能介绍 → 怎么用 → 常见改动 → 其他；英文页英文提示词、中文页中文提示词；内容部分只有这三节，不写 `何时` / `怎么调用` / 文件角色 / 目录清单表；**required**，缺一份或入口/顺序不对 = 缺件）+ Feishu Review：`review-intro.md` / `review-body.md` / `review-usage.md`。全文不要用具体 Agent 应用名，写成当前 Agent / Agent。细节：`skill-authoring.md` § README / § Install prompt / § Agent-app names。

## Must

- Creating or editing any skill reads `skill-authoring.md` first.
- Before every Review open, adapt every skill under the current app’s default skills path — `open-review.md` § Preflight.
- Bare `/skills-check` then opens the overview; `/<skill> -review` opens that skill’s page — `open-review.md`.
- This skill is resident: other skills created or updated this turn follow `sync-on-update.md` § Resident.
- Adopt / retrofit follows `adopt-review.md`.
- **Check the 关联记录 before editing:** Read `cross-reference.md` first; update it after any cross-reference change.
- Keep this hub thin; long runbooks stay in `references/`.
- Default open to the agent’s built-in browser (`open-review.md` § Browser).
- Companion sync and Must-not pairing follow `skill-authoring.md`（README 两份 + Review 三页 + 不用具体 Agent 应用名）。

## Must not

- Stuff the adopt/sync playbooks into `SKILL.md`. *(← Must: keep this hub thin)*
- Open overview via `/jeffrey-workflow-skill -reviewall`. *(← Must: overview is `/skills-check`)*
- Default-open Review in the external browser. *(← Must: built-in browser)*

## Definition of Done

- [ ] Create/update skill work read `skill-authoring.md` first.
- [ ] Review open ran § Preflight; unadapted skills were fixed before the viewer started.
- [ ] Intent routed to one of: `skill-authoring.md` / `open-review.md` / `adopt-review.md` / `sync-on-update.md`.
- [ ] 关联记录 checked + updated when files or `##` headings changed.
- [ ] Companions aligned (`README.md` / `README.zh.md` / `review-*` / `tag.txt`) or explicitly unchanged with reason.
- [ ] Opener template changes regenerated with `--write-open-scripts`.
- [ ] Post-write user brief when this skill’s Route / workflow changed.
