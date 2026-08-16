# Agent Skill authoring workflow

Read this when **creating or updating** any Agent Skill. This file is the skill-shape spec for **`skills-check`**. For large-repo exploration, also read **`jeffrey-workflow-skill/references/repo-exploration.md`**. Human Review: overview `/skills-check`; single page `/<skill> -review`. Adopt / sync: `adopt-review.md` and `sync-on-update.md` in this skill.

## Exploration checklist (required)

Before editing `SKILL.md` or other skill content, read-only exploration in this order:

1. Source paths, modules, and call chains the user named.
2. In-repo **examples** (`examples/`, `samples/`, tests, similar skills).
3. In-repo **docs** (`README`, `docs/`, `*.md`, inline comments).

**关联记录 first:** before editing any skill, read **that skill’s** `cross-reference.md`. Before editing this skill’s files, read **this** skill’s `cross-reference.md`. After changing any cross-reference, update the matching record.

Write only from what you read. Prefer repo-local facts; use **web search** only when the user allows **and** the gap is not a repo-local fact. If information is missing: **list gaps** and ask for paths or excerpts.

**Must not** (overlaps above): guess APIs/paths/behavior without reading; invent to fill gaps; routine web search for repo-local facts.

**Large repos**: follow **`repo-exploration.md`**—scoped tools; no whole-tree recursive scans.

## File roles (canonical)

| Path | Audience | Role |
|------|----------|------|
| `SKILL.md` | Agent | **Thin** English hub: routing + Commands (+ few always-on bullets). `-review` on every skill; overview via `/skills-check` |
| `references/` | Agent | Long workflows, full Must/Must-not, DoD, file indexes — **read on demand** |
| `README.md` | Human | English README — **required**; link to `README.zh.md` |
| `README.zh.md` | Human | Chinese README — **required**; link to `README.md` |
| `review-intro.md` | Human | Feishu Review **简介** only — short Chinese blurb (overview + detail header) |
| `review-body.md` | Human | Feishu Review **能做什么** / **执行步骤** (`## 能做什么`, `## 执行步骤`; **Chinese**). Split 能做什么 only when jobs are loosely related. Every item has a matching `###` — even one step |
| `review-usage.md` | Human | Feishu Review **使用方法** (one sentence) + **功能** — what a person types / says / clicks. No `description` dump, no `scripts/*` inventory |
| `tag.txt` | Human / Review | Display tags |
| `examples/` | Both | Layer-3 cases (see **Three layers**) |
| `scripts/` | Agent / local | Bound to flags / SKILL actions — not listed under Review「怎么用」 |

## Three layers (required)

Every skill has **at least** these three layers. The hub (layer 1) indexes the other two. Extra dirs are allowed when the skill’s work needs them.

| Layer | Default path | Role |
|-------|--------------|------|
| **1 Index** | `SKILL.md` | Route / Commands only. A short Layers table names layer-2 and layer-3 paths. |
| **2 Content** | `references/` | Playbooks, norms, DoD. Domain aliases: `modules/` (UE), `standards/` (video). |
| **3 Cases** | `examples/` | Concrete worked examples the agent can copy. If cases already live in `templates/`, `modules/*/code-templates.md`, or `standards/*模板*`, `examples/` still holds a `case-index.md` that points at them. |

**Optional extras** (only when the skill’s content needs them): `scripts/` / `tools/` (runnable), code next to playbooks, Review companions (`review-*.md`).

A stub `examples/agent-snippet.md` that only says “load the skill → read X” does **not** count as layer 3. Write a real case or a `case-index.md`.

## Prefer static skill assets (required when **using or authoring** any skill)

When a skill workflow would **dynamically write code** (ad-hoc Shell that grows into a script, one-off `.py`/`.ps1` in the workspace, helpers reinvented each run), **judge staticizability first**.

| Signal → staticize into the **owning skill** | Keep dynamic (do not pollute the skill) |
|----------------------------------------------|-----------------------------------------|
| Same purpose / flags / inputs across runs or machines | Truly one-shot for this chat only |
| Agent (or human) will need it again for this skill’s Commands / Route | Tied to one user project’s product code, not the skill |
| Stable enough to version next to `SKILL.md` | Secrets, machine-only paths, or ephemeral debug |

