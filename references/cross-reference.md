# 关联记录 / Cross-reference map

Records **who references each tracked file** and whether the reference is to the **whole file (整篇)** or a **specific section (§)**.

**读法:** Grep `^## ` for the target filename, then read only its row group.

## Maintenance rule (required)

- **Before editing** any file listed below (rename, move, delete, or rename/remove a `##` / `§` heading that appears in the 范围 column), **read this record first** and update every listed referencer.
- **After editing**, keep this record in sync.
- **Scope of tracking:** all `references/*.md`, `scripts/*`, `examples/*`, and `tag.txt`. `SKILL.md` / `README.md` / `README.zh.md` / `review-*.md` appear as **referencers** only.

## references/

### cross-reference.md (this file)
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Route「Editing…」+ Always | 整篇 |
| `hub-norms.md` (top table + File index + Must + DoD) | 整篇 |

### open-review.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Commands + Route「总览 / -review」+ Always | § Preflight / § Overview / § Single |
| `hub-norms.md` File index + Must | 整篇 + § Preflight |
| `review-body.md` 能做什么 · 打开 Review | § Preflight / § Overview / § Single |
| `adopt-review.md` Verify | § Single |
| `sync-on-update.md` After sync | 整篇 |

### adopt-review.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Route「接入 / 改造」| 整篇 |
| `open-review.md` § Preflight | § Fleet adapt |
| `hub-norms.md` File index + Must | 整篇 |
| `review-body.md` 执行步骤 · 接入 Review | 整篇 |
| `sync-on-update.md` § New skill | 整篇 |
| `examples/adopt-checklist.md` | 整篇 |

### sync-on-update.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Route「本轮被创建或修改」+ Always「Resident」| § Resident + 整篇 |
| `hub-norms.md` File index + Must | 整篇 |
| `review-body.md` 能做什么 · 接入 Review | 整篇 |

### skill-authoring.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Route「Create/update Skill」+ Always「Authoring」| 整篇 + § Install prompt |
| `hub-norms.md` File index + Must + DoD | 整篇 |
| `adopt-review.md` 读法 + § Checklist | 整篇 + § Three layers / § Synchronize / § Positive / negative |
| `open-review.md` | 整篇 |
| `sync-on-update.md` | § Synchronize companion files |
| `review-body.md` 能做什么 / 执行步骤 | 整篇 |
| `examples/three-layer-layout.md` | § Three layers |
| `scripts/skills-check-viewer.py` | § Three layers / § Positive / negative norms |

### hub-norms.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Route「Norms/DoD」+ Always | 整篇 |

## scripts/

### skills-check-viewer.py
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` (via `open-review.md`) | 调用 (整篇) |
| `open-review.md` § Overview / § Single / § Ensure | 调用 (整篇) |
| `adopt-review.md` § Generate opener | 调用 (`--write-open-scripts`) |
| `sync-on-update.md` § Review skill update | 调用 (整篇) |
| `scripts/open-review.ps1` | 调用 (整篇) |
| **Parses:** each skill’s `review-intro.md`, `review-body.md`, `review-usage.md`, `tag.txt`, `SKILL.md`, `README.md`, `README.zh.md` | 解析 |
| **Generates:** each skill’s `scripts/open-review.ps1` | 生成 |
| **Writes (`POST /api/tag`):** each skill’s `tag.txt` + this skill’s `tag-vocab.txt` | 写入 |

### open-review.ps1
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` `-review` | 调用 (整篇) |
| `open-review.md` § Single | 调用 (整篇) |
| Generated/overwritten by `skills-check-viewer.py --write-open-scripts` | 被生成 |

## examples/

### adopt-checklist.md
| Referenced by | 范围 |
|---------------|------|
| `hub-norms.md` File index | 整篇 |
| `adopt-review.md` | 整篇 |

### three-layer-layout.md
| Referenced by | 范围 |
|---------------|------|
| `SKILL.md` Layers 表 | 整篇 |
| `adopt-review.md` § Checklist | 整篇 |

## tag.txt
| Referenced by | 范围 |
|---------------|------|
| `scripts/skills-check-viewer.py` | 解析 + 写入 (整篇) |
| `hub-norms.md` File index | 整篇 |
| `skill-authoring.md` § Tag | 整篇 |

## tag-vocab.txt
| Referenced by | 范围 |
|---------------|------|
| `scripts/skills-check-viewer.py` | 读取 + 追加 (整篇) |
| `skill-authoring.md` § Tag | 整篇 |
| `hub-norms.md` File index | 整篇 |
| `open-review.md` § Views (Tag hook) | 整篇 |
