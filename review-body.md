## 能做什么

- **Skill 规范**：
  - 管每个 skill 必须怎么写：形态规范在 `references/skill-authoring.md`
  - 不要用具体 Agent 应用名，写成当前 Agent / Agent
- **打开 Review**：
  - 两种页面：Skills 总览，和单个 skill 的 Review
  - 总览体检并适配当前 Agent 默认 skills 路径下的全部 skill；单页只体检、只补这一个
  - 需关注或缺件时，标题栏下列问题，可复制修复提示词去粘贴
- **在总览页管标签**：
  - 总览可以按标签筛选，多选为任一命中
  - 改标签写入该 skill 的 `tag.txt`，卡片和筛选立刻刷新；清空则删除该文件
- **接入 Review**：
  - 给还没接入的 skill 补齐 Review 配套和它自己的 `-review`
  - 只从该 skill 已有文件抽取，不编造流程
  - 本 skill 常驻，其他 skill 被改时会同步配套

## 执行步骤

### Skill 规范

1. **先读规范**：打开 `references/skill-authoring.md`。
2. **再读关联**：读被改 skill 自己的 `cross-reference.md`。
3. **然后落盘**：按规范改文件，并同步该 skill 的 README 与 Review 页（安装提示词按文件语言；不要用具体 Agent 应用名）。

### 打开 Review

1. **先预检**：总览对当前 Agent 默认 skills 路径跑 `--print`，缺件当场补齐。单页 `-review` 用 `--print --skill`，只检查、只补那一个 skill。
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