**When staticizable — Must:**

1. **Add** the asset under the skill that owns the workflow: `scripts/` (runnable, bound to a Command/flag), `examples/` (templates to adapt), or `references/` (documented snippets — not a fake “script inventory” under Feishu「怎么用」).
2. **Document when to use**: Commands / Route row, and/or a short **When** in the script header or the matched `references/*.md` section.
3. **Sync companions** if humans need the new action (`review-body.md` / `review-usage.md` / `README.md` + `README.zh.md`) — same as § Synchronize companion files.
4. Tell the user what was added and the **when** trigger.

**Must not:** Re-invent the same helper as chat-only dynamic code every session when it belongs in that skill. *(← Must: prefer static + document when)*

Authoring check: new repeatable automation → ship static + when as the documented path.

## Thin hub / slash-attach budget (required when creating **any** skill)

Applies to **every** Agent Skill created or materially reshaped under this workflow — not only `jeffrey-workflow-skill`.

**Product fact:** `/skill-name` and `@skill-name` paste the **entire** hub `SKILL.md` into that user turn. Agents cannot lazy-load the pasted body. Description-only auto-attach (no slash) lists the skill without pasting the hub.

| Must | Must not *(← overlapping Must)* |
|------|----------------------------------|
| Keep `SKILL.md` **routing-only**: frontmatter `description`, purpose one-liner, Commands, Route table, optional ≤5 always-on bullets | Stuff full Must/Must-not lists, Definition of Done checklists, large file indexes, or long procedures into `SKILL.md` *(← thin hub)* |
| Put long agent content in `references/*.md` and route to them; after attach, Read **one** matched reference (partial `##` when long) | Default-Read every `references/*.md` or the whole skill tree on attach *(← route + partial read)* |
| Prefer a dedicated norms/DoD file when the hub would otherwise bloat (e.g. `references/hub-norms.md` or `references/<domain>-norms.md`) | Duplicate the same long norms in both hub and references *(← single source in references)* |

**Shape checklist (create / update):**

1. Frontmatter `description` (triggers) — what auto-attach exposes every turn.
2. Hub body = Commands + Route (+ minimal Always). Target: short enough that a slash paste is cheap (rough guide: prefer well under ~100 lines / ~4K characters of hub body).
3. Norms, DoD, indexes, multi-step playbooks → `references/`.
4. Long reference files: top **读法** / when→which `##` table — see **Partial read** below.
5. **Three layers:** hub indexes content + cases — § Three layers. Missing `examples/` or a stub-only examples dir is unfinished.

Reference layout: this hub’s thin `SKILL.md` + `references/hub-norms.md`. Template: `examples/agent-snippet.md`.

## README at skill root (required)

Every skill **must** have **two** root README files. Both are **required companions** (Feishu Review **缺件** if either is missing, or if they do not link to each other). Not Feishu Review sources (`review-*.md` stays the Review pages).

| File | Language | Entry to the other (first line after the `#` title) |
|------|----------|-----------------------------------------------------|
| `README.md` | English | `[中文](README.zh.md)` |
| `README.zh.md` | Chinese | `[English](README.md)` |

The two files cover the **same facts**. Do not keep a bilingual single file.

**Section order** (both files, same sequence):

1. **简介** — untitled prose right after the language link. One short paragraph: what the skill is.
2. **安装方法** — first H2: English `## Install` / Chinese `## 安装`. One short line: install **through the current agent**. Then **one fenced prompt** in **that file’s language** (`README.md` English, `README.zh.md` Chinese). The prompt **must** include the git URL and the install steps. Do **not** give a human `git clone` command. Extra install-only notes (e.g. `-setupproject`) may follow the fence, still inside this H2.
3. **具体内容介绍** — **exactly three** H2s, all written for **the person using the skill**: what it can do, how to use it, then how to change it. English: `## Features`, `## How to use`, `## Common changes`. Chinese: `## 功能介绍`, `## 怎么用`, `## 常见改动`. Nothing else belongs in this block.
4. **其他内容** — extras that are not install and not those three (e.g. Privacy).

