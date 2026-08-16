# skills-check

[English](README.md)

技能形态规范，以及当前 Agent 默认 skills 路径下的飞书风格 Review。它让每个 skill 保持同一种形态，并给你一个页面看清哪些 skill 健康、哪些缺件。

## 安装

通过 Agent 安装。把下面代码块整段交给当前 Agent。

```
请把 skill「skills-check」安装到你当前所在的 Agent 应用。
仓库：https://github.com/jeffrey0328/skills-check.git
步骤：
1. 先读取并遵守你当前这个 Agent 的 skill 规范（安装目录、frontmatter、挂载方式、项目指针、人类页要求）。未读到该规范之前不要改文件。不要凭记忆套用某一个 Agent 产品的路径和字段。
2. 按该规范把该仓库克隆到当前 Agent 的默认 skills 路径，文件夹名用「skills-check」。
3. 再按该规范改本 skill 里需要对接到当前 Agent 的部分。不要通读 references/、review-body.md、examples/ 里的流程正文。
```

## 功能介绍

- 管每个 skill 必须怎么写：创建或编辑时先按统一形态落盘，人类页和 Review 页一起齐。
- 打开 Skills 总览和单个 skill 的 Review 页：先体检整套 skill，再打开页面。
- 在总览页按标签筛选，右键卡片改标签，保存即写入。
- 给还没接入 Review 的 skill 补齐配套文件和它自己的 `-review`。

## 怎么用

**常驻** —— 每轮对话 Agent 自己会挂载，不需要你 `@`。只要有 skill 被创建或修改（Agent 动手前先读编写规范），或者你想看 skill 的状态，它就会生效。仍然可以说 `/skills-check` 或 `@skills-check`。

| 你说 | 会发生什么 |
|------|------------|
| `/skills-check` | 先体检全部 skill，再打开 Skills 总览（下拉勾选标签筛选，右键卡片改标签） |
| `/<任一 skill> -review` | 先体检全部 skill，再打开那一个 skill 的页面 |
| 「建一个 skill 做…」/「改一下这个 skill」 | Agent 按形态规范写，并同步给人看的页面 |
| 「把 `<skill>` 接入 Review」 | 给那个 skill 补齐配套文件和它自己的 `-review` |

## 常见改动

下面这些话直接对 Agent 说，它自己去找并改对应文件。

| 想改什么 | 对 Agent 说 |
|----------|-------------|
| skill 编写规范（任何 skill 必须怎么写） | 「改一下 skill 编写规范：`<新要求>`，并铺开到每个 skill」 |
| Review 检查标准（什么算缺件、什么算需关注） | 「Review 体检加一条：`<规则>`，算缺件 / 需关注」 |
| 某个 skill 的 Review 页内容（简介 / 能做什么 / 使用方法） | 「把 `<skill>` 的 Review 简介改成 `<内容>`」 |
| skill 卡片上显示的标签 | 在总览页右键那张卡片选「编辑标签」直接改；或说「把 `<skill>` 的标签改成 `<标签>`」 |
| 标签词表里的候选标签 | 「标签词表加上 `<标签>`，把 `<旧标签>` 去掉」 |
| Review 用哪里打开（内置 / 外部浏览器、端口） | 「Review 用外部浏览器打开」/「Review 换成 `<端口>` 端口」 |
| 一条要全套 skill 一起遵守的约定（配套文件、hub 形态） | 「`<新约定>`，全部 skill 都改，不只这一个」 |
