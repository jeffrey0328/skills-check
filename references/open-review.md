# Open Feishu-style Review

**读法:** § Preflight first on every open；§ Overview for `/skill-review` (alone) / `/skills-check` / 总览 / 体检；§ Single for `/<skill> /skill-review`；§ Browser for which window to use；§ Skills root when the skills root needs resolving. Global command: `/skill-review`.

## Skills root

Scan and write only the **current agent app’s default personal-skills path**.

Resolve the default personal-skills path of **the current agent app**. Do not scan or write other agent apps’ skills trees.

Skip non-skill dirs in that root (`logs`, `scripts`, `.git`, names starting with `.`). A skill is a directory that contains `SKILL.md`.

## Preflight (required before every open)

Do this **before** § Overview or § Single. Scope depends on what you are opening. Do not open while the **in-scope** skill(s) fail the adopt checklist.

| Open | Scan | Adapt |
|------|------|-------|
| `/skill-review` (alone) / `/skills-check` overview | `--print` (all skills) | Every failing skill in the root |
| `/<skill> /skill-review` single | `--print --skill <folder>` | **Only that skill.** Leave siblings alone. |

1. Resolve the skills root (§ Skills root).
2. Run the matching scan:

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --print
python "<skills-check>/scripts/skills-check-viewer.py" --print --skill "<skill-folder>"
```

(If this skill lives under a different root, pass that root as the first argument.)

3. For each **in-scope** skill folder, treat these as **must-adapt** (fix in this turn, then re-scan):
   - missing `README.md` / `README.zh.md` / `review-intro.md` / `review-body.md` / `review-usage.md`
   - README pair missing the other-language entry, missing the agent install prompt (English prompt in `README.md`, Chinese prompt in `README.zh.md`; git URL + steps), or section order is not 简介 → 安装 → 具体内容 → 其他
   - a specific agent app name appears in the skill (write 当前 Agent / Agent instead)
   - missing `SKILL.md` Commands row `/skill-review`
   - missing `scripts/open-review.ps1`, or the script does not call `skills-check\scripts\skills-check-viewer.py`
   - missing `tag.txt` (write a short tag from the folder name; tell the user they can rename)
4. Adapt in-scope failing skills with `references/adopt-review.md` (extract companions from that skill’s existing `SKILL.md` / `README.md`; do not invent domain workflow). Overview: then `--write-open-scripts` once for the root. Single: if that skill’s opener is missing, write **that** `scripts/open-review.ps1` only; do not rewrite every skill.
5. Re-run the same-scope scan. Open Review only when in-scope required companions and `/skill-review` / opener path pass. Remaining 需关注 (pairing, examples, description length) may stay; mention them in the short summary.

If in-scope skills already pass the must-adapt list, skip writes and continue to § Overview or § Single.

## Flags

| User says | Action |
|-----------|--------|
| **`/skill-review`** (alone) | **Restart** the all-skills overview (kill old viewer → load latest `.py` → open `#/`) |
| **`/skills-check`** (no flag) | Same as `/skill-review` alone |
| Natural language while this skill is attached: Skills 总览 / review 全部 / 体检 skills | Same as `/skill-review` alone |
| **`/<any-skill> /skill-review`** or **`@<any-skill> /skill-review`** | **Restart** that skill’s Review (kill old viewer → load latest `.py` → open `#/skill/<folder>`). Detect the skill from the **user message** `/` `@`, not from resident auto-attach. |
| **`/skills-check /skill-review`** | This skill’s own single page (same as any other skill’s `/skill-review`) |

**Docs split:**

- **Every** skill: `/skill-review` in **`SKILL.md`** Commands (Agent). With that skill named in the same message → that skill’s page.
- **Overview entry:** global command **`/skill-review`** (alone). `/skills-check` with no extra skill name is the same overview. Do not keep `-reviewall` on `jeffrey-workflow-skill` or any other hub.
- **Feishu Review「怎么用」:** list the overview command **only** on **this** skill (`review-usage.md`). Other skills do not list `/skill-review` / overview on their Review page.

## Browser

Default to **the agent's built-in browser**, not the external browser — unless the user explicitly asks for the external/system browser.

**How:** start the viewer with **`--no-browser`**, then open the printed local URL via `open_resource`.

- Overview: `python …\skills-check\scripts\skills-check-viewer.py --no-browser` → `open_resource` the URL.
- Single: `python …\skills-check\scripts\skills-check-viewer.py --skill <folder> --no-browser` → `open_resource` the URL. (`open-review.ps1` does not pass `--no-browser`, so for the internal-browser default call Python directly.)
- **External browser only on explicit request:** omit `--no-browser` and let the viewer auto-open.

## Overview