**`Features` / `功能介绍` (required)** — what this skill can do, as a short bullet list (about 3–8 items). Each bullet is one capability a person would recognize. Write outcomes, not file names. Do **not** paste `review-body.md` 能做什么 verbatim (that page is for Feishu Review and may name agent files).

**`How to use` / `怎么用` (required)** — how a person triggers this skill, and *when* it fires, in one place:

- One lead line: resident / auto-attach vs `@<name>` vs keywords. Resident: say so plainly (no `@` needed).
- Then a two-column table: **你说什么 / You say** → **会发生什么 / What happens**. Rows are what the person types or says (`/flag`, `@<name>`, a plain request), never internal file paths.
- Fold “when it applies” into this section — do **not** add a separate `When` / `何时` or `How to invoke` / `怎么调用` H2. If the skill only fires in narrow cases, say so in the lead line.

**`Common changes` / `常见改动` (required)** — how the user changes this skill’s own content, as a two-column table:

| Column | Content |
|--------|---------|
| 想改什么 / What to change | The user-visible knob: this skill’s norms, its checking standards, its templates, its data store, its output paths, its triggers |
| 对 Agent 说 / Say to the agent | One sentence a person can paste. The agent locates the file itself |

Cover every knob a user actually wants to turn in that skill. Name a file only as a trailing hint after the intent, never as the row key. Write the say-to-the-agent sentence in **that README’s language** (English in `README.md`, Chinese in `README.zh.md`).

**Must not:** Add any other H2 to 具体内容介绍 — no `When` / `何时`, no `How to invoke` / `怎么调用`, no `What it does` / `做什么`, no file-roles / file-inventory / layout table (`File roles`, `文件角色`, `Layout`, `目录`). One-line purpose stays in the 简介 paragraph; capabilities go in `功能介绍`; trigger timing goes in `怎么用`; file roles are agent-facing (§ File roles + the skill’s `references/hub-norms.md` File index). *(← Must: 具体内容 = 功能介绍 + 怎么用 + 常见改动)*

**Must not:** Put `## What` / `## 做什么` before Install; or give a standalone `git clone` as the install method. *(← Must: 简介 → 通过 Agent 安装提示词 → 具体内容 → 其他)*

Include at minimum (split across those four blocks):

- Intro paragraph (purpose and outcomes).
- Install: agent prompt with git URL + steps — § Install prompt.
- `功能介绍`: what it can do. `怎么用`: how it is triggered and when it fires. `常见改动`: how to ask the agent to change its norms, standards, templates, and data.

**Language**

- `SKILL.md`: **English** default (agent control plane).
- `README.md`: English human page — **required companion** (missing, no link to `README.zh.md`, or wrong section order = 缺件).
- `README.zh.md`: Chinese human page — **required companion** (missing, no link to `README.md`, or wrong section order = 缺件).
- `review-intro.md`: **Chinese** one short plain-text paragraph for Feishu Review overview/detail 简介 (dedicated file; not English `description` / README). No Markdown markers (`**bold**`, `` `code` ``) — overview shows the text as-is.
- `review-body.md`: **Chinese** `## 能做什么` and `## 执行步骤` (viewer reads these only; English `description` must not fill 能做什么). **执行步骤** is last on the Review page (after 怎么用). Split 能做什么 only when two jobs are loosely related. Same job with different modules or stages stays one item (e.g. UE C++ + PCG + Landscape = 写 UE C++). Every 能做什么 item has a matching `###` under `## 执行步骤` — even a single step. Viewer accepts **only** `## 执行步骤` — not `## 功能怎么执行`.
- `review-usage.md` / human Review UI: **Chinese** default. `## 使用方法` (no `###`) is **one sentence**: 常驻写「常驻，不需要 @skill，也不需要用户或关键词触发。」；非常驻写「对话里 `@<name>`，或提到 / 说 …」；`@<name>` 和每个关键词都用 code span。No labeled rows, no example sentences. `## 功能` + `### <能做什么标题>` + `####` 命令 / 参数 / 脚本 / 工具 = what the person types. Do not nest another「功能」heading. Table columns are 命令/参数/脚本/工具 + 说明. Do not copy frontmatter `description`. Do not list agent-only scripts. Install-to-other-agent lives only in the README Install prompt.

