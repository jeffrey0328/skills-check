# Adopt Review — copy into a target skill

Use with `references/adopt-review.md`. Tick in the **target** skill folder. Preflight (`open-review.md` § Preflight) runs this list for **every** skill under the current app’s default skills path before opening Review.

- [ ] `README.md` — required English; intro → `## Install` (English agent prompt: git URL + Steps; no human `git clone`) → `## Features` → `## How to use` → `## Common changes`; no `When` / `How to invoke`, no file-roles or layout table; `[中文](README.zh.md)` after title; no specific agent app name
- [ ] `README.zh.md` — required Chinese; 简介 → `## 安装`（中文 Agent 提示词：仓库地址 + 步骤）→ `## 功能介绍`（能做什么，短列表）→ `## 怎么用`（你说什么 → 会发生什么，何时触发写在引导句里）→ `## 常见改动`（想改什么 → 对 Agent 说的一句话）；不写 `何时` / `怎么调用` / 文件角色 / 目录清单表; `[English](README.md)` after title; 不要用具体 Agent 应用名
- [ ] `review-intro.md` — Chinese plain-text 简介 (no Markdown markers); 不要用具体 Agent 应用名
- [ ] `review-body.md` — `## 能做什么` / `## 执行步骤`（最下；相关度低才拆项；每项都有 `###`，一步也写）；不要用具体 Agent 应用名
- [ ] `review-usage.md` — `## 使用方法`（一句话怎么调用）；`## 功能` 下只有 `####` 命令/参数/脚本/工具（domain skill 不写 `-review` / `/skills-check`）；不要用具体 Agent 应用名
- [ ] `tag.txt` — one line; user-confirmed
- [ ] `SKILL.md` Commands row: `-review` → `scripts/open-review.ps1`
- [ ] Generate opener:

```powershell
python "<skills-check>/scripts/skills-check-viewer.py" --write-open-scripts --print
```

- [ ] Verify `/<skill> -review` (single) and `/skills-check` (overview card)
