## 能做什么

- **Skill 规范**：创建或编辑任何 skill 时，先读本 skill 的 `references/skill-authoring.md`。人类页：英文 `README.md` 与中文 `README.zh.md` 互相入口，排版简介 → 安装 → 具体内容 → 其他；安装是通过 Agent 的一段提示词（仓库地址 + 步骤），英文页用英文、中文页用中文。Review 页是 `review-intro.md`（中文纯文本简介）、`review-body.md`（能做什么 / 执行步骤）、`review-usage.md`（使用方法一句话 + 功能只挂命令/参数/脚本/工具）。不要用具体 Agent 应用名，写成当前 Agent / Agent。缺一份、缺入口、缺安装提示词或顺序不对记为缺件。
- **打开 Review**：`/skills-check` 打开 Skills 总览，`/<skill> -review` 打开该 skill 单页；都会先适配当前 Agent 默认 skill 路径。需关注或缺件时可点「复制提示词」。
- **在总览页管标签**：标签下拉可勾选多个，带其中任一标签的 skill 会显示；卡片右键「编辑标签」直接改该 skill 的标签，保存即写入并刷新。
- **接入 Review**：按清单给未适配的 skill 补人类页和 `-review`；本 skill 常驻，其他 skill 被改时会同步人类页。

## 执行步骤

### Skill 规范

1. **先读规范**：打开 `references/skill-authoring.md`。
2. **再读关联**：读被改 skill 自己的 `cross-reference.md`。
3. **然后落盘**：按规范改文件，并同步该 skill 的 README 与 Review 页（安装提示词按文件语言；不要用具体 Agent 应用名）。

### 打开 Review

1. **先预检**：对当前 Agent 默认 skills 路径跑 `--print`，缺件当场补齐。
2. **再打开**：总览用 `/skills-check`，单页用 `/<skill> -review`。
3. **然后看问题**：需关注或缺件时先看标题栏；要修则点「复制提示词」。

### 在总览页管标签

1. **先筛**：打开标签下拉，勾选一个或多个标签；要还原就点旁边的「清除筛选」。
2. **再改**：在卡片上右键，选「编辑标签」。
3. **然后保存**：删掉不要的、点已有标签加入或回车新建，点「保存」写入并刷新。

### 接入 Review

1. **先对清单**：按 `adopt-review.md` 看缺哪些文件。
2. **再抽已有内容**：从该 skill 的 `SKILL.md` / `README.md` / `README.zh.md` 写出人类页，不编造流程。
3. **然后接线**：补 `SKILL.md` 的 `-review` 行，用 `--write-open-scripts` 生成 `open-review.ps1`。