**Feishu Review prose (`review-intro` / `review-body` / `review-usage`) — bold**

| Do | Do not |
|----|--------|
| Bold **only the lead label** before `：` on list items, same pattern every line — e.g. `- **路由**：正文` / `1. **开场**：正文` | Mid-sentence bold for emphasis (`仅在…时`、`不`、`Must` 等) |
| Use `` `code` `` for paths, flags, filenames, type names | Mix: some bullets bold lead, some bold nowhere, some bold mid-line |
| `review-intro.md`: plain text, **no** `**bold**` (overview escapes as plain) | Bold inside intro |

If a bullet has no natural lead label, either add a short one or leave the whole line unbolded — do not sprinkle `**` elsewhere in that line.

## Install prompt (required)

`## Install` / `## 安装` is **install through the current agent**. After one short intro line, one fenced prompt in **that README’s language**. It does **not** go on Feishu Review / `review-usage.md`.

The prompt **must** include:

1. The skill folder name.
2. The git URL (`Repo:` / `仓库：https://…/*.git`).
3. Numbered **Steps** / **步骤**: first read **this** agent app’s skill spec; then clone into that app’s default skills path (folder name = skill name); then adapt only the bind points. Paths come from that spec.

English intro + English prompt in `README.md`. Chinese intro + Chinese prompt in `README.zh.md`. Same facts; do **not** paste the Chinese block into `README.md`.

Fill `<name>` and `<repo.git>`.

English (`README.md`):

```
Install the skill "<name>" into the agent app you are currently running in.
Repo: https://github.com/<owner>/<repo>.git
Steps:
1. First read and follow this agent app's current skill spec (install directory, frontmatter, how skills are attached, project pointers, human-page requirements). Do not edit files until that spec is read. Do not apply another agent product's paths or fields from memory.
2. Following that spec, clone this repo into this agent app's default skills path, using the folder name "<name>".
3. Then change only the parts of this skill that must bind to the current agent, following that spec. Do not read through the process prose in references/, review-body.md, or examples/.
```

Chinese (`README.zh.md`):

```
请把 skill「<name>」安装到你当前所在的 Agent 应用。
仓库：https://github.com/<owner>/<repo>.git
步骤：
1. 先读取并遵守你当前这个 Agent 的 skill 规范（安装目录、frontmatter、挂载方式、项目指针、人类页要求）。未读到该规范之前不要改文件。不要凭记忆套用某一个 Agent 产品的路径和字段。
2. 按该规范把该仓库克隆到当前 Agent 的默认 skills 路径，文件夹名用「<name>」。
3. 再按该规范改本 skill 里需要对接到当前 Agent 的部分。不要通读 references/、review-body.md、examples/ 里的流程正文。
```

**Must:** `README.md` uses the English prompt; `README.zh.md` uses the Chinese prompt (git URL + steps + spec first).

**Must not:** Put a human `git clone` command in Install, put a Chinese prompt in `README.md`, or start installing before the current agent’s spec is read. *(← Must: one agent prompt per language; spec first)*

## Agent-app names (forbidden)

Do **not** use a specific agent app name. Write **the current agent app**, **Agent**, or **the agent**. This applies **anywhere** in a skill (hub, README, review-*, references, examples, scripts, templates, agents, tools, filenames).

Forbidden names (any capitalization or spacing): Cursor, Claude Code, ClaudeCode, Codex, WorkBuddy, Trae, CodeBuddy — including those names inside paths and filenames.

**Must:** discover the current app’s skills path from this skill’s location or from that app’s spec; never hard-code an agent app directory.

**Must not:** Use a specific agent app name or that app’s path. *(← Must: agent-agnostic wording)*