Serves local HTTP (default **http://127.0.0.1:18765/**), hash `#/`.

| Action | What updates |
|--------|----------------|
| **`/skill-review` or `/skills-check`** (start viewer) | **Restarts** Review: ends old `skills-check-viewer` processes, loads **latest `.py`**, rescans skills, opens browser (same port when possible) |
| **Browser refresh** | Re-scans skill files only — **does not** reload viewer Python code |

Ctrl+C stops the server.

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --no-browser
```

Optional: `--port 18765`  `--no-restart`.

After stdout prints the URL, `open_resource` that URL. Reply with a short Chinese summary from stdout. Do not paste the full HTML.

## Single

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --skill "<skill-folder>" --no-browser
```

Or (external-browser path; the generated script does not pass `--no-browser`):

```powershell
powershell -ExecutionPolicy Bypass -File "<skill>/scripts/open-review.ps1"
```

Then `open_resource` the printed URL when using `--no-browser`.

## Ensure open-review scripts

After the viewer’s `OPEN_REVIEW_PS1` template changes, rewrite every skill’s opener:

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --write-open-scripts --print
```

## Views

| View | Hash | Content |
|------|------|---------|
| **Overview** | `#/` | Summary cards + each skill’s status, issues, one-line intro. Status filter row, then a **tag dropdown** (multi-check = 任一命中). 「清除筛选」clears status + tags. **Right-click a card** → 编辑标签 / 进入 Review 页 / 复制修复提示词 |
| **Single skill** | `#/skill/<folder>` | 状态为需关注/缺件时标题栏下直接列出问题（点「复制提示词」弹窗给出可粘贴的修复说明；需关注可点「忽略」），再是 **使用方法** / 能力芯片 / **功能描述** / **功能** / **执行步骤**；右上角下拉切换 skill |

**怎么用** is read only from each skill’s **`review-usage.md`**. Structure:

1. `## 使用方法` — one sentence on how to invoke. No `###`.
2. `## 功能` — under `### <能做什么标题>`, only `####` 命令 / 参数 / 脚本 / 工具. Overview command **only on this skill**. Skip the heading when there are none.

**功能描述 / 执行步骤** come from Chinese **`review-body.md`**（`## 能做什么` 在页面上显示为 **功能描述**）。 **Overview / detail 简介** comes from **`review-intro.md`**. English frontmatter `description` and the README pair are not used for the human intro. Page order: 使用方法 → 能做什么芯片 → 功能描述 → 功能 / 执行步骤.

**Fix hook:** 需关注/缺件条目上的「复制提示词」弹出完整修复说明。弹窗里再点「复制提示词」写入剪贴板并关闭，可直接去粘贴。点框外不关闭。不打开编辑器、不切工作区。

**Ignore hook:** 需关注条目上的「忽略」写入本 skill 的 `review-ignored.json`（按检查 id + 原文记住这一条）。之后总览和单页都不再列出；该 skill 若只剩被忽略的需关注、没有缺件，状态变为通过。缺件没有忽略按钮。写入走 `POST /api/ignore`，鉴权与 `/api/tag` 相同。同一条检查如果原文变了会再出现。

**Tag hook:** 总览卡片右键 →「编辑标签」弹窗（当前标签可 ✕ 删、候选点一下加入、输入框回车新建）→「保存」直接写该 skill 的 `tag.txt` 并刷新卡片与筛选；清空则删除 `tag.txt`。写入走 `POST /api/tag`，只认本次会话 token、拒绝跨站与 skills 根目录之外的路径。候选与词表：`skill-authoring.md` § Tag。

File roles and pairing rules: `skill-authoring.md`.

## Health checks

| Check | Pass | 缺件 (fail) | 需关注 (warn) |
|-------|------|-------------|----------------|
| File / role checks | required companions present: `README.md` + `README.zh.md`（互相入口；英文/中文安装提示词；简介→安装→内容→其他）、`review-intro` / `review-body` / `review-usage`；不用具体 Agent 应用名 | missing `README.md` / `README.zh.md` / `review-*` / `tag.txt` / `open-review.ps1`；README 缺另一语入口、缺对应语言的安装提示词或排版顺序不对；出现具体 Agent 应用名 | pairing leftovers, examples, description length |
| **能做什么条目** | 页面「功能描述」：功能本身、规则、细节；每项子列表；不重复命令/执行步骤，不写人类页 | — | 标签后写成一段；或把 slash 命令、`先`/`再`/`然后`、人类页清单写进功能描述 |
| **README 面向用户** | 具体内容只有 功能介绍 + 怎么用（你说什么 → 会发生什么）+ 常见改动（想改什么 → 对 Agent 说的一句话） | — | README 残留文件角色 / 目录清单表或 `何时` / `怎么调用` / `What it does` 之类多余小节；缺 `功能介绍` / `怎么用` / `常见改动` |
| **肯定/否定配对** | 无否定句，或每条 Must not 与某条 Must 有包含/重合（或显式 `← Must`） | — | 否定句缺少重合肯定句；README/正文里冗余括号否定 |

Violations of the pairing rule are **需关注**, not 缺件. A missing README file, missing other-language entry, or wrong README section order is **缺件**.

## Must

- Run § Preflight on every Review open: `/skill-review` alone adapts the fleet; `/<skill> /skill-review` adapts **that skill only**.
- Edit that skill’s `review-usage.md` when「怎么用」needs changes.
- Write「怎么用」only as what a person types / says / clicks. Scripts stay under `scripts/` for the agent.
- Show the overview command on Feishu Review **only** for `skills-check`.
- Default open to the agent's built-in browser: viewer `--no-browser`, then `open_resource`. *(see § Browser)*
- Persist ignored 需关注 via `POST /api/ignore` into this skill’s `review-ignored.json` (id + 原文). *(see § Views · Ignore hook)*

## Must not

- Invent「怎么用」正文. *(← Must: edit review-usage.md)*
- Put `description` 原文 or a script inventory on「怎么用」. *(← Must: 怎么用 = what the person types / says / clicks)*
- List overview / `/skill-review` on other skills’ Feishu Review pages. *(← Must: overview only on this skill’s Review)*
- Open the Review page in the external browser by default. *(← Must: default to built-in browser)*
- Keep or revive `-reviewall` on `jeffrey-workflow-skill`. *(← Must: overview is `/skill-review`)*
- Open Review while an **in-scope** skill still fails the must-adapt list. *(← Must: Preflight first)*
- On `/<skill> /skill-review`, adapt or block on sibling skills. *(← Must: single-page preflight is that skill only)*
- Treat resident auto-attach as the skill named for `/skill-review`. *(← Must: detect `/` `@` from the user message)*
- Put an 忽略 button on 缺件. *(← Must: persist ignored 需关注)*
