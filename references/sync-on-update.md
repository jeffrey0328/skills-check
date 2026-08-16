# Sync Review when a skill updates

Two update kinds. Match the kind first, then do only that checklist.

**读法:** § Resident first (this skill is always-on)；§ Domain skill update for content/trigger/layout changes on any skill；§ Review skill update when this folder’s viewer or opener template changes；§ After sync for how to refresh the running page.

## Resident (always-on)

This skill is **常驻**. When it is attached and **any other skill** under the current agent app’s default skills path is created or updated this turn:

1. If that skill fails the adopt checklist (`adopt-review.md` § What “supports Review” means), adapt it first.
2. Then run § Domain skill update for the companions that drifted.
3. End the turn with a one-line Chinese note of what was synced. Do not open the Review page unless the user asked to review.

Pure typo/format fixes with no Route / `description` / workflow change: skip companion rewrites; say so in one line.

## Domain skill update

When you change a skill’s workflow, constraints, triggers, examples, or layout (typical `jeffrey-workflow-skill` authoring turn):

| Companion | Sync when |
|-----------|-----------|
| `README.md` / `README.zh.md` | Purpose, triggers, install, or file list changed (keep both files in sync) |
| `review-intro.md` | One-line 简介 no longer matches what the skill does |
| `review-body.md` | 能做什么 / 执行步骤 drifted from the new Route / Commands |
| `review-usage.md` | Chat input, domain 子指令, or auto-invoke mode changed |
| `tag.txt` | Only when the user asks to retag |
| `SKILL.md` `-review` row | Keep it; do not drop it during a content edit |
| `scripts/open-review.ps1` | Leave as-is unless § Review skill update applies |
| `references/cross-reference.md` | Files or cited `##` / `§` headings were added, renamed, moved, or deleted |

Authoring detail: `skill-authoring.md` § Synchronize companion files.

After the files are saved, **restart** that skill’s Review so the page rescans:

- `/<that-skill> -review`

A browser refresh also rescans Markdown. It does not reload `skills-check-viewer.py`.

## Review skill update

When **this** skill changes (`skills-check-viewer.py`, `OPEN_REVIEW_PS1` template, health-check rules, or the adopt/sync docs):

1. **Restart the viewer** with `/skills-check` (or `/<skill> -review`). Start always kills the old process and loads the latest `.py`.
2. **If the opener template changed** (the string that `ensure_open_review_scripts` writes), rewrite every skill’s script in the same turn:

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --write-open-scripts --print
```

3. **If adopt / sync / open runbooks changed**, keep this skill’s own `review-intro.md` / `review-body.md` / `review-usage.md` / `README.md` / `README.zh.md` aligned (same companion rule as any other skill).
4. **Point other hubs at the new paths** when you move a file: `jeffrey-workflow-skill` authoring docs, each skill’s `cross-reference.md` opener row, and `open-review.ps1`.

## New skill added to the fleet

Treat as adopt + one opener pass:

1. Follow `references/adopt-review.md` on the new folder.
2. Run `--write-open-scripts` so the new folder gets `open-review.ps1` and existing folders stay on the current template.
3. Open `/skills-check` once to confirm the new card.

## After sync

| You want | Do |
|----------|----|
| Latest Markdown on an already-open page | Browser refresh, or restart `/<skill> -review` |
| Latest viewer Python / health checks | `/skills-check` or `/<skill> -review` (restart) |
| Latest `open-review.ps1` in every skill | `--write-open-scripts` then restart |

Reply with a short Chinese summary of what was synced. Do not paste viewer HTML.

## Must

- While this skill is attached, sync (or adopt-then-sync) every other skill created or updated this turn. *(see § Resident)*
- Sync the human companions in the domain-skill table when that skill’s substance changes.
- Restart Review after a viewer `.py` change; run `--write-open-scripts` when the opener template changes.

## Must not

- Rely on browser refresh to pick up a new `skills-check-viewer.py`. *(← Must: restart the viewer)*
- Hand-edit each skill’s `open-review.ps1` to a different viewer path. *(← Must: regenerate from this skill’s template)*