The install prompt says「某一个 Agent 产品」, not an agent app name.

This section is the ban list (needed so the checker can name what is forbidden). CSS `cursor:` in stylesheets is the CSS property, not an agent app name.

## Auto-invocation decision (required when creating)

Two **mechanisms** (configured differently; **both** must be explained to humans when used):

| Mechanism | Configured in (skill / project) | Tell the human in |
|-----------|----------------------------------|-------------------|
| **按 description 加载** | `SKILL.md` frontmatter: `description` triggers; **omit** `disable-model-invocation` to allow | `## 使用方法` 按常驻 / `@` / 关键词三行写。不要把 `description` 原文抄进 Review |
| **项目 AGENTS 拉起** | Project root **`AGENTS.md`** pointer | `## 使用方法` 用一句话写清 `@` 或会提到的词 |

Skill frontmatter = control plane. Review tells the person how they invoke the skill. Agent-only fields stay in `SKILL.md`.

**Before finishing** a new skill (or when the user changes invoke policy), **ask once** which **product** mode:

| Mode | Skill frontmatter | Project `AGENTS.md` | `review-usage.md` |
|------|----------------------------|---------------------|-------------------|
| **仅手动** | `disable-model-invocation: true` | No required pointer | 一句话：对话里 `@<name>`，需要时再写会说的词 |
| **条件自动** | Often `disable-model-invocation: true` + AGENTS；**or** omit disable and rely on `description` match | If AGENTS path: add pointer | 一句话写清 `@<name>` 和会提到的词 |
| **常驻 / 默认** | **Omit** `disable-model-invocation`；`description` 写清常驻意图 | Optional | 一句话：常驻，不需要 @skill，也不需要用户或关键词触发。 |

### Feishu sections for auto-load

Invoke path belongs in `## 使用方法` as one sentence. Never paste the frontmatter `description` onto Review.

Defaults if unanswered: **ask** — do not guess. Current set: **`jeffrey-workflow-skill`** → **常驻 / 默认**（description）；**`ue-dev-skill`**（UE 唯一入口，域内容在其 `modules/`）→ **条件自动**（`AGENTS.md` + `disable-model-invocation: true`）; **`user-profile`** → **常驻 / 默认**（description）；**`skills-check`** → **常驻 / 默认**（description：创建/编辑 skill 先读本规范；打开 Review 前先适配当前 agent 默认 skills 路径下的全部 skill；其他 skill 本轮被改时同步人类页）。

## Review flags

| Entry | Agent docs (`SKILL.md`) | Feishu Review page (`review-usage.md`) |
|-------|-------------------------|----------------------------------------|
| **`/<skill> -review`** | **Every** skill — that skill’s page via `scripts/open-review.ps1` | Domain skills omit it. **`skills-check`** lists its own `-review` |
| **`/skills-check`** | **`skills-check` only** — all-skills overview | **Only** `skills-check` lists the overview command |

Other skills: keep `-review` in `SKILL.md` Commands; **do not** put `-review` or `/skills-check` in their `review-usage.md`. Adopt / sync: `skills-check/references/adopt-review.md` and `sync-on-update.md`. Resident `skills-check` runs that sync when any skill is created or updated in the same turn.

## Tag (required when creating)

Each skill has **one or more** short display tags (Chinese preferred), shown after the skill name on the Feishu Review overview and detail pages.

**Storage (in the skill directory):**

```
<skill-root>/tag.txt
```

- Single line, UTF-8.
- **Multiple tags**: comma-separated, e.g. `代码,UE` or `工作流`. Up to **8** tags, each ≤ **24** chars.
- Spaces around commas are optional; the Review viewer trims each segment.

**Shared vocabulary:** `skills-check/tag-vocab.txt` (one tag per line) holds the fleet-wide tag list. The overview offers those plus every tag already in use as candidates, and appends newly created tags. Prefer an existing tag over a near-synonym so the overview’s tag filter stays useful.

