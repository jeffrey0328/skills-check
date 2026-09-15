---
name: skills-check
description: >-
  Resident skill for skill norms and Feishu-style Review. Auto-runs every
  conversation: when creating or editing any skill, read this skill's authoring
  spec first; before opening the overview, adapt every skill under the current
  agent app's default skills path; /<skill> /skill-review preflights that
  skill only; when any skill is created or updated, sync its Review companions.
  Open overview with /skill-review or /skills-check; open one skill with
  /<skill> /skill-review.
  Triggers: conversation start, 写skill, 创建skill, 更新skill, skill规范,
  Skills 总览, /skill-review, 体检, review 同步.
---

# Skills check (hub)

Thin control plane. **`/` and `@` paste this entire file** — keep routing-only. After attach: match intent → Read **one** `references/*.md` (Grep `^## ` → offset/limit if multi-section).

**Skill root:** `skills-check/` under the current agent app’s default skills path.

| Layer | Path |
|-------|------|
| 1 Index | this file |
| 2 Content | `references/` |
| 3 Cases | `examples/` |

## Commands

| Command | Action |
|---------|--------|
| *(none)* | Fleet preflight, then open the **all-skills overview** → `references/open-review.md` |
| `/skill-review` (this skill in the user message) | This-skill preflight, then this skill’s Review page → `references/open-review.md` § Single |

## Route (required)

| User intent | Read first |
|-------------|------------|
| Create/update Skill, SKILL.md, README, review-*, 写skill, 创建skill, 更新skill, skill规范 | `references/skill-authoring.md` |
| `/skill-review` (alone) / `/skills-check` / Skills 总览 / 体检 / review 全部 | `references/open-review.md` § Preflight then § Overview |
| `/<any-skill> /skill-review` | `references/open-review.md` § Preflight then § Single |
| 普通 skill 怎么接入 Review / 改造 / adopt | `references/adopt-review.md` |
| 其他 skill 本轮被创建或修改 / 同步 Review | `references/sync-on-update.md` |
| Norms / DoD / where is file X? | `references/hub-norms.md` |
| Editing/renaming/moving any references/scripts/examples file or `##` heading | `references/cross-reference.md` **first** |

## Always (minimal)

- **Resident:** stay in effect the whole conversation.
- **Authoring:** creating or editing any skill → read `references/skill-authoring.md` first (then that skill’s own `cross-reference.md`).
- When any other skill is created or updated this turn, follow `references/sync-on-update.md` (adopt first if it fails the checklist).
- **Before every Review open:** `references/open-review.md` § Preflight — `/skill-review` alone adapts the fleet; `/<skill> /skill-review` adapts that skill only.
- `/<any-skill> /skill-review` still opens that skill’s page after preflight.
- Before editing any skill file, read `references/cross-reference.md`; update it after changing any cross-reference.
- Full Must / DoD → `references/hub-norms.md`.
