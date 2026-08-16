# Case: required three-layer tree

**When:** creating a skill or Preflight finds a missing layer. Optional extras only if that skill’s work needs them.

```
<skill>/
├── SKILL.md                 # 1 Index — Route / Commands + Layers table
├── references/              # 2 Content — playbooks (or modules/ / standards/)
│   └── <workflow>.md
├── examples/                # 3 Cases — worked example or case-index.md
│   └── case-index.md
├── README.md
├── README.zh.md
├── review-intro.md          # Review (optional extra, required for Feishu)
├── review-body.md
├── review-usage.md
├── tag.txt
├── scripts/                 # tools / code — only if Commands need them
└── tools/
```

Adopt Review checklist: `examples/adopt-checklist.md`.
