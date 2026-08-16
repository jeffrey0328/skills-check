# skills-check

[中文](README.zh.md)

Skill-shape norms plus Feishu-style Review for skills under the current agent app’s default skills path. It keeps every skill in the same shape, and gives you one page to see which skills are healthy and which are missing pieces.

## Install

Install through the current agent. Paste the fenced block to that agent.

```
Install the skill "skills-check" into the agent app you are currently running in.
Repo: https://github.com/jeffrey0328/skills-check.git
Steps:
1. First read and follow this agent app's current skill spec (install directory, frontmatter, how skills are attached, project pointers, human-page requirements). Do not edit files until that spec is read. Do not apply another agent product's paths or fields from memory.
2. Following that spec, clone this repo into this agent app's default skills path, using the folder name "skills-check".
3. Then change only the parts of this skill that must bind to the current agent, following that spec. Do not read through the process prose in references/, review-body.md, or examples/.
```

## Features

- Keeps every skill in the same shape: when one is created or edited, the agent writes it to the shared form and keeps the human pages and Review pages in sync.
- Opens the all-skills overview and a single skill’s Review page: preflights the fleet first, then opens the page.
- Filters the overview by tag, and lets you right-click a card to edit tags (saves immediately).
- Adds Review companions and that skill’s own `-review` to a skill that does not have them yet.

## How to use

**Resident** — the agent attaches this skill on its own, in every conversation; you do not have to `@` it. It fires whenever a skill is created or edited (the agent reads the authoring spec first), and whenever you ask to see the state of your skills. You can still say `/skills-check` or `@skills-check`.

| You say | What happens |
|---------|--------------|
| `/skills-check` | Checks every skill first, then opens the all-skills overview (check tags in the dropdown, right-click a card to edit tags) |
| `/<any-skill> -review` | Checks every skill first, then opens that one skill’s page |
| “create a skill that …” / “update this skill” | The agent applies the skill-shape norms and syncs the human pages |
| “add `<skill>` to Review” | That skill gets the required companion files and its own `-review` |

## Common changes

Say one of these to the agent; it finds and edits the right file itself.

| What to change | Say to the agent |
|----------------|------------------|
| The skill-authoring norms (how any skill must be written) | “Change the skill-authoring norms: `<new requirement>`, and roll it out to every skill” |
| The Review checking standards (what counts as 缺件 vs 需关注) | “Add a Review check: `<rule>`, and treat it as 缺件 / 需关注” |
| What one skill’s Review page says (简介 / 能做什么 / 使用方法) | “Change `<skill>`’s Review 简介 to `<text>`” |
| The tag shown on a skill’s card | Right-click that card on the overview and pick 编辑标签; or say “Change `<skill>`’s tag to `<tag>`” |
| Which tags the vocabulary offers | “Add `<tag>` to the tag vocabulary and drop `<old tag>`” |
| Where Review opens (built-in vs external browser, port) | “Open Review in the external browser” / “Use port `<n>` for Review” |
| A shared convention across all skills (companion files, hub shape) | “`<new convention>` — apply it to every skill, not just this one” |