**Editing from the overview:** on **Skills 总览**, right-click a skill card → **编辑标签** → pick existing tags or type a new one → 保存. That writes `tag.txt` directly (empty selection deletes the file) and refreshes the cards and the tag filter. The agent still writes `tag.txt` when creating a skill, or when the user asks in chat.

**Before finishing** a new skill:

1. **Propose** tag(s) from the domain (e.g. `代码,UE`、`工作流`、`自媒体`、`画像`).
2. **Ask** the user to confirm or rename:  
   > 建议标签为「…」（多标签用逗号分隔），是否放到这些标签下？可改成你想要的名称。
3. Write the confirmed string to **`tag.txt`**.

On update, change `tag.txt` only when the user asks to retag.

## Partial read (skills & rules → context/cache)

**Consuming** a Skill or project/plugin rules file: do **not** default-Read the whole file into context.

1. Prefer hub `SKILL.md` routing → **one** `references/<file>.md` for the intent.
2. Inside a multi-section `.md` (`##` headings, or an explicit 读法/index table): Grep `^## `, then Read **only** the needed section(s) via offset/limit.
3. Same for `AGENTS.md` / plugin `PublicAgentRules.md`-style docs when they document sectioned load rules.

**Authoring:** follow **Thin hub / slash-attach budget** (required above). For long single files, add a top **读法 / when→which `##`** table. Keep always-on adapters as pointers (omit full body copies).

## Positive / negative norms (Skills **and** Rules)

Applies to **Skill** `SKILL.md` / `references/` **and** project **Rules** (`AGENTS.md`, satellites, `.mdc`). Same rule in **`jeffrey-workflow-skill/references/project-rules.md`** § Writing norms.

**Prefer affirmative** imperatives (**Must** / **Do** / **When→Then**).

**Must not / Do not / Never / 禁止 / 不要** may appear **only if** there is already a **positive** norm whose scope **contains or overlaps** that prohibition (same concern: what to do instead, or the allowed path). The negative sharpens the positive; it must not stand alone.

| OK | Not OK |
|----|--------|
| Must: Human Review = Feishu + `review-intro.md` + `review-body.md` + `review-usage.md` (+ `README.md` / `README.zh.md` for install). Must not: create `review.html` / `human-guide.html`. | Must not: create `review.html`. *(alone)* |
| Must: partial-read needed `##` only. Must not: default-Read whole multi-section file. | Must not: read whole file. *(alone)* |
| 提交说明默认中文。 | 同句肯定后再加括号否定（例如默认中文后又写勿用英文）— 括号否定多余，只留肯定 |

**If you cannot name the overlapping positive** → rewrite as **Must** only (state the allowed behavior); drop the orphan negative.

**Human README / Review prose:** prefer affirmative-only. After a complete positive, drop redundant paren negatives (Feishu Review flags those as **需关注**).

Authoring / update check: every new or touched Must not has an explicit paired Must (same file or clearly cited). Feishu Review health check flags unpaired negatives **and** redundant paren negatives as **需关注** (`skills-check/scripts/skills-check-viewer.py` → `pos_neg_pair`).

## Synchronize companion files on create/update

After changing workflow, constraints, triggers, examples, or layout, check:

- **`README.md`**: English; `[中文](README.zh.md)` after the title; order 简介 → `## Install` → `## Features` → `## How to use` → `## Common changes` → 其他. Install = one **English** agent prompt (git URL + Steps). No `When` / `How to invoke` H2, no file-roles table. See § README at skill root + § Install prompt.
- **`README.zh.md`**: Chinese; `[English](README.md)` after the title; same order with `## 安装` and the **Chinese** prompt, then 功能介绍 / 怎么用 / 常见改动. Same facts as `README.md`.
- **`常见改动` rows**: if this change added or moved a knob a user would ask to change (norms, checking standards, data store, output paths, triggers), update the row in **both** READMEs.
- **`review-intro.md`**: Chinese one-line/paragraph 简介（纯文本，无 Markdown 标记）。
- **`review-body.md`**: Chinese `## 能做什么` / `## 执行步骤`（执行步骤在页面最下；相关度低才拆项；每项都有对应 `###`，一步也写；加粗仅条目标签；见上表）。
- **`review-usage.md`**: `## 使用方法` = 一句话怎么调用（常驻 / `@` / 关键词，见 § Language）；`## 功能` + `### <能做什么标题>` + `####` 命令/参数/脚本/工具；**overview command only on `skills-check`’s Review page** (other skills: agent `SKILL.md` `-review` only — see **Review flags**); no agent-only script list, no `## description 内容`; same bold rule as body.
- **Wording:** do not use a specific agent app name. Write **the current agent app**, **Agent**, or **the agent** — § Agent-app names.
- **`tag.txt`**: one-line display tag (see **Tag** above).
- Human Review = Feishu + `review-intro.md` + `review-body.md` + `review-usage.md` (see **Positive / negative norms**).
- **`examples/`**: layer-3 cases (or `case-index.md` pointing at in-skill templates) — § Three layers.
- **`references/`**: if agent workflows moved out of `SKILL.md`.
- **Thin hub:** create/update still satisfies **Thin hub / slash-attach budget** — hub stays routing-only; long norms/DoD/playbooks stay in `references/`.
- **Prefer static:** if the change adds repeatable automation that used to be chat-only dynamic code, ensure `scripts/` / `examples/` / `references/` + **when to use** are present — § Prefer static skill assets.
- **`cross-reference.md` (this skill's 关联记录):** if you added, renamed, moved, or deleted a `references/` / `scripts/` / `examples/` file, `tag.txt`, or a cited `##` / `§` heading, update the affected rows so it stays the single source for "who references what (whole/§)".

## Cross-skill rollout (关联记录 & shared conventions)

When you **create or change a skill-wide convention** — the `cross-reference.md` 关联记录 mechanism, a companion-file requirement, hub / `references` shape, or a shared script / flag — **apply it to every skill**, not only the one in front of you, so all skills stay consistent.

1. **Enumerate** skills: list directories under the current agent app’s default skills path (skip parent-level `scripts/` / `logs/` and plugin / system-managed skills).
2. **Apply per skill, adapted to its layout:** a skill with a `references/` dir puts `cross-reference.md` there and wires the rule into `SKILL.md` + `references/hub-norms.md`; a skill with no `references/` puts `cross-reference.md` at its root and wires the rule into `SKILL.md` only.
3. **Keep each skill's `cross-reference.md` current** whenever that skill's files change — this per-skill sync is the ordinary case; the fleet-wide rollout above applies only to **shared conventions**.
4. **Parallelize** across skills when the change is uniform (one subagent per skill), then **report per skill**.

Scope: a routine content or typo fix in one skill only needs **that** skill's `cross-reference.md` kept in sync — it does **not** require touching the others. *(← rollout is for shared conventions, not every edit)*

**Loading:** the skills-repo root `AGENTS.md` points here, so this norm loads before editing any skill via the workspace's AGENTS rules — independent of whether another hub is auto-attached that turn.

## Post-write user brief (required)

After **create or meaningful update** of a Skill (new Route row, new `references/*.md`, new triggers, hub→child dispatch), the agent **must** end the turn with a clear user-facing brief — not only “已写入”. Cover:

1. **怎么写的（分层）** — which files changed and why (hub Route / `description` vs long playbook in `references/`; companions touched or why skipped).
2. **怎么调用 / 被触发** — every real entry path: `/` `@` paste, `description` auto-attach (or `disable-model-invocation: true` → no auto), parent hub Route / `skills-registry`, project `AGENTS.md` if any.
3. **执行逻辑** — step-by-step what the agent does when the new content matches (match intent → which file Read → what rules apply → report `Routed: …` when a hub is involved). Prefer a short numbered flow or mermaid; name the exact reference path.

Skip only for pure typo/format fixes with no Route/`description`/workflow change — say so in one line.

If a companion file needs no change, say why in the summary. Meaningful skill changes should keep `SKILL.md`, `README.md`, `README.zh.md`, `review-intro.md`, `review-body.md`, `review-usage.md`, `examples/`, and `references/` aligned in substance.
