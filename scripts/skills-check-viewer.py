#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描当前 Agent 默认 skills 路径下的个人 Agent Skill，用本地 HTTP 打开飞书风格 Review
（默认 http://127.0.0.1:18765/；Ctrl+C 结束）：

  1) 总览：状态卡 + 每个 skill 的状态 / 问题 / 一句简介
  2) 单 skill：同风格独立页 — 能做什么 / 怎么用 / 执行步骤；页内可切换 skill

对照 skill-authoring 规范做健康检查（只读，不改文件）。

/skills-check 或 /<skill> -review（本脚本启动）会先结束旧 Review 进程再加载最新 .py，并尽量占用 18765。
浏览器刷新只重扫 skill 文件，不重载本脚本。

用法:
  python skills-check-viewer.py
  python skills-check-viewer.py "C:\\Users\\...\\skills"
  python skills-check-viewer.py --skill "C:\\Users\\...\\skills\\ue-dev-skill"
  python skills-check-viewer.py --port 18765
  python skills-check-viewer.py --no-browser
  python skills-check-viewer.py --print
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

DEFAULT_PORT = 18765
SKIP_DIRS = {"logs", "scripts", ".git"}
# Legacy review.html section ids (still mined for content)
LEGACY_SECTION_IDS = ("can-do", "steps", "contents", "examples")
AUTO_INVOKE_OK = {
    "user-profile",
    "jeffrey-workflow-skill",
    "video-creator-skill",
    "skills-check",
}
LARGE_SKILL_LINES = 180
VIEWER_PROC_MARK = "skills-check-viewer"
# Shared tag vocabulary (candidates for the overview tag editor / filter)
TAG_VOCAB_PATH = Path(__file__).resolve().parent.parent / "tag-vocab.txt"
MAX_TAGS_PER_SKILL = 8
MAX_TAG_VOCAB = 200
MAX_TAG_LEN = 24

# Positive/negative norm pairing (skill-authoring.md § Positive / negative norms)
_POS_HEADING = re.compile(
    r"(?im)^#{2,4}\s+(Must|Do|Always|应当|必须|要)\b(?!\s*not\b)"
)
_NEG_HEADING = re.compile(
    r"(?im)^#{2,4}\s+(Must\s+not|Do\s+not|Never|禁止|不要|勿)\b"
)
_NEG_BULLET_START = re.compile(
    r"(?im)^\s*[-*]\s+(?:Do\s+not|Don't|Never|禁止|不要|不允许|勿)\b"
)
_ANY_BULLET = re.compile(r"(?m)^\s*[-*]\s+(.+)$")
_ANY_NUMBERED = re.compile(r"(?m)^\s*\d+\.\s+(.+)$")
_PAIR_MARK = re.compile(r"(←|overlaps|配对|\(←|←\s*Must)", re.I)
# Inline / parenthetical negatives in Review prose (review-body etc.)
_PAREN_NEG = re.compile(
    r"[（(]\s*((?:勿|不要|禁止|不得|不可|别|Do\s+not|Don't|Never)[^）)]*)[）)]",
    re.I,
)
_INLINE_NEG = re.compile(
    r"(?:勿|不要|禁止|不得|不允许|Never\b|Do\s+not\b|Don't\b)",
    re.I,
)
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "when", "only", "into",
    "your", "user", "must", "not", "dont", "don't", "never", "without", "unless",
    "see", "per", "via", "any", "all", "file", "files", "skill", "skills",
    "以及", "或者", "如果", "可以", "进行", "使用", "相关", "内容", "文件",
}


def _norm_tokens(text: str) -> set[str]:
    t = text.lower()
    t = re.sub(r"`[^`]+`", " ", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", t, flags=re.UNICODE)
    out: set[str] = set()
    for w in t.split():
        if w in _STOP or len(w) < 3:
            continue
        out.add(w)
    # CJK bigrams for short Chinese phrases
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for phrase in cjk:
        if len(phrase) >= 2:
            out.add(phrase)
        for i in range(len(phrase) - 1):
            out.add(phrase[i : i + 2])
    return out


def _split_md_sections(text: str) -> list[tuple[str, str]]:
    """Return [(heading_line, body), ...] including a leading '' section."""
    if not text:
        return []
    parts = re.split(r"(?m)^(#{2,4}\s+.+)$", text)
    if len(parts) == 1:
        return [("", parts[0])]
    out: list[tuple[str, str]] = []
    if parts[0].strip():
        out.append(("", parts[0]))
    i = 1
    while i + 1 < len(parts):
        out.append((parts[i].strip(), parts[i + 1]))
        i += 2
    return out


def _strip_fenced_code(text: str) -> str:
    """Drop ``` ... ``` blocks so template/example Must not does not false-warn."""
    return re.sub(r"```[\s\S]*?```", "\n", text or "")


def _section_bullets(body: str) -> list[str]:
    return [m.group(1).strip() for m in _ANY_BULLET.finditer(body or "")]


def _tokens_overlap(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = a & b
    if len(inter) >= 2:
        return True
    # one strong shared token (path-ish / long)
    return any(len(t) >= 6 for t in inter)


def check_pos_neg_pairing(docs: dict[str, str]) -> tuple[str, str]:
    """
    Warn (需关注) when negatives lack an overlapping Must, or when README/prose
    uses a parenthetical 勿/不要 that the same sentence's affirmative already covers.
    Also scans list items in README / SKILL / references — not only ## Must not.
    """
    orphans: list[str] = []

    for rel, text in docs.items():
        if not (text or "").strip():
            continue
        text = _strip_fenced_code(text)
        sections = _split_md_sections(text)
        must_bullets: list[str] = []
        for heading, body in sections:
            if heading and _POS_HEADING.match(heading) and not re.search(
                r"(?i)must\s+not|do\s+not|禁止", heading
            ):
                must_bullets.extend(_section_bullets(body))
            for m in re.finditer(
                r"(?im)^\s*[-*]\s+\*\*(?:Must|Do|应当|必须)\*\*\s*[:：]?\s*(.+)$",
                body or "",
            ):
                must_bullets.append(m.group(0))

        must_toks = [_norm_tokens(b) for b in must_bullets]

        def paired(neg: str) -> bool:
            if _PAIR_MARK.search(neg):
                return True
            nt = _norm_tokens(neg)
            return any(_tokens_overlap(nt, mt) for mt in must_toks if mt)

        def same_line_has_affirmative(line: str, neg_span: str) -> bool:
            """Positive residue after stripping the negative fragment."""
            rest = line
            for m in _PAREN_NEG.finditer(line):
                rest = rest.replace(m.group(0), " ")
            rest = _INLINE_NEG.sub(" ", rest)
            # Affirmative cues in Chinese/English norms
            if re.search(
                r"(默认|应当|必须|优先|只用|仅在|仅当|使用|用|写|执行|打开|同步|读)",
                rest,
            ):
                return True
            if re.search(r"\b(must|should|prefer|use|only|default)\b", rest, re.I):
                return True
            return bool(_norm_tokens(rest) & _norm_tokens(neg_span))

        for heading, body in sections:
            is_neg_sec = bool(heading and _NEG_HEADING.match(heading))
            bullets = _section_bullets(body)
            if is_neg_sec:
                if not must_bullets and bullets:
                    for b in bullets[:5]:
                        orphans.append(f"{rel}: {one_line(b, 60)}")
                    continue
                for b in bullets:
                    if not paired(b):
                        orphans.append(f"{rel}: {one_line(b, 60)}")
                continue

            # Prose / list lines (能做什么、执行步骤、以及其它正文)
            lines: list[str] = []
            lines.extend(_section_bullets(body))
            lines.extend(m.group(1).strip() for m in _ANY_NUMBERED.finditer(body or ""))
            for raw in (body or "").splitlines():
                s = raw.strip()
                if s and not s.startswith("#") and not s.startswith("|"):
                    if _NEG_BULLET_START.match(raw) or _PAREN_NEG.search(s) or (
                        _INLINE_NEG.search(s) and (s.startswith("-") or s.startswith("*") or re.match(r"^\d+\.", s))
                    ):
                        if s.lstrip("-* ").strip() not in lines:
                            lines.append(s.lstrip("-*0123456789. ").strip())

            for b in lines:
                # Parenthetical 勿…：同句已有肯定 → 多余否定，需关注（建议只留肯定）
                for pm in _PAREN_NEG.finditer(b):
                    neg_bit = pm.group(1).strip()
                    if same_line_has_affirmative(b, neg_bit):
                        orphans.append(
                            f"{rel}: 括号否定多余「{one_line(neg_bit, 40)}」— 同句已有肯定，建议只留肯定句"
                        )
                    elif not paired(b):
                        orphans.append(f"{rel}: {one_line(b, 60)}")

                if _NEG_BULLET_START.match(f"- {b}") or (
                    _INLINE_NEG.search(b) and not _PAREN_NEG.search(b)
                ):
                    # Leading / mid-line negative without file-level Must overlap
                    if _PAIR_MARK.search(b):
                        continue
                    if paired(b):
                        continue
                    # Same-bullet affirmative covering the negative → OK under pairing rule
                    if same_line_has_affirmative(b, b) and _INLINE_NEG.search(b):
                        # Still OK if clearly paired in-sentence; do not orphan
                        continue
                    orphans.append(f"{rel}: {one_line(b, 60)}")

    if not orphans:
        return "pass", "否定句均有重合的肯定句（或无否定句）"

    seen: set[str] = set()
    uniq: list[str] = []
    for o in orphans:
        if o in seen:
            continue
        seen.add(o)
        uniq.append(o)

    preview = "；".join(uniq[:4])
    extra = f" 等共 {len(uniq)} 条" if len(uniq) > 4 else ""
    return (
        "warn",
        f"否定句缺少重合的肯定句（需关注）— {preview}{extra}",
    )


def default_skills_root() -> Path:
    # this file: <skills-root>/<this-skill>/scripts/skills-check-viewer.py
    return Path(__file__).resolve().parents[2]


def forbidden_app_name_re() -> re.Pattern[str]:
    spec = Path(__file__).resolve().parents[1] / "references" / "skill-authoring.md"
    text = spec.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"(?ms)^##\s+Agent-app names \(forbidden\)\s*\n(.*?)(?=^##\s+|\Z)",
        text,
    )
    section = m.group(1) if m else ""
    line = re.search(r"Forbidden names[^:]+:\s*(.+?)(?:—|\n)", section)
    raw = line.group(1) if line else ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    alts = [re.escape(p).replace(r"\ ", r"[\s-]*") for p in parts]
    if not alts:
        raise RuntimeError("skill-authoring.md missing Agent-app names list")
    return re.compile(r"(?i)(" + "|".join(alts) + r")")


def parse_frontmatter(text: str) -> dict:
    text = text.lstrip("\ufeff").lstrip()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end].strip("\n")
    data: dict = {}
    key = None
    buf: list[str] = []
    folded = False
    for line in block.splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:", line) and not line.startswith(" "):
            if key is not None:
                data[key] = "\n".join(buf).strip().strip("\"'")
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest in (">-", ">", "|"):
                buf = []
                folded = True
            else:
                buf = [rest] if rest else []
                folded = False
        elif key is not None:
            if folded:
                if line.strip() == "":
                    continue
                buf.append(line.strip())
            else:
                if line.strip() == "" and not buf:
                    continue
                buf.append(line.strip())
    if key is not None:
        data[key] = "\n".join(buf).strip().strip("\"'")
    return data


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def strip_md_markers(text: str) -> str:
    """简介等纯展示文案：去掉 **bold** / `code` / 残留 *，保留正文。"""
    t = text or ""
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", t)
    return t.strip()


def one_line(text: str, limit: int = 100) -> str:
    text = re.sub(r"\s+", " ", strip_md_markers(text or "").strip())
    if not text:
        return ""
    for sep in ("。", ". ", "；", "; "):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            if sep.startswith("."):
                text = text.rstrip(".")
            break
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def strip_tags(fragment: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", "", fragment, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", "", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def md_inline_to_html(text: str) -> str:
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def md_block_to_html(md: str) -> str:
    """Minimal markdown → HTML for README / SKILL snippets."""
    if not (md or "").strip():
        return ""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    in_ul = False
    in_ol = False
    in_table = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            # numbered markdown is emitted as <ul>; keep closer safe
            out.append("</ul>")
            in_ol = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            close_lists()
            close_table()
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(
                    lines[i]
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                i += 1
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
            if i < len(lines):
                i += 1
            continue

        if re.match(r"^\|.+\|$", stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in cells):
                i += 1
                continue
            if not in_table:
                close_lists()
                out.append("<table><tbody>")
                in_table = True
                out.append(
                    "<tr>"
                    + "".join(f"<th>{md_inline_to_html(c)}</th>" for c in cells)
                    + "</tr>"
                )
            else:
                out.append(
                    "<tr>"
                    + "".join(f"<td>{md_inline_to_html(c)}</td>" for c in cells)
                    + "</tr>"
                )
            i += 1
            continue
        else:
            close_table()

        m_h = re.match(r"^(#{2,4})\s+(.+)$", stripped)
        if m_h:
            close_lists()
            level = len(m_h.group(1))
            out.append(f"<h{level}>{md_inline_to_html(m_h.group(2))}</h{level}>")
            i += 1
            continue

        m_ul = re.match(r"^[-*]\s+(.+)$", stripped)
        if m_ul:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline_to_html(m_ul.group(1))}</li>")
            i += 1
            continue

        m_ol = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if m_ol:
            # Always bullets — never mix ol/ul in the Review page.
            if in_ol:
                out.append("</ul>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline_to_html(m_ol.group(1))}</li>")
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        close_lists()
        out.append(f"<p>{md_inline_to_html(stripped)}</p>")
        i += 1

    close_lists()
    close_table()
    return "\n".join(out)


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def strip_empty_usage_h2(md: str) -> str:
    """Drop ## sections whose body is empty or only 无 / 无。"""
    text = (md or "").lstrip("\ufeff")
    parts = re.split(r"(?m)^(##\s+.+)$", text)
    if len(parts) < 3:
        return text.strip()
    out: list[str] = []
    if parts[0].strip():
        out.append(parts[0].strip())
    for i in range(1, len(parts), 2):
        heading = parts[i].rstrip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        compact = re.sub(r"\s+", "", body)
        if not compact or compact in ("无", "无。", "无。"):
            continue
        if re.fullmatch(r"无。?", body.strip()):
            continue
        out.append(heading)
        out.append(body)
    return "\n\n".join(out).strip()


def parse_md_h2_sections(text: str) -> dict[str, str]:
    text = text.lstrip("\ufeff")
    parts = re.split(r"(?m)^##\s+(.+)$", text)
    # parts[0]=preamble, then title, body, title, body...
    sections: dict[str, str] = {}
    if len(parts) < 3:
        if parts and parts[0].strip():
            sections["_preamble"] = parts[0].strip()
        return sections
    if parts[0].strip():
        sections["_preamble"] = parts[0].strip()
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections[title] = body
    return sections


def pick_md_section(sections: dict[str, str], keywords: tuple[str, ...]) -> str:
    for title, body in sections.items():
        if title == "_preamble":
            continue
        t = title.lower()
        for kw in keywords:
            if kw.lower() in t:
                return body
    return ""


def cards_from_md_body(md: str, default_title: str = "") -> list[dict]:
    """L2 by ### headings only. Lists, steps, and tables stay inside the card."""
    md = (md or "").strip()
    if not md:
        return []
    h3_parts = re.split(r"(?m)^###\s+(.+)$", md)
    if len(h3_parts) >= 3:
        cards: list[dict] = []
        if h3_parts[0].strip():
            cards.append(
                {
                    "title": default_title,
                    "html": normalize_prose_html(md_block_to_html(h3_parts[0].strip())),
                }
            )
        for i in range(1, len(h3_parts), 2):
            title = h3_parts[i].strip()
            body = h3_parts[i + 1].strip() if i + 1 < len(h3_parts) else ""
            cards.append(
                {
                    "title": title,
                    "html": normalize_prose_html(md_block_to_html(body)) if body else "",
                }
            )
        return cards
    return [
        {
            "title": default_title,
            "html": normalize_prose_html(md_block_to_html(md)),
        }
    ]


_BOLD_LEAD = re.compile(r"^[-*]\s+\*\*([^*]+)\*\*\s*[:：]?\s*(.*)$")


def parse_can_do_items(md: str) -> list[dict]:
    """Split 能做什么 into titled items (### or **Title**： bullets)."""
    md = (md or "").strip()
    if not md:
        return []
    h3_parts = re.split(r"(?m)^###\s+(.+)$", md)
    if len(h3_parts) >= 3:
        items: list[dict] = []
        for i in range(1, len(h3_parts), 2):
            title = h3_parts[i].strip()
            body = h3_parts[i + 1].strip() if i + 1 < len(h3_parts) else ""
            items.append(
                {
                    "title": title,
                    "html": normalize_prose_html(md_block_to_html(body or title)),
                }
            )
        return items
    items = []
    for line in md.splitlines():
        m = _BOLD_LEAD.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        rest = m.group(2).strip()
        items.append(
            {
                "title": title,
                "html": normalize_prose_html(md_block_to_html(rest or title)),
            }
        )
    return items


def _match_execute_card(title: str, exe_map: dict[str, dict]) -> dict | None:
    if title in exe_map:
        return exe_map[title]
    for key, card in exe_map.items():
        if title in key or key in title:
            return card
    return None


def build_capabilities(can_src: str, exe_src: str) -> list[dict]:
    """Pair each 能做什么 item with its ## 执行步骤 subsection."""
    can_items = parse_can_do_items(can_src)
    exe_cards = cards_from_md_body(exe_src, "") if exe_src and has_cjk(exe_src) else []
    exe_map = {
        (card.get("title") or "").strip(): card
        for card in exe_cards
        if (card.get("title") or "").strip()
    }
    caps: list[dict] = []
    used: set[str] = set()
    if can_items:
        for i, item in enumerate(can_items):
            title = item["title"]
            exe = _match_execute_card(title, exe_map)
            if exe:
                used.add((exe.get("title") or title).strip())
            caps.append(
                {
                    "id": f"cap-{i}",
                    "title": title,
                    "can_do_html": item["html"],
                    "execute_html": (exe or {}).get("html") or "",
                }
            )
        for card in exe_cards:
            title = (card.get("title") or "").strip()
            if not title or title in used:
                continue
            if any(title == c["title"] or title in c["title"] or c["title"] in title for c in caps):
                continue
            caps.append(
                {
                    "id": f"cap-x-{len(caps)}",
                    "title": title,
                    "can_do_html": "",
                    "execute_html": card.get("html") or "",
                }
            )
        return caps
    for i, card in enumerate(exe_cards):
        title = (card.get("title") or f"步骤 {i + 1}").strip()
        caps.append(
            {
                "id": f"cap-{i}",
                "title": title,
                "can_do_html": "",
                "execute_html": card.get("html") or "",
            }
        )
    return caps


_USAGE_H2_TITLE = {
    "使用方法": "",
    "对话里输入什么": "",
    "功能": "",
    "子指令": "",
}
_USAGE_KINDS = ("命令", "参数", "脚本", "工具")

def _kind_from_table_header(header: str) -> str | None:
    cells = [c.strip().strip("`") for c in header.strip().strip("|").split("|")]
    if not cells:
        return None
    first = cells[0]
    if first in _USAGE_KINDS:
        return first
    if first == "输入":
        return "命令"
    return None


_ASSET_ITEM = re.compile(r"^[-*]\s+")


def _is_scripts_tools_section(title: str) -> bool:
    return ("脚本" in title and "工具" in title) or title in ("脚本", "工具")


def _classify_asset_line(line: str) -> str | None:
    """'tool' | 'script' for a list item; None if not an item."""
    stripped = line.strip()
    if not stripped or not _ASSET_ITEM.match(stripped):
        return None
    if re.search(r"tools/", stripped, re.I):
        return "tool"
    return "script"


def _cards_from_scripts_and_tools(body: str) -> list[dict]:
    scripts: list[str] = []
    tools: list[str] = []
    other: list[str] = []
    for line in body.splitlines():
        kind = _classify_asset_line(line)
        if kind == "tool":
            tools.append(line)
        elif kind == "script":
            scripts.append(line)
        elif line.strip():
            other.append(line)
    cards: list[dict] = []
    if scripts:
        cards.append(
            {
                "title": "脚本",
                "html": normalize_prose_html(md_block_to_html("\n".join(scripts))),
            }
        )
    if tools:
        cards.append(
            {
                "title": "工具",
                "html": normalize_prose_html(md_block_to_html("\n".join(tools))),
            }
        )
    if other:
        extra = normalize_prose_html(md_block_to_html("\n".join(other)))
        if cards:
            cards[-1]["html"] = (cards[-1]["html"] + extra).strip()
        else:
            cards.append({"title": "脚本和工具", "html": extra})
    return cards


def usage_inner_cards(usage_md: str) -> list[dict]:
    """怎么用 L2：按使用方法 / 指令 / 脚本 / 工具等类别拆，不把条目或表格行打散成卡。"""
    secs = parse_md_h2_sections(usage_md)
    cards: list[dict] = []
    for title, body in secs.items():
        if not (body or "").strip():
            continue
        if title in _USAGE_HIDE_H2 or _is_scripts_tools_section(title):
            continue
        if title in _USAGE_ALWAYS_COMMON:
            continue
        if title == "_preamble":
            cards.append(
                {
                    "title": "说明",
                    "html": normalize_prose_html(md_block_to_html(body)),
                }
            )
            continue
        cards.append(
            {
                "title": _USAGE_H2_TITLE.get(title, title),
                "html": normalize_prose_html(md_block_to_html(body)),
            }
        )
    return cards


_USAGE_ALWAYS_COMMON = {"使用方法", "对话里输入什么", "项目中怎么自动调用"}
_USAGE_HIDE_H2 = {"脚本和工具", "脚本", "工具", "description 内容"}


def usage_prose_html(usage_md: str) -> str:
    """## 使用方法 body as one prose block."""
    secs = parse_md_h2_sections(usage_md)
    body = secs.get("使用方法") or secs.get("对话里输入什么") or ""
    if not (body or "").strip():
        return ""
    return normalize_prose_html(md_block_to_html(body))
_CAP_KEY_STOP = {
    "打开", "接入", "这个", "什么", "怎么", "skill", "review", "本页",
    "script", "scripts",
}


def _is_table_sep(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in cells)


def _distinct_cap_keys(title: str) -> list[str]:
    keys: list[str] = []
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", title or ""):
        if len(phrase) >= 4:
            keys.append(phrase[:2])
            keys.append(phrase[-2:])
        else:
            keys.append(phrase)
    for word in re.findall(r"[A-Za-z]{4,}", title or ""):
        if word.lower() not in _CAP_KEY_STOP:
            keys.append(word)
    keys = [k for k in keys if k.lower() not in _CAP_KEY_STOP]
    return keys or ([title.strip()] if (title or "").strip() else [])


def _key_in_text(key: str, text: str) -> bool:
    if re.fullmatch(r"[A-Za-z]+", key):
        return bool(re.search(rf"(?<![A-Za-z]){re.escape(key)}(?![A-Za-z])", text, re.I))
    return key in text


def _caps_hit_by_text(text: str, titles: list[str]) -> list[str]:
    hits: list[str] = []
    for title in titles:
        if not title:
            continue
        if title in text:
            hits.append(title)
            continue
        keys = _distinct_cap_keys(title)
        if keys and all(_key_in_text(k, text) for k in keys):
            hits.append(title)
    return hits


def _best_cap_title(text: str, titles: list[str]) -> str | None:
    if not text or not titles:
        return None
    scored: list[tuple[int, str]] = []
    for title in titles:
        if not title:
            continue
        if title in text:
            scored.append((100 + len(title), title))
            continue
        keys = _distinct_cap_keys(title)
        if not keys:
            continue
        hits = [k for k in keys if k in text]
        if not hits:
            continue
        scored.append((sum(len(k) for k in hits), title))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _atoms_from_flat(category: str, body: str, cap_hint: str | None) -> list[dict]:
    atoms: list[dict] = []
    table_buf: list[str] = []
    prose_buf: list[str] = []

    def flush_table() -> None:
        nonlocal table_buf
        if not table_buf:
            return
        header = table_buf[0]
        sep = ""
        rows = table_buf[1:]
        if rows and _is_table_sep(rows[0]):
            sep = rows[0]
            rows = rows[1:]
        if not rows:
            prose_buf.extend(table_buf)
            table_buf = []
            return
        md = "\n".join(table_buf)
        kind = _kind_from_table_header(header) or category
        atoms.append(
            {
                "category": kind,
                "cap_hint": cap_hint,
                "kind": "table",
                "text": md,
                "md": md,
            }
        )
        table_buf = []

    def flush_prose() -> None:
        nonlocal prose_buf
        text = "\n".join(prose_buf).strip()
        prose_buf = []
        if not text:
            return
        atoms.append(
            {
                "category": category,
                "cap_hint": cap_hint,
                "kind": "prose",
                "text": text,
                "md": text,
            }
        )

    for raw in (body or "").splitlines():
        stripped = raw.strip()
        if re.match(r"^\|.+\|$", stripped):
            flush_prose()
            table_buf.append(stripped)
            continue
        if table_buf:
            flush_table()
        if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+[.)]\s+", stripped):
            flush_prose()
            atoms.append(
                {
                    "category": category,
                    "cap_hint": cap_hint,
                    "kind": "bullet",
                    "text": stripped,
                    "md": stripped,
                }
            )
            continue
        if not stripped:
            flush_prose()
            continue
        prose_buf.append(raw)
    flush_table()
    flush_prose()
    return atoms


def _usage_atoms(usage_md: str) -> list[dict]:
    secs = parse_md_h2_sections(usage_md)
    atoms: list[dict] = []
    for title, body in secs.items():
        if not (body or "").strip():
            continue
        if title in _USAGE_HIDE_H2 or _is_scripts_tools_section(title):
            continue
        if title in _USAGE_ALWAYS_COMMON:
            continue
        if title == "_preamble":
            category = "说明"
        else:
            category = _USAGE_H2_TITLE.get(title, title)
        force_common = title in _USAGE_ALWAYS_COMMON
        h3_parts = re.split(r"(?m)^###\s+(.+)$", body)
        if len(h3_parts) >= 3:
            if h3_parts[0].strip():
                chunk = _atoms_from_kind_body(category, h3_parts[0], None)
                if force_common:
                    for atom in chunk:
                        atom["force_common"] = True
                atoms.extend(chunk)
            for i in range(1, len(h3_parts), 2):
                hint = h3_parts[i].strip()
                chunk = _atoms_from_kind_body(
                    category, h3_parts[i + 1] if i + 1 < len(h3_parts) else "", hint
                )
                if force_common:
                    for atom in chunk:
                        atom["force_common"] = True
                atoms.extend(chunk)
            continue
        chunk = _atoms_from_kind_body(category, body, None)
        if force_common:
            for atom in chunk:
                atom["force_common"] = True
        atoms.extend(chunk)
    return atoms


def _atoms_from_kind_body(
    default_cat: str, body: str, cap_hint: str | None
) -> list[dict]:
    """Split #### 命令/参数/脚本/工具; otherwise infer from table header."""
    h4_parts = re.split(r"(?m)^####\s+(.+)$", body)
    if len(h4_parts) < 3:
        return _retag_usage_kinds(_atoms_from_flat(default_cat, body, cap_hint))
    atoms: list[dict] = []
    if h4_parts[0].strip():
        atoms.extend(_retag_usage_kinds(_atoms_from_flat(default_cat, h4_parts[0], cap_hint)))
    for i in range(1, len(h4_parts), 2):
        kind = h4_parts[i].strip()
        cat = kind if kind in _USAGE_KINDS else default_cat
        chunk = _atoms_from_flat(
            cat, h4_parts[i + 1] if i + 1 < len(h4_parts) else "", cap_hint
        )
        if cat in _USAGE_KINDS:
            for atom in chunk:
                atom["category"] = cat
        else:
            _retag_usage_kinds(chunk)
        atoms.extend(chunk)
    return atoms


def _retag_usage_kinds(atoms: list[dict]) -> list[dict]:
    for atom in atoms:
        cat = (atom.get("category") or "").strip()
        if cat in _USAGE_KINDS:
            continue
        inferred = None
        if atom.get("kind") == "table":
            first = (atom.get("md") or "").splitlines()[0] if atom.get("md") else ""
            inferred = _kind_from_table_header(first)
        atom["category"] = inferred or "命令"
    return atoms


def _cards_from_atoms(atoms: list[dict]) -> list[dict]:
    if not atoms:
        return []
    cards: list[dict] = []
    buf_cat = ""
    buf_md: list[str] = []

    def flush() -> None:
        nonlocal buf_cat, buf_md
        md = "\n".join(buf_md).strip()
        if md:
            cards.append(
                {
                    "title": buf_cat,
                    "html": normalize_prose_html(md_block_to_html(md)),
                }
            )
        buf_cat = ""
        buf_md = []

    for atom in atoms:
        cat = atom.get("category") or "怎么用"
        if buf_md and cat != buf_cat:
            flush()
        buf_cat = cat
        buf_md.append(atom.get("md") or atom.get("text") or "")
    flush()
    return cards


def attach_usage_to_capabilities(
    usage_md: str, caps: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Split 怎么用: common cards stay above chips; matched cards follow a capability."""
    titles = [c.get("title") or "" for c in caps if c.get("title")]
    common_atoms: list[dict] = []
    by_title: dict[str, list[dict]] = {t: [] for t in titles}
    for atom in _usage_atoms(usage_md):
        dest = None
        hint = (atom.get("cap_hint") or "").strip()
        if hint and hint in by_title:
            dest = hint
        elif hint:
            dest = _best_cap_title(hint, titles)
        if dest is None and not atom.get("force_common"):
            blob = f"{atom.get('text', '')}\n{atom.get('md', '')}"
            hits = _caps_hit_by_text(blob, titles)
            dest = hits[0] if len(hits) == 1 else None
        if dest and dest in by_title:
            by_title[dest].append(atom)
        else:
            common_atoms.append(atom)
    for cap in caps:
        cap["usage_cards"] = _cards_from_atoms(by_title.get(cap.get("title") or "", []))
    return _cards_from_atoms(common_atoms), caps


def load_review_intro(skill_dir: Path) -> str:
    """Feishu Review 简介 — only from skill-root review-intro.md (Chinese)."""
    path = skill_dir / "review-intro.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff").strip()
    text = re.sub(r"^#\s+[^\n]+\n+", "", text, count=1).strip()
    if not text or not has_cjk(text):
        return ""
    return one_line(text, 160)


def extract_legacy_review_sections(review_html: str) -> dict[str, str]:
    if not review_html:
        return {}
    out: dict[str, str] = {}
    for sid in LEGACY_SECTION_IDS:
        m = re.search(
            rf'<section[^>]*\bid=["\']{re.escape(sid)}["\'][^>]*>([\s\S]*?)</section>',
            review_html,
            re.I,
        )
        if not m:
            continue
        body = m.group(1).strip()
        body = re.sub(r"^\s*<h2[^>]*>[\s\S]*?</h2>\s*", "", body, count=1, flags=re.I)
        out[sid] = body
    # header blurb
    blurb_m = re.search(
        r"<header[^>]*>[\s\S]*?<p[^>]*>([\s\S]*?)</p>",
        review_html,
        re.I,
    )
    if blurb_m:
        out["_blurb"] = strip_tags(blurb_m.group(1))
    title_m = re.search(
        r"<header[^>]*>[\s\S]*?<h1[^>]*>([\s\S]*?)</h1>",
        review_html,
        re.I,
    )
    if title_m:
        out["_title"] = strip_tags(title_m.group(1))
    return out


def join_html_parts(*parts: str) -> str:
    return "\n".join(p for p in parts if p and p.strip())


def normalize_prose_html(fragment: str, *, strip_leading_h2: bool = True) -> str:
    """Unify lists to bullets; optionally drop accidental outer h2."""
    if not fragment:
        return ""
    html = fragment
    html = re.sub(r"<ol\b([^>]*)>", r"<ul\1>", html, flags=re.I)
    html = re.sub(r"</ol>", "</ul>", html, flags=re.I)
    if strip_leading_h2:
        html = re.sub(r"^\s*<h2[^>]*>[\s\S]*?</h2>\s*", "", html, count=1, flags=re.I)
    return html


def build_content_sections(
    *,
    folder: str,
    skill_dir: Path,
    fm_name: str,
    desc: str,
    readme_text: str,
    skill_text: str,
    review_html: str,
    example_files: list[str],
    ref_files: list[str],
    disable: str,
) -> dict:
    """
    Human Review body (Feishu detail):
      can_do  — Skill 能做什么
      execute — 每件能做的事：先干什么、后干什么
      how_to_use — 只读 skill 根目录 review-usage.md
    """
    legacy = extract_legacy_review_sections(review_html)
    body_path = skill_dir / "review-body.md"
    body_text = (
        body_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        if body_path.is_file()
        else ""
    )
    body_secs = parse_md_h2_sections(body_text) if body_text else {}
    skill_secs = parse_md_h2_sections(
        re.sub(r"^---[\s\S]*?---\s*", "", skill_text.lstrip("\ufeff"), count=1)
    ) if skill_text else {}

    # --- can_do：仅中文 review-body.md ---
    can_do = ""
    section = pick_md_section(
        body_secs,
        ("能做什么", "能干嘛", "是什么", "做什么", "能力"),
    )
    if section and has_cjk(section):
        can_do = md_block_to_html(section)
    if not can_do:
        legacy_can = legacy.get("can-do", "")
        if legacy_can and has_cjk(legacy_can):
            can_do = legacy_can

    # --- execute：仅中文 review-body.md · 只认 ## 执行步骤 ---
    execute = ""
    section = body_secs.get("执行步骤", "")
    if section and has_cjk(section):
        execute = md_block_to_html(section)
    if not execute:
        legacy_ex = join_html_parts(
            legacy.get("steps", ""),
            legacy.get("contents", ""),
        )
        if legacy_ex and has_cjk(legacy_ex):
            execute = legacy_ex
    if not execute and ref_files:
        items = "".join(f"<li><code>references/{f}</code></li>" for f in ref_files[:12])
        execute = (
            "<p class='hint'>长流程在 references/；Agent 应按 SKILL 路由按需读取：</p>"
            f"<ul>{items}</ul>"
        )

    # --- how_to_use: dedicated file only；空「无」小节不输出 ---
    usage_path = skill_dir / "review-usage.md"
    usage_md = ""
    if usage_path.is_file():
        usage_md = usage_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        usage_md = re.sub(r"^#\s+[^\n]+\n+", "", usage_md, count=1)
        usage_md = strip_empty_usage_h2(usage_md)
        how = md_block_to_html(usage_md) if usage_md.strip() else ""
    else:
        how = (
            "<div class='empty-block'>缺少 <code>review-usage.md</code>。"
            "请在本 skill 根目录新增该文件（对话输入 / 有则写子指令；条件自动或常驻须写「项目中怎么自动调用」），"
            "再重跑 Review。</div>"
        )

    placeholder = (
        "<div class='empty-block'>暂无整理好的内容。请在 <code>review-body.md</code> 补充中文「能做什么 / 执行步骤」后重跑 Review。</div>"
    )
    placeholder_card = [{"title": "", "html": placeholder}]

    can_do_html = normalize_prose_html(can_do) or placeholder
    execute_html = normalize_prose_html(execute) or placeholder
    how_html = normalize_prose_html(how, strip_leading_h2=False) or placeholder

    can_src = pick_md_section(
        body_secs, ("能做什么", "能干嘛", "是什么", "做什么", "能力")
    )
    exe_src = body_secs.get("执行步骤", "")
    can_do_cards = (
        cards_from_md_body(can_src, "") if can_src and has_cjk(can_src) else placeholder_card
    )
    execute_cards = (
        cards_from_md_body(exe_src, "")
        if exe_src and has_cjk(exe_src)
        else placeholder_card
    )
    if usage_path.is_file() and usage_md.strip():
        how_cards = usage_inner_cards(usage_md)
    else:
        how_cards = [{"title": "怎么用", "html": how_html}]

    caps = build_capabilities(can_src, exe_src)
    if usage_path.is_file() and usage_md.strip():
        usage_common_cards, caps = attach_usage_to_capabilities(usage_md, caps)
    else:
        usage_common_cards = []
    for cap in caps:
        cap["needs_detail"] = bool(
            (cap.get("execute_html") or "").strip() or cap.get("usage_cards")
        )

    zh_intro = load_review_intro(skill_dir)
    usage_prose = (
        usage_prose_html(usage_md)
        if usage_path.is_file() and usage_md.strip()
        else ""
    )

    return {
        "title": legacy.get("_title") or fm_name or folder,
        "blurb": zh_intro,  # only review-intro.md
        "can_do": can_do_html,
        "execute": execute_html,
        "how_to_use": how_html,
        "can_do_cards": can_do_cards,
        "execute_cards": execute_cards,
        "how_to_use_cards": how_cards,
        "usage_common_cards": usage_common_cards,
        "usage_prose": usage_prose,
        "capabilities": caps,
        "has_legacy_review": bool(review_html),
        "has_review_usage": usage_path.is_file(),
        "has_review_intro": bool(zh_intro),
        "has_review_body": body_path.is_file() and bool(can_do or execute),
    }


def list_skill_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_dir() or p.name in SKIP_DIRS or p.name.startswith("."):
            continue
        if (p / "SKILL.md").is_file():
            out.append(p)
    return out


def check_skill(folder: Path) -> dict:
    name = folder.name
    skill_path = folder / "SKILL.md"
    readme_path = folder / "README.md"
    review_path = folder / "review.html"
    refs_dir = folder / "references"
    examples_dir = folder / "examples"
    git_marker = folder / ".git"

    skill_text = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
    fm = parse_frontmatter(skill_text) if skill_text else {}
    skill_lines = count_lines(skill_text)
    desc = (fm.get("description") or "").strip()
    fm_name = (fm.get("name") or "").strip()
    tag_path = folder / "tag.txt"
    tags: list[str] = []
    if tag_path.is_file():
        raw = tag_path.read_text(encoding="utf-8", errors="replace").strip()
        # First line; comma-separated multi-tags
        line = raw.splitlines()[0] if raw else ""
        tags = [t.strip() for t in line.split(",") if t.strip()]
    tag = " · ".join(tags)  # for compact check detail / legacy single string
    disable = str(fm.get("disable-model-invocation", "")).strip().lower()

    readme_text = (
        readme_path.read_text(encoding="utf-8", errors="replace")
        if readme_path.is_file()
        else ""
    )
    review_text = (
        review_path.read_text(encoding="utf-8", errors="replace")
        if review_path.is_file()
        else ""
    )

    ref_files = (
        sorted(p.name for p in refs_dir.iterdir() if p.is_file())
        if refs_dir.is_dir()
        else []
    )
    example_files: list[str] = []
    if examples_dir.is_dir():
        example_files = sorted(
            str(p.relative_to(examples_dir)).replace("\\", "/")
            for p in examples_dir.rglob("*")
            if p.is_file()
        )

    content = build_content_sections(
        folder=name,
        skill_dir=folder,
        fm_name=fm_name,
        desc=desc,
        readme_text=readme_text,
        skill_text=skill_text,
        review_html=review_text,
        example_files=example_files,
        ref_files=ref_files,
        disable=disable,
    )

    intro = one_line(content.get("blurb") or "", 120) or "（缺少 review-intro.md）"

    section_hits = {
        sid: bool(
            re.search(rf'id=["\']{re.escape(sid)}["\']', review_text)
        )
        for sid in LEGACY_SECTION_IDS
    }

    checks: list[dict] = []

    def add(cid: str, level: str, title: str, detail: str) -> None:
        checks.append({"id": cid, "level": level, "title": title, "detail": detail})

    if skill_path.is_file():
        add("skill_md", "pass", "SKILL.md", f"{skill_lines} 行")
    else:
        add("skill_md", "fail", "SKILL.md", "缺失")

    if fm_name:
        if fm_name == name:
            add("fm_name", "pass", "frontmatter name", fm_name)
        else:
            add(
                "fm_name",
                "warn",
                "frontmatter name ≠ 文件夹",
                f"name=`{fm_name}` · folder=`{name}`",
            )
    else:
        add("fm_name", "fail", "frontmatter name", "缺失")

    if tags:
        add("tag", "pass", "tag.txt", "、".join(tags))
    else:
        add("tag", "warn", "tag.txt", "缺失（总览/单页名称旁显示；创建时询问；多标签用逗号分隔）")

    if len(desc) >= 40:
        add("fm_desc", "pass", "frontmatter description", f"{len(desc)} 字符")
    elif desc:
        add("fm_desc", "warn", "frontmatter description 过短", f"{len(desc)} 字符")
    else:
        add("fm_desc", "fail", "frontmatter description", "缺失")

    readme_zh_path = folder / "README.zh.md"
    readme_zh_text = (
        readme_zh_path.read_text(encoding="utf-8", errors="replace")
        if readme_zh_path.is_file()
        else ""
    )

    def _h2_section(text: str, heading: str) -> str:
        m = re.search(
            rf"(?ms)^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)",
            text,
        )
        return m.group(1) if m else ""

    def _readme_order_fail(text: str, *, first_h2: str) -> str:
        body = re.sub(r"^#\s+[^\n]+\n+", "", text.lstrip("\ufeff"), count=1)
        body = re.sub(r"^\[.*?\]\(README(?:\.zh)?\.md\)\s*\n+", "", body, count=1)
        first = re.search(r"(?m)^##\s+", body)
        if not first:
            return "缺二级标题"
        intro = body[: first.start()].strip()
        if not intro:
            return "标题后缺简介（安装之前应有一段简介）"
        h2s = [h.strip() for h in re.findall(r"(?m)^##\s+(.+?)\s*$", text)]
        if not h2s:
            return "缺二级标题"
        if h2s[0] != first_h2:
            return f"第一个二级标题应是{first_h2}（现为 {h2s[0]}）"
        install = _h2_section(text, first_h2)
        if re.search(r"(?m)^git clone\b", install):
            return "安装节不要写给人看的 git clone，应写成给 Agent 的提示词"
        if not re.search(r"https?://\S+\.git", install):
            return "安装提示词缺 git 仓库地址"
        if first_h2 == "Install":
            if re.search(r"请把 skill", install):
                return "英文 README 的安装提示词应写成英文"
            if not re.search(r"Steps", install):
                return "安装提示词缺 Steps"
        elif not re.search(r"步骤", install):
            return "安装提示词缺步骤"
        return ""

    if not readme_path.is_file():
        add("readme", "fail", "README.md", "缺失（必备：英文 README）")
    else:
        links_zh = bool(re.search(r"README\.zh\.md", readme_text))
        order_fail = _readme_order_fail(readme_text, first_h2="Install")
        if not links_zh:
            add("readme", "fail", "README.md", "未链到中文 README.zh.md")
        elif order_fail:
            add("readme", "fail", "README.md", order_fail)
        else:
            add("readme", "pass", "README.md", "英文 + 入口到 README.zh.md + 简介→安装→内容")

    if not readme_zh_path.is_file():
        add("readme_zh", "fail", "README.zh.md", "缺失（必备：中文 README）")
    else:
        links_en = bool(re.search(r"\]\(README\.md\)", readme_zh_text))
        has_zh = bool(re.search(r"[\u4e00-\u9fff]", readme_zh_text))
        order_fail = _readme_order_fail(readme_zh_text, first_h2="安装")
        if not links_en:
            add("readme_zh", "fail", "README.zh.md", "未链到英文 README.md")
        elif not has_zh:
            add("readme_zh", "fail", "README.zh.md", "无中文")
        elif order_fail:
            add("readme_zh", "fail", "README.zh.md", order_fail)
        else:
            add("readme_zh", "pass", "README.zh.md", "中文 + 入口到 README.md + 简介→安装→内容")

    def _readme_user_facing_problems() -> list[str]:
        """README 具体内容只有「功能介绍」+「怎么用」+「常见改动」，都写给用的人。"""
        problems: list[str] = []
        install_h2 = {"install", "安装"}
        extras_h2 = {"privacy", "隐私"}
        for label, text, features, howto, changes in (
            ("README.md", readme_text, "Features", "How to use", "Common changes"),
            ("README.zh.md", readme_zh_text, "功能介绍", "怎么用", "常见改动"),
        ):
            if not text:
                continue
            h2s = [h.strip() for h in re.findall(r"(?m)^##\s+(.+?)\s*$", text)]
            for wanted in (features, howto, changes):
                if not any(h.lower() == wanted.lower() for h in h2s):
                    problems.append(f"{label} 缺「{wanted}」")
            allowed = {features.lower(), howto.lower(), changes.lower()} | install_h2 | extras_h2
            surplus = [h for h in h2s if h.lower() not in allowed]
            if surplus:
                problems.append(f"{label} 多余小节「{'、'.join(surplus)}」")
        return problems

    readme_user_problems = _readme_user_facing_problems()
    if readme_path.is_file() and readme_zh_path.is_file():
        if readme_user_problems:
            add(
                "readme_user_facing",
                "warn",
                "README 具体内容不面向用户",
                "；".join(readme_user_problems)
                + "（内容部分只留功能介绍 + 怎么用 + 常见改动）",
            )
        else:
            add(
                "readme_user_facing",
                "pass",
                "README 具体内容面向用户",
                "只有功能介绍 + 怎么用 + 常见改动；无文件角色清单",
            )

    usage_path = folder / "review-usage.md"
    usage_text_early = (
        usage_path.read_text(encoding="utf-8", errors="replace")
        if usage_path.is_file()
        else ""
    )
    if usage_path.is_file():
        add("review_usage", "pass", "review-usage.md", "怎么用（人会说 / 会点的入口）")
    else:
        add("review_usage", "fail", "review-usage.md", "缺失（Review 页「怎么用」专用）")

    if re.search(r"(?m)^##\s+脚本和工具\s*$", usage_text_early):
        add(
            "usage_tools",
            "warn",
            "怎么用 · 脚本和工具",
            "人类页不必写脚本清单，删 ## 脚本和工具",
        )
    if re.search(r"(?m)^##\s+description 内容\s*$", usage_text_early):
        add(
            "usage_desc",
            "warn",
            "怎么用 · description 内容",
            "人类页不必抄 description，删 ## description 内容",
        )

    def _check_install_prompt(
        cid: str, title: str, text: str, install_h2: str, *, english: bool
    ) -> None:
        if not text:
            add(cid, "warn", title, "缺安装提示词")
            return
        install = _h2_section(text, install_h2)
        has_url = bool(re.search(r"https?://\S+\.git", install))
        if english:
            has_spec = bool(
                re.search(
                    r"First read and follow this agent app's current skill spec",
                    install,
                )
            )
            has_steps = bool(re.search(r"Steps", install))
            chinese_block = bool(re.search(r"请把 skill", install))
        else:
            has_spec = bool(
                re.search(r"先读取并遵守你当前这个 Agent 的 skill 规范", install)
            )
            has_steps = bool(re.search(r"步骤", install))
            chinese_block = False
        if chinese_block:
            add(cid, "fail", title, "英文 README 的安装提示词应写成英文")
        elif has_spec and has_url and has_steps:
            add(cid, "pass", title, "通过 Agent 安装（仓库 + 步骤 + 先查规范）")
        else:
            add(cid, "fail", title, "安装节应是一段给 Agent 的提示词，内含仓库地址和步骤")

    _check_install_prompt(
        "readme_adopt", "README · 安装提示词", readme_text, "Install", english=True
    )
    _check_install_prompt(
        "readme_zh_adopt",
        "README.zh · 安装提示词",
        readme_zh_text,
        "安装",
        english=False,
    )

    brand_re = forbidden_app_name_re()
    brand_hits: list[str] = []
    skip_dir = {".git", "node_modules", "dist", ".venv"}
    text_ext = {
        ".md",
        ".py",
        ".ps1",
        ".txt",
        ".html",
        ".json",
        ".js",
        ".ts",
        ".tsx",
        ".css",
        ".cs",
        ".gitignore",
        ".yml",
        ".yaml",
        ".toml",
    }
    for p in folder.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in text_ext:
            continue
        if skip_dir & set(p.parts):
            continue
        rel = str(p.relative_to(folder)).replace("\\", "/")
        if p.name.startswith("_strip-"):
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if rel.endswith("references/skill-authoring.md"):
            body = re.sub(
                r"(?ms)^##\s+Agent-app names \(forbidden\)\s*\n.*?(?=^##\s+|\Z)",
                "",
                body,
            )
        css_prop = "cur" + "sor"
        body = re.sub(rf"(?i){css_prop}\s*:", "", body)
        found = sorted({m.group(0) for m in brand_re.finditer(body)})
        name_hit = brand_re.search(rel)
        if name_hit:
            found = sorted(set(found) | {name_hit.group(0)})
        if found:
            brand_hits.append(f"{rel}（{'、'.join(found)}）")
    if brand_hits:
        detail = "；".join(brand_hits[:8])
        if len(brand_hits) > 8:
            detail += f" …共 {len(brand_hits)} 处"
        add("agent_app_name", "fail", "Agent 应用名", detail)
    else:
        add("agent_app_name", "pass", "Agent 应用名", "未写具体 Agent 应用名")

    if review_path.is_file():
        add(
            "review_html",
            "warn",
            "review.html",
            "遗留页仍在；应删除。人类入口为飞书 Review + README / review-usage.md",
        )
    else:
        add("review_html", "pass", "review.html", "已不使用（正确）")

    if re.search(r"(?m)^\s*\|\s*`?-review`?", skill_text) or re.search(
        r"(?m)^#+\s+.*-review\b", skill_text
    ):
        add("review_flag", "pass", "SKILL.md -review", "Commands 含 -review")
    else:
        add("review_flag", "fail", "SKILL.md -review", "缺失（打开本页入口）")

    open_script = folder / "scripts" / "open-review.ps1"
    if open_script.is_file():
        opener_text = open_script.read_text(encoding="utf-8", errors="replace")
        if "skills-check" in opener_text and "skills-check-viewer.py" in opener_text:
            add("open_review", "pass", "scripts/open-review.ps1", "指向 skills-check viewer")
        else:
            add(
                "open_review",
                "fail",
                "scripts/open-review.ps1",
                "未指向 skills-check/scripts/skills-check-viewer.py",
            )
    else:
        add("open_review", "fail", "scripts/open-review.ps1", "缺失")

    if example_files:
        substantial = False
        examples_dir = folder / "examples"
        if examples_dir.is_dir():
            for p in examples_dir.rglob("*"):
                if not p.is_file() or p.name == ".gitkeep":
                    continue
                n = p.name.lower()
                if (
                    p.stat().st_size >= 400
                    or n == "case-index.md"
                    or n.endswith("-case.md")
                    or n.endswith("-checklist.md")
                    or n.endswith("-bootstrap.md")
                ):
                    substantial = True
                    break
        if substantial:
            add("examples", "pass", "第三层 examples/", f"{len(example_files)} 个文件")
        else:
            add(
                "examples",
                "fail",
                "第三层 examples/",
                "仅有过短 stub（skill-authoring.md § Three layers）",
            )
    else:
        add("examples", "fail", "第三层 examples/", "缺失")

    if disable in ("true", "yes", "1"):
        add("disable", "pass", "disable-model-invocation", "true")
    elif name in AUTO_INVOKE_OK:
        add("disable", "pass", "自动加载 hub", "未设 disable（符合设计）")
    else:
        add("disable", "warn", "disable-model-invocation", "未设；新 skill 默认建议 true")

    if ref_files:
        mentions_refs = bool(re.search(r"references/", skill_text, re.I))
        has_route = bool(
            re.search(r"(Routing|Read first|Route to|何时读|路由)", skill_text, re.I)
        )
        if mentions_refs and has_route:
            add("hub_refs", "pass", "references/ + 路由", f"{len(ref_files)} 个参考文件")
        elif mentions_refs:
            add("hub_refs", "warn", "references/ 无明确路由表", f"{len(ref_files)} 个文件")
        else:
            add("hub_refs", "warn", "references/ 未在 SKILL 引用", f"{len(ref_files)} 个文件")
    elif skill_lines >= LARGE_SKILL_LINES:
        add(
            "hub_refs",
            "warn",
            "长 SKILL 未拆 references/",
            f"{skill_lines} 行 ≥ {LARGE_SKILL_LINES}",
        )
    else:
        add("hub_refs", "pass", "体量", f"{skill_lines} 行，无 references/")

    if git_marker.exists():
        add("git", "pass", "Git 子模块", ".git 存在")
    else:
        add("git", "warn", "Git", "目录下无 .git")

    intro_path = folder / "review-intro.md"
    if intro_path.is_file() and content.get("blurb") and has_cjk(content["blurb"]):
        add("zh_intro", "pass", "review-intro.md", one_line(content["blurb"], 40))
    elif intro_path.is_file():
        add("zh_intro", "fail", "review-intro.md", "存在但无有效中文正文")
    else:
        add("zh_intro", "fail", "review-intro.md", "缺失（Review 简介专用；中文）")

    body_check = folder / "review-body.md"
    body_for_heading = (
        body_check.read_text(encoding="utf-8", errors="replace")
        if body_check.is_file()
        else ""
    )
    if re.search(r"(?m)^##\s+功能怎么执行\s*$", body_for_heading):
        add(
            "review_body_old_h2",
            "fail",
            "review-body.md",
            "旧标题「功能怎么执行」已停用，改为 ## 执行步骤",
        )
    if body_check.is_file() and content.get("has_review_body"):
        add("review_body", "pass", "review-body.md", "能做什么 / 执行步骤")
    elif body_check.is_file():
        add("review_body", "fail", "review-body.md", "存在但缺少中文「能做什么 / 执行步骤」")
    else:
        add("review_body", "fail", "review-body.md", "缺失（Review 能做什么/执行步骤专用；中文）")

    # Positive / negative norm pairing → 不合规 = 需关注 (warn)
    pairing_docs: dict[str, str] = {}
    if skill_text:
        pairing_docs["SKILL.md"] = skill_text
    if readme_text:
        pairing_docs["README.md"] = readme_text
    if readme_zh_text:
        pairing_docs["README.zh.md"] = readme_zh_text
    usage_text = (
        usage_path.read_text(encoding="utf-8", errors="replace")
        if usage_path.is_file()
        else ""
    )
    if usage_text:
        pairing_docs["review-usage.md"] = usage_text
    if refs_dir.is_dir():
        for p in sorted(refs_dir.iterdir()):
            if p.is_file() and p.suffix.lower() == ".md":
                pairing_docs[f"references/{p.name}"] = p.read_text(
                    encoding="utf-8", errors="replace"
                )
    pair_level, pair_detail = check_pos_neg_pairing(pairing_docs)
    add("pos_neg_pair", pair_level, "肯定/否定配对", pair_detail)

    fails = sum(1 for c in checks if c["level"] == "fail")
    warns = sum(1 for c in checks if c["level"] == "warn")
    passes = sum(1 for c in checks if c["level"] == "pass")
    if fails:
        status = "fail"
    elif warns:
        status = "warn"
    else:
        status = "pass"

    issues = [
        {"level": c["level"], "text": f'{c["title"]} — {c["detail"]}'}
        for c in checks
        if c["level"] in ("warn", "fail")
    ]

    return {
        "folder": name,
        "path": str(folder),
        "status": status,
        "frontmatter_name": fm_name,
        "tag": tag,
        "tags": tags,
        "display_title": content["title"],
        "intro": intro,
        "issues": issues,
        "skill_lines": skill_lines,
        "ref_count": len(ref_files),
        "ref_files": ref_files,
        "example_count": len(example_files),
        "has_readme": readme_path.is_file() and readme_zh_path.is_file(),
        "has_review": review_path.is_file(),
        "has_review_usage": usage_path.is_file(),
        "has_review_intro": (folder / "review-intro.md").is_file()
        and bool(content.get("blurb")),
        "has_open_script": open_script.is_file(),
        "content": content,
        "checks": checks,
        "counts": {"pass": passes, "warn": warns, "fail": fails},
    }


def clean_tags(raw: object, limit: int = MAX_TAGS_PER_SKILL) -> list[str]:
    """Normalize a tag list: no commas/newlines, deduped, capped at `limit`."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = re.sub(r"[,\r\n\t]+", " ", item).strip()
        tag = re.sub(r"\s{2,}", " ", tag)[:MAX_TAG_LEN].strip()
        if tag and tag not in out:
            out.append(tag)
    return out[:limit]


def read_tag_vocab() -> list[str]:
    """The shared vocabulary is a whole-fleet list — not capped per skill."""
    if not TAG_VOCAB_PATH.is_file():
        return []
    lines = TAG_VOCAB_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return clean_tags(
        [ln for ln in lines if not ln.lstrip().startswith("#")], limit=MAX_TAG_VOCAB
    )


def merge_tag_vocab(tags: list[str]) -> list[str]:
    """Add unseen tags to the vocabulary file; return the merged list."""
    vocab = read_tag_vocab()
    added = [t for t in tags if t not in vocab]
    if added:
        vocab = (vocab + added)[:MAX_TAG_VOCAB]
        TAG_VOCAB_PATH.write_text("\n".join(vocab) + "\n", encoding="utf-8")
    return vocab


def write_skill_tags(root: Path, folder: str, tags: list[str]) -> list[str]:
    """Write `tag.txt` for one skill under `root`. Empty list removes the file."""
    if not isinstance(folder, str) or not folder.strip():
        raise ValueError("folder 缺失")
    if folder != Path(folder).name or folder in {".", ".."}:
        raise ValueError("folder 非法")
    target = (root / folder).resolve()
    if target.parent != root.resolve():
        raise ValueError("folder 超出 skills 根目录")
    if not target.is_dir() or not (target / "SKILL.md").is_file():
        raise ValueError("不是 skill 目录")
    clean = clean_tags(tags)
    tag_file = target / "tag.txt"
    if not clean:
        if tag_file.is_file():
            tag_file.unlink()
        return []
    tmp = tag_file.with_suffix(".txt.tmp")
    tmp.write_text(", ".join(clean) + "\n", encoding="utf-8")
    os.replace(tmp, tag_file)
    merge_tag_vocab(clean)
    return clean


def scan_skills(root: Path) -> dict:
    skills = [check_skill(d) for d in list_skill_dirs(root)]
    summary = {
        "total": len(skills),
        "pass": sum(1 for s in skills if s["status"] == "pass"),
        "warn": sum(1 for s in skills if s["status"] == "warn"),
        "fail": sum(1 for s in skills if s["status"] == "fail"),
        "missing_readme": sum(1 for s in skills if not s["has_readme"]),
        "missing_review": sum(1 for s in skills if not s["has_review"]),
        "missing_review_usage": sum(1 for s in skills if not s["has_review_usage"]),
        "missing_review_intro": sum(1 for s in skills if not s.get("has_review_intro")),
        "missing_open_script": sum(1 for s in skills if not s["has_open_script"]),
    }
    used: dict[str, int] = {}
    for s in skills:
        for t in s.get("tags", []):
            used[t] = used.get(t, 0) + 1
    vocab = [t for t in read_tag_vocab() if t not in used]
    tag_options = sorted(used, key=lambda t: (-used[t], t)) + vocab
    return {
        "generated_at": datetime.now(timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds"),
        "skills_root": str(root.resolve()),
        "summary": summary,
        "skills": skills,
        "tag_options": tag_options,
        "tag_counts": used,
        "norms": [
            "单页 Review（飞书风）：能做什么 / 怎么用 / 执行步骤",
            "怎么用只读各 skill 的 review-usage.md（对话输入 / 子指令功能 / 自动调用）",
            "总览：状态 + 问题 + 一句简介；点进单页后右上角切换 skill",
            "各 skill：scripts/open-review.ps1 打开本 skill Review",
        ],
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Skills 总览</title>
<style>
  :root {
    --primary: #3370ff;
    --primary-soft: #e8f0ff;
    --bg: #f5f6f7;
    --card: #ffffff;
    --text: #1f2329;
    --text-2: #646a73;
    --border: #dee0e3;
    --ok: #00b42a;
    --ok-soft: #e8ffea;
    --warn: #ff7d00;
    --warn-soft: #fff3e8;
    --fail: #f53f3f;
    --fail-soft: #ffece8;
    --radius: 10px;
    --shadow: 0 1px 2px rgba(31, 35, 41, 0.06), 0 2px 8px rgba(31, 35, 41, 0.04);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    font-family: "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .hidden { display: none !important; }
  .topbar {
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px;
    display: flex;
    align-items: center;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .logo {
    width: 28px; height: 28px; border-radius: 8px;
    background: linear-gradient(135deg, #3370ff, #14c9c9);
    display: grid; place-items: center;
    color: #fff; font-weight: 700; font-size: 13px;
    flex: 0 0 auto;
  }
  .topbar h1 { margin: 0; font-size: 16px; font-weight: 600; }
  .topbar .actions { margin-left: auto; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .topbar .meta { color: var(--text-2); font-size: 12px; text-align: right; }
  .btn {
    appearance: none; border: none; background: var(--primary); color: #fff;
    font: inherit; font-size: 13px; font-weight: 500; padding: 7px 14px;
    border-radius: 6px; cursor: pointer; white-space: nowrap;
  }
  .btn:hover { background: #4e83fd; }
  .btn-ghost { background: var(--primary-soft); color: var(--primary); }
  .btn-ghost:hover { background: #d6e4ff; }
  select.skill-switch {
    font: inherit; font-size: 13px; padding: 7px 10px;
    border-radius: 6px; border: 1px solid var(--border);
    background: #fff; color: var(--text); max-width: min(360px, 52vw);
  }
  .wrap { max-width: 1040px; margin: 0 auto; padding: 24px 20px 48px; }
  .hero {
    background: linear-gradient(135deg, #3370ff 0%, #4e83fd 55%, #14c9c9 120%);
    color: #fff; border-radius: 14px; padding: 22px 24px;
    box-shadow: var(--shadow); margin-bottom: 14px;
  }
  .hero .label { opacity: .85; font-size: 13px; }
  .hero .big {
    font-size: 34px; font-weight: 700; letter-spacing: -.5px; margin: 4px 0 8px;
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  }
  .hero .sub { font-size: 13px; opacity: .9; }
  .grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 18px;
  }
  @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px; box-shadow: var(--shadow);
  }
  .card .k { color: var(--text-2); font-size: 12px; margin-bottom: 6px; }
  .card .v { font-size: 22px; font-weight: 650; letter-spacing: -.3px; }
  .card .hint { color: var(--text-2); font-size: 11px; margin-top: 4px; }
  .card.card-pass {
    background: #e8ffea;
    border-color: #b7ebc6;
  }
  .card.card-pass .k,
  .card.card-pass .v { color: var(--ok); }
  .card.card-warn {
    background: #fff7e0;
    border-color: #f5c842;
  }
  .card.card-warn .k,
  .card.card-warn .v { color: #d48806; }
  .card.card-fail {
    background: #ffece8;
    border-color: #f98981;
  }
  .card.card-fail .k,
  .card.card-fail .v { color: var(--fail); }
  .section {
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    box-shadow: var(--shadow); margin-bottom: 14px; overflow: visible;
  }
  .section-hd {
    padding: 14px 18px; border-bottom: 1px solid var(--border);
    font-size: 15px; font-weight: 650; display: flex; align-items: center; gap: 8px;
    letter-spacing: -.01em;
  }
  .section-bd { padding: 14px 18px 16px; font-size: 13px; color: var(--text-2); line-height: 1.65; }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary); }
  .dot.warn { background: var(--warn); }
  .dot.fail { background: var(--fail); }
  .problems-block { margin: 0 0 14px; display: flex; flex-direction: column; gap: 6px; }
  .problems-block .problems-hd {
    font-size: 13px; font-weight: 650; color: var(--text); padding: 0 2px;
  }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 18px; border-bottom: 1px solid var(--border); }
  .chip-btn {
    border: 1px solid var(--border); background: #f2f3f5; border-radius: 999px;
    padding: 5px 12px; font-size: 12px; cursor: pointer; color: var(--text-2);
  }
  .chip-btn.active { background: var(--primary-soft); color: var(--primary); border-color: #c2d4ff; font-weight: 600; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 18px 18px; }
  .chip {
    background: #f2f3f5; border-radius: 8px; padding: 8px 12px;
    font-size: 12px; color: var(--text-2);
  }
  .foot { text-align: center; color: var(--text-2); font-size: 12px; margin-top: 8px; }

  .skill-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    padding: 16px 18px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    text-align: left;
    width: 100%;
    background: transparent;
    border-left: none; border-right: none; border-top: none;
    font: inherit; color: inherit;
  }
  .skill-row:last-child { border-bottom: none; }
  .skill-row:hover { background: #fafbfc; }
  .skill-row .name { font-weight: 650; font-size: 14px; display: inline; }
  .skill-row .name-row {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  }
  .skill-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--primary-soft);
    color: var(--primary);
    line-height: 1.4;
  }
  .hero .skill-tag {
    background: rgba(255,255,255,.22);
    color: #fff;
    font-size: 12px;
    vertical-align: middle;
  }
  .skill-row .intro { color: var(--text-2); font-size: 12px; line-height: 1.5; margin-top: 4px; max-width: 52em; }
  .skill-row .issues { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
  .issue-line {
    font-size: 12px; padding: 4px 8px; border-radius: 6px;
    display: flex; gap: 8px; align-items: center;
  }
  .issue-line.warn { background: var(--warn-soft); color: #a34d00; }
  .issue-line.fail { background: var(--fail-soft); color: #c12424; }
  .issue-line .tag { font-weight: 700; flex: 0 0 auto; text-transform: uppercase; font-size: 10px; letter-spacing: .04em; }
  .issue-line .issue-text { flex: 1; min-width: 0; }
  .fix-btn {
    flex: 0 0 auto;
    font-size: 11px; font-weight: 650;
    padding: 2px 8px; border-radius: 999px;
    background: var(--primary); color: #fff;
    text-decoration: none; line-height: 1.4;
  }
  button.fix-btn { border: none; cursor: pointer; font-family: inherit; }
  button.fix-btn:disabled { opacity: .65; cursor: wait; }
  .fix-btn:hover { filter: brightness(1.06); }
  .problems-block .problems-hd {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
  }
  .fix-modal {
    position: fixed; inset: 0; z-index: 40;
    background: rgba(15, 18, 24, .45);
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }
  .fix-modal-card {
    width: min(640px, 100%);
    background: var(--card);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 16px 16px 14px;
  }
  .fix-modal-hd { font-size: 14px; font-weight: 650; color: var(--text); margin-bottom: 8px; }
  .fix-modal textarea {
    width: 100%; min-height: 220px; resize: vertical;
    border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 12px; font: inherit; font-size: 13px; line-height: 1.55;
    color: var(--text); background: #fff; box-sizing: border-box;
  }
  .fix-modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
  .tag-filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 18px; border-bottom: 1px solid var(--border); }
  .tag-filters .lead { font-size: 12px; color: var(--text-2); margin-right: 2px; }
  .tag-dd { position: relative; }
  .tag-dd-btn {
    font: inherit; font-size: 12px; min-width: 168px; max-width: 280px;
    padding: 5px 28px 5px 12px; border: 1px solid var(--border); border-radius: 8px;
    background: #fff; color: var(--text); cursor: pointer; text-align: left;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .tag-dd-btn::after {
    content: ""; position: absolute; right: 12px; top: 50%;
    width: 0; height: 0; margin-top: -2px;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid var(--text-2);
  }
  .tag-dd-btn { position: relative; }
  .tag-dd-btn.open { border-color: #c2d4ff; color: var(--primary); }
  .tag-dd-menu {
    position: absolute; left: 0; top: calc(100% + 4px); z-index: 50;
    min-width: 100%; max-height: 280px; overflow: auto;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; box-shadow: var(--shadow); padding: 4px;
  }
  .tag-dd-menu label {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; border-radius: 6px; font-size: 12px;
    color: var(--text); cursor: pointer;
  }
  .tag-dd-menu label:hover { background: var(--primary-soft); color: var(--primary); }
  .tag-dd-menu .n { margin-left: auto; opacity: .5; }
  .tag-dd-clear {
    display: block; width: 100%; border: 0; background: none;
    padding: 6px 10px; border-radius: 6px; font: inherit; font-size: 12px;
    color: var(--text-2); cursor: pointer; text-align: left;
  }
  .tag-dd-clear:hover { background: #f2f3f5; color: var(--text); }
  .tag-reset {
    border: 0; background: none; padding: 4px 2px;
    font: inherit; font-size: 12px; color: var(--primary); cursor: pointer;
  }
  .tag-reset:hover { text-decoration: underline; }
  .ctx-menu {
    position: fixed; z-index: 60; min-width: 168px; padding: 6px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; box-shadow: var(--shadow);
  }
  .ctx-menu button {
    display: block; width: 100%; text-align: left; border: 0; background: none;
    padding: 7px 10px; border-radius: 6px; font: inherit; font-size: 13px;
    color: var(--text); cursor: pointer;
  }
  .ctx-menu button:hover { background: var(--primary-soft); color: var(--primary); }
  .tag-modal-card { width: min(520px, 100%); background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow); padding: 16px; }
  .tag-modal-sub { font-size: 12px; color: var(--text-2); margin: 2px 0 12px; }
  .tag-box { display: flex; flex-wrap: wrap; gap: 6px; min-height: 34px; padding: 7px; border: 1px solid var(--border); border-radius: 8px; }
  .tag-box .empty-hint { font-size: 12px; color: var(--text-2); padding: 3px 2px; }
  .tag-pill {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
    padding: 3px 8px; border-radius: 999px; background: var(--primary-soft); color: var(--primary);
  }
  .tag-pill button { border: 0; background: none; color: inherit; cursor: pointer; font: inherit; line-height: 1; padding: 0; opacity: .7; }
  .tag-pill button:hover { opacity: 1; }
  .tag-cand { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .tag-cand button {
    border: 1px solid var(--border); background: #f2f3f5; border-radius: 999px;
    padding: 3px 10px; font-size: 12px; color: var(--text-2); cursor: pointer;
  }
  .tag-cand button:hover { background: var(--primary-soft); color: var(--primary); border-color: #c2d4ff; }
  .tag-new { display: flex; gap: 8px; margin-top: 12px; }
  .tag-new input {
    flex: 1 1 auto; border: 1px solid var(--border); border-radius: 8px;
    padding: 7px 10px; font: inherit; font-size: 13px; color: var(--text); background: #fff;
  }
  .tag-err { font-size: 12px; color: var(--fail); margin-top: 8px; min-height: 16px; }
  .label-sm { font-size: 12px; color: var(--text-2); margin: 12px 0 4px; }
  .ok-line { font-size: 12px; color: var(--ok); margin-top: 8px; }
  .badges { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; align-items: flex-start; }
  .badge {
    font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px;
  }
  .badge.pass { background: var(--ok-soft); color: var(--ok); }
  .badge.warn { background: var(--warn-soft); color: var(--warn); }
  .badge.fail { background: var(--fail-soft); color: var(--fail); }
  /* Hero：通过用浅绿底 + 绿字（与总览徽标一致） */
  .hero .badge.pass {
    background: var(--ok-soft);
    color: var(--ok);
    font-weight: 700;
  }
  .hero .badge.warn {
    background: var(--warn-soft);
    color: var(--warn);
    font-weight: 700;
  }
  .hero .badge.fail {
    background: var(--fail-soft);
    color: var(--fail);
    font-weight: 700;
  }
  .hero .badge.neutral {
    background: rgba(255,255,255,.18);
    color: #fff;
    font-weight: 500;
  }
  .badge.neutral { background: #f2f3f5; color: var(--text-2); font-weight: 500; }
  .go { color: var(--primary); font-size: 12px; font-weight: 600; margin-top: 10px; }
  .empty { padding: 28px 18px; text-align: center; color: var(--text-2); }

  /* detail — same Feishu chrome */
  .detail-layout {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 14px;
    max-width: 1040px;
    margin: 0 auto;
    padding: 24px 20px 48px;
  }
  @media (max-width: 820px) {
    .detail-layout { grid-template-columns: 1fr; }
    .side { position: static !important; }
  }
  .side {
    position: sticky; top: 72px; align-self: start;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 12px; box-shadow: var(--shadow);
  }
  .side strong {
    display: block; margin: 4px 8px 8px; color: var(--text-2);
    font-size: 12px; letter-spacing: .04em;
  }
  .side a, .side button.navlink {
    display: block; width: 100%; text-align: left;
    padding: 8px 10px; border-radius: 8px; color: var(--text);
    text-decoration: none; background: transparent; border: none;
    font: inherit; cursor: pointer; font-size: 13px;
  }
  .side a:hover, .side button.navlink:hover { background: var(--primary-soft); color: var(--primary); }
  .side a.active, .side button.navlink.active {
    background: var(--primary-soft); color: var(--primary); font-weight: 600;
  }
  .side .sep { height: 1px; background: var(--border); margin: 10px 6px; }
  .detail-main .hero { margin-bottom: 14px; }
  .detail-main .hero .big { font-size: 26px; }
  .prose { color: var(--text-2); font-size: 13px; line-height: 1.65; }
  .prose h2, .prose h3, .prose h4 {
    margin: 14px 0 6px; font-size: 13px; font-weight: 650; color: var(--text);
  }
  .prose h2:first-child, .prose h3:first-child, .prose h4:first-child { margin-top: 0; }
  .prose p { margin: 0 0 8px; font-size: 13px; color: var(--text-2); }
  .prose ul, .prose ol {
    margin: 0 0 8px; padding-left: 1.15em;
    list-style: disc;
  }
  .prose ol { list-style: disc; }
  .prose li { margin: 3px 0; font-size: 13px; color: var(--text-2); }
  .prose b, .prose strong { color: var(--text); font-weight: 600; }
  .prose code {
    background: #f2f3f5; border: 1px solid var(--border); border-radius: 4px;
    padding: 1px 5px; font-size: 12px; color: var(--text);
  }
  .prose pre {
    background: #f2f3f5; border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 12px; overflow: auto; font-size: 12px; color: var(--text);
  }
  .prose table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0 10px; color: var(--text); }
  .prose th, .prose td { border: 1px solid var(--border); padding: 7px 9px; text-align: left; }
  .prose th { background: #fafbfc; color: var(--text-2); font-weight: 500; }
  .prose .hint, .section-bd .hint { color: var(--text-2); font-size: 12px; }
  .empty-block {
    padding: 12px 14px; border-radius: 8px; background: var(--warn-soft); color: #a34d00; font-size: 13px;
  }
  .section-bd.nested {
    display: flex; flex-direction: column; gap: 10px;
    padding: 12px; background: var(--bg);
  }
  .subcard {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px 14px;
  }
  .subcard-hd {
    font-size: 13px; font-weight: 650; color: var(--text); margin-bottom: 6px;
  }
  .subcard-hd:empty { display: none; }
  .subcard .prose { margin: 0; }

  .preview-note {
    font-size: 12px; color: var(--text-2); margin: 0 0 12px;
    padding: 8px 12px; background: var(--primary-soft); border-radius: 8px;
  }

  /* A · 能力主线 */
  .cap-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
  .cap-chip {
    border: 1px solid var(--border); background: #fff; color: var(--text-2);
    border-radius: 999px; padding: 7px 12px; font: inherit; font-size: 13px;
    cursor: pointer;
  }
  .cap-chip:hover { border-color: #c2d4ff; color: var(--primary); }
  .cap-chip.active {
    background: var(--primary-soft); color: var(--primary);
    border-color: #c2d4ff; font-weight: 650;
  }
  .layout-a-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    align-items: stretch;
  }
  @media (max-width: 900px) { .layout-a-grid { grid-template-columns: 1fr; } }
  .layout-a-fill { width: 100%; }
  .cap-blurb {
    font-size: 13px; color: var(--text-2); line-height: 1.6;
    margin: 0 0 12px; padding: 10px 12px;
    background: #fff; border: 1px solid var(--border); border-radius: 8px;
  }
  .timeline .prose ul {
    list-style: none; padding-left: 0; margin: 0;
    border-left: 2px solid #c2d4ff; margin-left: 7px; padding-left: 16px;
  }
  .timeline .prose li {
    position: relative; margin: 10px 0; color: var(--text);
  }
  .timeline .prose li::before {
    content: ""; position: absolute; left: -21px; top: 7px;
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--primary);
  }

  #sec-how-common { margin-bottom: 10px; }
  #sec-how-common .prose p:last-child { margin-bottom: 0; }
</style>
</head>
<body>
  <div class="topbar">
    <div class="logo" id="logoMark">S</div>
    <h1 id="topTitle">Skills 总览</h1>
    <div class="actions">
      <div class="meta">
        <div id="rootPath"></div>
        <div id="genAt"></div>
      </div>
      <button type="button" class="btn btn-ghost hidden" id="btnBack">← 总览</button>
      <select class="skill-switch hidden" id="skillSwitch" aria-label="切换 Skill"></select>
    </div>
  </div>

  <div id="viewOverview">
    <div class="wrap">
      <div class="hero">
        <div class="label">个人 Skills 健康度</div>
        <div class="big" id="heroBig">—</div>
        <div class="sub" id="heroSub"></div>
      </div>
      <div class="grid">
        <div class="card card-pass">
          <div class="k">✅ 通过</div>
          <div class="v" id="nPass">—</div>
          <div class="hint">无 warn / fail</div>
        </div>
        <div class="card card-warn">
          <div class="k">⚠️ 需关注</div>
          <div class="v" id="nWarn">—</div>
          <div class="hint">有 warn，无 fail</div>
        </div>
        <div class="card card-fail">
          <div class="k">❌ 缺件</div>
          <div class="v" id="nFail">—</div>
          <div class="hint" id="missHint"></div>
        </div>
      </div>

      <div class="section">
        <div class="section-hd"><span class="dot"></span>Skill 总览</div>
        <div class="filters" id="filters">
          <button type="button" class="chip-btn active" data-filter="all">全部</button>
          <button type="button" class="chip-btn" data-filter="fail">仅缺件</button>
          <button type="button" class="chip-btn" data-filter="warn">仅需关注</button>
          <button type="button" class="chip-btn" data-filter="pass">仅通过</button>
        </div>
        <div class="tag-filters" id="tagFilters"></div>
        <div id="skillList"></div>
      </div>
      <div class="foot">总览看状态与问题 · 单页：需关注/缺件时先列具体问题，再是能做什么 / 使用方法 / 执行步骤</div>
    </div>
  </div>

  <div id="viewDetail" class="hidden">
    <div class="detail-layout" id="detailLayout">
      <nav class="side" id="detailSide" aria-label="本页导航">
        <strong>本页</strong>
        <button type="button" class="navlink" data-scroll="sec-can-do">能做什么</button>
        <button type="button" class="navlink" data-scroll="sec-how-common">使用方法</button>
        <button type="button" class="navlink" data-scroll="sec-execute">执行步骤</button>
      </nav>
      <div class="detail-main" id="detailMain"></div>
    </div>
  </div>

  <div class="ctx-menu hidden" id="ctxMenu"></div>

  <div id="tagModal" class="fix-modal hidden">
    <div class="tag-modal-card">
      <div class="fix-modal-hd" id="tagModalTitle">编辑标签</div>
      <div class="tag-modal-sub">回车添加，保存后写入该 skill 的 <code>tag.txt</code>，总览与筛选立即刷新。</div>
      <div class="label-sm">当前标签</div>
      <div class="tag-box" id="tagCurrent"></div>
      <div class="label-sm">已有标签（点一下加进来）</div>
      <div class="tag-cand" id="tagCand"></div>
      <div class="tag-new">
        <input id="tagInput" type="text" placeholder="新标签，回车添加" maxlength="24" />
        <button type="button" class="btn btn-ghost" id="tagAdd">添加</button>
      </div>
      <div class="tag-err" id="tagErr"></div>
      <div class="fix-modal-actions">
        <button type="button" class="btn btn-ghost" id="tagCancel">取消</button>
        <button type="button" class="fix-btn" id="tagSave">保存</button>
      </div>
    </div>
  </div>

  <div id="fixModal" class="fix-modal hidden">
    <div class="fix-modal-card">
      <div class="fix-modal-hd">修复提示词</div>
      <textarea id="promptText" readonly rows="12"></textarea>
      <div class="fix-modal-actions">
        <button type="button" class="btn btn-ghost" id="fixClose">关闭</button>
        <button type="button" class="fix-btn" id="promptCopy">复制提示词</button>
      </div>
    </div>
  </div>

<script>
let DATA = __DATA__;
let filter = "all";
let refreshTimer = null;
const selectedCapBySkill = {};
const WRITE_TOKEN = __WRITE_TOKEN__;
let tagFilter = [];
let tagMenuOpen = false;
let tagDraft = { folder: null, tags: [] };

async function refreshData() {
  try {
    const r = await fetch("/api/skills", { cache: "no-store" });
    if (!r.ok) return;
    const next = await r.json();
    if (next && Array.isArray(next.skills)) {
      DATA = next;
    }
  } catch (_) { /* keep embedded DATA */ }
}

function scheduleRefreshAndRoute() {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    await refreshData();
    route();
  }, 0);
}

function statusLabel(s) {
  if (s === "pass") return "✅ 通过";
  if (s === "warn") return "⚠️ 需关注";
  return "❌ 缺件";
}
function statusIcon(st) {
  if (st === "pass") return "✅";
  if (st === "warn") return "⚠️";
  return "❌";
}

function authoringSpecPath() {
  const root = String(DATA.skills_root || "").replace(/[\\/]+$/, "");
  const sep = root.includes("\\") ? "\\" : "/";
  return root + sep + "skills-check" + sep + "references" + sep + "skill-authoring.md";
}
function buildFixPrompt(s, issue) {
  const path = s.path || s.folder;
  const spec = `先读 ${authoringSpecPath()}，再读该 skill 的 cross-reference.md，按规范改完并同步人类页。不要扩大范围。`;
  if (issue) {
    const level = issue.level === "fail" ? "缺件" : "需关注";
    return `请用 /skills-check 规范修复这个 skill 的 Review 问题。\n\nSkill：${s.folder}\n路径：${path}\n级别：${level}\n问题：${issue.text}\n\n${spec}`;
  }
  const list = (s.issues || []).map((i, n) =>
    `${n + 1}. [${i.level === "fail" ? "缺件" : "需关注"}] ${i.text}`
  ).join("\n");
  return `请用 /skills-check 规范修复 skill「${s.folder}」的全部 Review 问题。\n\n路径：${path}\n\n${list}\n\n${spec}`;
}

function issueLineHtml(s, issue) {
  const tag = issue.level === "fail" ? "缺件" : "需关注";
  const prompt = encodeURIComponent(buildFixPrompt(s, issue));
  return `<div class="issue-line ${issue.level}"><span class="tag">${tag}</span><span class="issue-text">${escapeHtml(issue.text)}</span><button type="button" class="fix-btn" data-prompt="${prompt}">复制提示词</button></div>`;
}
function findSkill(folder) {
  return (DATA.skills || []).find((s) => s.folder === folder) || null;
}
function parseRoute() {
  const h = (location.hash || "#/").replace(/^#/, "");
  const m = h.match(/^\/?skill\/([^/?#]+)/);
  if (m) return { view: "detail", folder: decodeURIComponent(m[1]) };
  return { view: "overview", folder: null };
}
function goOverview() { location.hash = "#/"; }
function goSkill(folder) { location.hash = "#/skill/" + encodeURIComponent(folder); }
function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function tagCounts() {
  const counts = DATA.tag_counts || {};
  const used = Object.keys(counts).filter((t) => counts[t] > 0);
  used.sort((a, b) => (counts[b] - counts[a]) || a.localeCompare(b, "zh"));
  return { counts, used };
}

function hasActiveFilter() {
  return filter !== "all" || tagFilter.length > 0;
}

function clearFilters() {
  filter = "all";
  tagFilter = [];
  tagMenuOpen = false;
  document.querySelectorAll("#filters .chip-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.filter === "all")
  );
  renderOverview();
}

function resetBtnHtml() {
  return hasActiveFilter()
    ? `<button type="button" class="tag-reset" data-reset="1">清除筛选</button>`
    : "";
}

function setTagMenuOpen(open) {
  tagMenuOpen = open;
  const btn = document.getElementById("tagDdBtn");
  const menu = document.getElementById("tagDdMenu");
  if (!btn || !menu) return;
  btn.classList.toggle("open", open);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  menu.classList.toggle("hidden", !open);
}

function renderTagFilters() {
  const box = document.getElementById("tagFilters");
  const { counts, used } = tagCounts();
  tagFilter = tagFilter.filter((t) => used.includes(t));
  if (!used.length) {
    tagMenuOpen = false;
    box.innerHTML = '<span class="lead">还没有标签 · 右键任意 skill 可以加</span>' + resetBtnHtml();
    return;
  }
  const label = tagFilter.length === 1 ? tagFilter[0]
    : (tagFilter.length > 1 ? `已选 ${tagFilter.length} 个` : "全部");
  const rows = used.map((t) => {
    const on = tagFilter.includes(t) ? " checked" : "";
    return `<label><input type="checkbox" data-tag="${escapeHtml(t)}"${on} /><span>${escapeHtml(t)}</span><span class="n">${counts[t]}</span></label>`;
  }).join("");
  box.innerHTML = `<span class="lead">标签</span>`
    + `<div class="tag-dd">`
    + `<button type="button" class="tag-dd-btn${tagMenuOpen ? " open" : ""}" id="tagDdBtn" aria-haspopup="listbox" aria-expanded="${tagMenuOpen ? "true" : "false"}">${escapeHtml(label)}</button>`
    + `<div class="tag-dd-menu${tagMenuOpen ? "" : " hidden"}" id="tagDdMenu">`
    + rows
    + `</div></div>`
    + resetBtnHtml();
}

function renderOverview() {
  document.getElementById("viewOverview").classList.remove("hidden");
  document.getElementById("viewDetail").classList.add("hidden");
  document.getElementById("btnBack").classList.add("hidden");
  document.getElementById("skillSwitch").classList.add("hidden");
  document.getElementById("topTitle").textContent = "Skills 总览";
  document.getElementById("logoMark").textContent = "S";
  document.title = "Skills 总览";

  document.getElementById("rootPath").textContent = DATA.skills_root;
  document.getElementById("genAt").textContent = "生成于 " + DATA.generated_at;
  const sum = DATA.summary;
  document.getElementById("heroBig").textContent = sum.total + " 个 Skill";
  document.getElementById("heroSub").textContent =
    `通过 ${sum.pass} · 需关注 ${sum.warn} · 缺件 ${sum.fail}`;
  document.getElementById("nPass").textContent = sum.pass;
  document.getElementById("nWarn").textContent = sum.warn;
  document.getElementById("nFail").textContent = sum.fail;
  const missParts = [];
  if (sum.missing_readme) missParts.push(`README ${sum.missing_readme}`);
  if (sum.missing_review_usage) missParts.push(`review-usage ${sum.missing_review_usage}`);
  if (sum.missing_open_script) missParts.push(`open-review ${sum.missing_open_script}`);
  const missSkills = (DATA.skills || [])
    .filter((s) => s.status === "fail")
    .map((s) => s.folder);
  let missHint = "companion 齐全";
  if (missParts.length || missSkills.length) {
    const bits = [];
    if (missParts.length) bits.push(missParts.join(" · "));
    if (missSkills.length) bits.push("涉及 " + missSkills.join("、"));
    missHint = bits.join(" · ");
  }
  document.getElementById("missHint").textContent = missHint;
  renderTagFilters();
  const list = document.getElementById("skillList");
  list.innerHTML = "";
  const skills = (DATA.skills || [])
    .filter((s) => filter === "all" || s.status === filter)
    .filter((s) => !tagFilter.length || (s.tags || []).some((t) => tagFilter.includes(t)));
  if (!skills.length) {
    list.innerHTML = '<div class="empty">当前筛选下没有 Skill</div>';
    return;
  }
  skills.forEach((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "skill-row";
    const issuesHtml = (s.issues && s.issues.length)
      ? `<div class="issues">${s.issues.map((i) => issueLineHtml(s, i)).join("")}</div>`
      : "";
    const tags = (s.tags && s.tags.length) ? s.tags : (s.tag ? [s.tag] : []);
    const tagHtml = tags.map((t) =>
      `<span class="skill-tag">${escapeHtml(t)}</span>`
    ).join("");
    const countBadge = (s.status === "pass")
      ? ""
      : `<span class="badge neutral">${s.counts.fail} fail · ${s.counts.warn} warn</span>`;
    btn.innerHTML = `
      <div>
        <div class="name-row">
          <span class="name">${escapeHtml(s.folder)}</span>
          ${tagHtml}
        </div>
        <div class="intro">${escapeHtml(s.intro || "")}</div>
        ${issuesHtml}
        <div class="go">进入 Review →</div>
      </div>
      <div class="badges">
        <span class="badge ${s.status}">${statusLabel(s.status)}</span>
        ${countBadge}
      </div>`;
    btn.addEventListener("click", (ev) => {
      if (ev.target.closest(".fix-btn")) return;
      goSkill(s.folder);
    });
    btn.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      openCtxMenu(ev.clientX, ev.clientY, s);
    });
    list.appendChild(btn);
  });
}

function fillSkillSwitch(active) {
  const sel = document.getElementById("skillSwitch");
  sel.innerHTML = "";
  (DATA.skills || []).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.folder;
    opt.textContent = `${statusIcon(s.status)} ${s.folder}`;
    if (s.folder === active) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.classList.remove("hidden");
}

function issuesSectionHtml(s) {
  if (s.status !== "warn" && s.status !== "fail") return "";
  const items = (s.issues || []).map((i) => issueLineHtml(s, i)).join("");
  const allBtn = (s.issues && s.issues.length > 1)
    ? `<button type="button" class="fix-btn" data-prompt="${encodeURIComponent(buildFixPrompt(s))}">复制全部提示词</button>`
    : "";
  return `
    <div class="problems-block" id="sec-problems">
      ${items || ""}
      ${allBtn}
    </div>`;
}

function commonHowHtml(c) {
  if ((c.usage_prose || "").trim()) {
    return `<div class="prose">${c.usage_prose}</div>`;
  }
  const commonCards = c.usage_common_cards || [];
  if (commonCards.length) {
    return commonCards.map((card) =>
      `<div class="prose">${card.html || ""}</div>`
    ).join("");
  }
  return "";
}
function innerCards(cards, fallbackHtml) {
  if (Array.isArray(cards) && cards.length) {
    return cards.map((card) =>
      `<div class="subcard">` +
        (card.title ? `<div class="subcard-hd">${escapeHtml(card.title)}</div>` : "") +
        `<div class="prose">${card.html || ""}</div>` +
      `</div>`
    ).join("");
  }
  if (!(fallbackHtml || "").trim()) return "";
  return `<div class="subcard"><div class="prose">${fallbackHtml}</div></div>`;
}

function scrollToSection(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const top = el.getBoundingClientRect().top + window.scrollY - 72;
  window.scrollTo({ top, behavior: "smooth" });
}

function heroHtml(s, c) {
  const tags = (s.tags && s.tags.length) ? s.tags : (s.tag ? String(s.tag).split("·").map((x) => x.trim()).filter(Boolean) : []);
  const tagHtml = tags.map((t) =>
    `<span class="skill-tag">${escapeHtml(t)}</span>`
  ).join("");
  return `
    <div class="hero">
      <div class="label">Skill Review</div>
      <div class="big"><span>${escapeHtml(c.title || s.display_title || s.folder)}</span>${tagHtml}</div>
      <div class="sub">${escapeHtml(c.blurb || s.intro || "")}</div>
      <div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px">
        <span class="badge ${s.status}">${statusLabel(s.status)}</span>
        <span class="badge neutral">${s.skill_lines} 行 SKILL.md</span>
      </div>
    </div>`;
}

function renderSideNavA(caps, activeId) {
  const side = document.getElementById("detailSide");
  side.classList.remove("hidden");
  const links = (caps || []).map((cap) =>
    `<button type="button" class="navlink${cap.id === activeId ? " active" : ""}" data-cap="${escapeHtml(cap.id)}">${escapeHtml(cap.title)}</button>`
  ).join("");
  side.innerHTML = `<strong>能做什么</strong>${links || "<span class='hint'>暂无拆项</span>"}`;
}

function renderDetailA(s, c) {
  const caps = c.capabilities || [];
  if (!selectedCapBySkill[s.folder] && caps.length) {
    selectedCapBySkill[s.folder] = caps[0].id;
  }
  const cur = caps.find((x) => x.id === selectedCapBySkill[s.folder]) || caps[0] || null;
  renderSideNavA(caps, cur ? cur.id : "");
  const chips = caps.map((cap) =>
    `<button type="button" class="cap-chip${cur && cap.id === cur.id ? " active" : ""}" data-cap="${escapeHtml(cap.id)}">${escapeHtml(cap.title)}</button>`
  ).join("");
  const blurb = cur && cur.can_do_html
    ? `<div class="cap-blurb">${cur.can_do_html}</div>`
    : "";
  const commonHtml = commonHowHtml(c);
  const commonBlock = commonHtml
    ? `<div class="section" id="sec-how-common">
        <div class="section-hd"><span class="dot"></span>使用方法</div>
        <div class="section-bd">${commonHtml}</div>
      </div>`
    : "";
  const detailed = !!(cur && cur.needs_detail);
  const hasUsage = !!(cur && Array.isArray(cur.usage_cards) && cur.usage_cards.length);
  const hasSteps = !!(cur && (cur.execute_html || "").trim());
  const capUsage = hasUsage ? innerCards(cur.usage_cards, "") : "";
  const steps = hasSteps ? `<div class="prose">${cur.execute_html}</div>` : "";
  const howBlock = hasUsage
    ? `<div class="section" id="sec-how-to-use">
        <div class="section-hd"><span class="dot"></span>功能</div>
        <div class="section-bd nested">${capUsage}</div>
      </div>`
    : "";
  const execBlock = hasSteps
    ? `<div class="section${hasUsage ? "" : " layout-a-fill"}" id="sec-execute">
        <div class="section-hd"><span class="dot"></span>执行步骤 · ${escapeHtml(cur.title)}</div>
        <div class="section-bd timeline">${steps}</div>
      </div>`
    : (detailed
      ? `<div class="section" id="sec-execute"><div class="section-hd"><span class="dot"></span>执行步骤 · ${escapeHtml(cur.title)}</div></div>`
      : "");
  const detailGrid = (hasUsage && hasSteps)
    ? `<div class="layout-a-grid">${howBlock}${execBlock}</div>`
    : `${howBlock}${execBlock}`;
  document.getElementById("detailMain").innerHTML = `
    ${heroHtml(s, c)}
    ${issuesSectionHtml(s)}
    ${commonBlock}
    <div class="cap-chips">${chips}</div>
    ${blurb}
    ${detailGrid}
  `;
}

function renderDetail(folder) {
  const s = findSkill(folder);
  if (!s) { goOverview(); return; }

  document.getElementById("viewOverview").classList.add("hidden");
  document.getElementById("viewDetail").classList.remove("hidden");
  document.getElementById("btnBack").classList.remove("hidden");
  document.getElementById("topTitle").textContent = "Skill Review";
  document.getElementById("logoMark").textContent = "R";
  document.title = s.folder + " · Skill Review";
  document.getElementById("rootPath").textContent = s.path;
  document.getElementById("genAt").textContent = DATA.generated_at;
  fillSkillSwitch(folder);

  const layout = document.getElementById("detailLayout");
  layout.classList.add("layout-a");
  layout.classList.remove("layout-d");

  const c = s.content || {};
  renderDetailA(s, c);
  window.scrollTo(0, 0);
}

function route() {
  const r = parseRoute();
  if (r.view === "detail") renderDetail(r.folder);
  else renderOverview();
}

document.getElementById("filters").addEventListener("click", (e) => {
  const btn = e.target.closest(".chip-btn");
  if (!btn) return;
  filter = btn.dataset.filter;
  document.querySelectorAll("#filters .chip-btn").forEach((b) => b.classList.toggle("active", b === btn));
  renderOverview();
});
document.getElementById("tagFilters").addEventListener("click", (e) => {
  e.stopPropagation();
  if (e.target.closest("#tagDdBtn")) {
    setTagMenuOpen(!tagMenuOpen);
    return;
  }
  if (e.target.closest("[data-reset]")) {
    clearFilters();
  }
});
document.getElementById("tagFilters").addEventListener("change", (e) => {
  const box = e.target.closest("input[data-tag]");
  if (!box) return;
  const tag = box.dataset.tag;
  if (box.checked) {
    if (!tagFilter.includes(tag)) tagFilter = tagFilter.concat([tag]);
  } else {
    tagFilter = tagFilter.filter((t) => t !== tag);
  }
  tagMenuOpen = true;
  renderOverview();
});
document.getElementById("ctxMenu").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const folder = document.getElementById("ctxMenu").dataset.folder;
  closeCtxMenu();
  if (btn.dataset.act === "tags") openTagModal(folder);
  else if (btn.dataset.act === "open") goSkill(folder);
  else if (btn.dataset.act === "prompt") {
    const s = findSkill(folder);
    if (s) showFixPrompt(buildFixPrompt(s, null));
  }
});
document.getElementById("tagCurrent").addEventListener("click", (e) => {
  const drop = e.target.closest("button[data-drop]");
  if (!drop) return;
  tagDraft.tags = tagDraft.tags.filter((t) => t !== drop.dataset.drop);
  renderTagDraft();
});
document.getElementById("tagCand").addEventListener("click", (e) => {
  const pick = e.target.closest("button[data-pick]");
  if (pick) addTagDraft(pick.dataset.pick);
});
document.getElementById("tagAdd").addEventListener("click", () => {
  const input = document.getElementById("tagInput");
  addTagDraft(input.value);
  input.value = "";
  input.focus();
});
document.getElementById("tagInput").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  e.preventDefault();
  addTagDraft(e.target.value);
  e.target.value = "";
});
document.getElementById("tagCancel").addEventListener("click", closeTagModal);
document.getElementById("tagSave").addEventListener("click", saveTagDraft);
document.addEventListener("contextmenu", (e) => {
  if (!e.target.closest(".skill-row")) closeCtxMenu();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  closeCtxMenu();
  if (tagMenuOpen) setTagMenuOpen(false);
  if (!document.getElementById("tagModal").classList.contains("hidden")) closeTagModal();
});
document.getElementById("btnBack").addEventListener("click", goOverview);
document.getElementById("skillSwitch").addEventListener("change", (e) => goSkill(e.target.value));
document.getElementById("viewDetail").addEventListener("click", (e) => {
  const capBtn = e.target.closest("[data-cap]");
  if (capBtn) {
    e.preventDefault();
    const r = parseRoute();
    if (!r.folder) return;
    selectedCapBySkill[r.folder] = capBtn.getAttribute("data-cap");
    renderDetail(r.folder);
    return;
  }
  const scrollBtn = e.target.closest("[data-scroll]");
  if (!scrollBtn) return;
  e.preventDefault();
  scrollToSection(scrollBtn.getAttribute("data-scroll"));
});
function closeCtxMenu() {
  document.getElementById("ctxMenu").classList.add("hidden");
}
function openCtxMenu(x, y, s) {
  const menu = document.getElementById("ctxMenu");
  const items = [`<button type="button" data-act="tags">编辑标签</button>`,
    `<button type="button" data-act="open">进入 Review 页</button>`];
  if ((s.issues || []).length) {
    items.push(`<button type="button" data-act="prompt">复制修复提示词</button>`);
  }
  menu.innerHTML = items.join("");
  menu.dataset.folder = s.folder;
  menu.classList.remove("hidden");
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, window.innerWidth - r.width - 8) + "px";
  menu.style.top = Math.min(y, window.innerHeight - r.height - 8) + "px";
}

function openTagModal(folder) {
  const s = findSkill(folder);
  if (!s) return;
  tagDraft = { folder: folder, tags: (s.tags || []).slice() };
  document.getElementById("tagModalTitle").textContent = "编辑标签 · " + folder;
  document.getElementById("tagErr").textContent = "";
  document.getElementById("tagInput").value = "";
  renderTagDraft();
  document.getElementById("tagModal").classList.remove("hidden");
  document.getElementById("tagInput").focus();
}
function closeTagModal() {
  document.getElementById("tagModal").classList.add("hidden");
  tagDraft = { folder: null, tags: [] };
}
function renderTagDraft() {
  const cur = document.getElementById("tagCurrent");
  cur.innerHTML = tagDraft.tags.length
    ? tagDraft.tags.map((t) =>
        `<span class="tag-pill">${escapeHtml(t)}<button type="button" data-drop="${escapeHtml(t)}" aria-label="移除">✕</button></span>`
      ).join("")
    : '<span class="empty-hint">暂无标签 · 保存后该 skill 的 tag.txt 会被删除</span>';
  const options = (DATA.tag_options || []).filter((t) => !tagDraft.tags.includes(t));
  const cand = document.getElementById("tagCand");
  cand.innerHTML = options.length
    ? options.map((t) => `<button type="button" data-pick="${escapeHtml(t)}">${escapeHtml(t)}</button>`).join("")
    : '<span class="empty-hint">没有可加的已有标签</span>';
}
function addTagDraft(raw) {
  const tag = String(raw || "").replace(/[,\r\n\t]+/g, " ").trim().slice(0, 24);
  const err = document.getElementById("tagErr");
  if (!tag) return;
  if (tagDraft.tags.includes(tag)) { err.textContent = "这个标签已经加过了"; return; }
  if (tagDraft.tags.length >= 8) { err.textContent = "一个 skill 最多 8 个标签"; return; }
  tagDraft.tags.push(tag);
  err.textContent = "";
  renderTagDraft();
}
async function saveTagDraft() {
  const folder = tagDraft.folder;
  if (!folder) return;
  const err = document.getElementById("tagErr");
  const btn = document.getElementById("tagSave");
  btn.disabled = true;
  try {
    const r = await fetch("/api/tag", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Skills-Check-Token": WRITE_TOKEN },
      body: JSON.stringify({ folder: folder, tags: tagDraft.tags }),
    });
    const out = await r.json().catch(() => ({}));
    if (!r.ok || !out.ok) {
      err.textContent = out.error || ("保存失败：HTTP " + r.status);
      return;
    }
    if (out.data && Array.isArray(out.data.skills)) DATA = out.data;
    closeTagModal();
    renderOverview();
  } catch (e) {
    err.textContent = "保存失败：" + e;
  } finally {
    btn.disabled = false;
  }
}

function closeFixModal() {
  document.getElementById("fixModal").classList.add("hidden");
}
async function copyPromptText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) { /* fall through */ }
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    return document.execCommand("copy");
  } catch (_) {
    return false;
  } finally {
    ta.remove();
  }
}
function showFixPrompt(prompt) {
  const ta = document.getElementById("promptText");
  ta.value = prompt;
  document.getElementById("fixModal").classList.remove("hidden");
  ta.focus();
  ta.select();
}
document.getElementById("fixClose").addEventListener("click", closeFixModal);
document.getElementById("promptCopy").addEventListener("click", async () => {
  const text = document.getElementById("promptText").value;
  if (!text) return;
  await copyPromptText(text);
  closeFixModal();
});
document.addEventListener("click", (ev) => {
  if (!ev.target.closest("#ctxMenu")) closeCtxMenu();
  const inTags = ev.composedPath().some((n) => n && n.id === "tagFilters");
  if (tagMenuOpen && !inTags) setTagMenuOpen(false);
  const openBtn = ev.target.closest(".fix-btn[data-prompt]");
  if (openBtn) {
    ev.preventDefault();
    ev.stopPropagation();
    const prompt = decodeURIComponent(openBtn.getAttribute("data-prompt") || "").trim();
    if (prompt) showFixPrompt(prompt);
    return;
  }
  if (ev.target.id === "fixModal" || ev.target.id === "tagModal") {
    ev.preventDefault();
    ev.stopPropagation();
  }
});
window.addEventListener("hashchange", scheduleRefreshAndRoute);
window.addEventListener("pageshow", scheduleRefreshAndRoute);
window.addEventListener("focus", () => { refreshData().then(route); });

if (DATA.initial_folder) {
  location.hash = "#/skill/" + encodeURIComponent(DATA.initial_folder);
}
scheduleRefreshAndRoute();
</script>
</body>
</html>
"""


def render_html(data: dict, write_token: str = "") -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__DATA__", payload).replace(
        "__WRITE_TOKEN__", json.dumps(write_token)
    )


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Do not SO_REUSEADDR here — on Windows it can report "free" while
            # another process is still LISTENing, which stacked zombie servers.
            s.bind((host, port))
            return True
        except OSError:
            return False


def stop_previous_review_servers(*, keep_pid: int | None = None) -> int:
    """
    End other skills-check-viewer.py processes so /skills-check and -review always
    load the latest script on the canonical port (not a leftover old process).
    """
    keep = keep_pid if keep_pid is not None else os.getpid()
    killed = 0
    if sys.platform == "win32":
        ps = f"""
$keep = {keep}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {{
    $_.Name -match '^python' -and
    $_.ProcessId -ne $keep -and
    $_.CommandLine -and
    ($_.CommandLine -like '*{VIEWER_PROC_MARK}*')
  }} |
  ForEach-Object {{
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $_.ProcessId
  }}
"""
        try:
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            for line in (r.stdout or "").splitlines():
                if line.strip().isdigit():
                    killed += 1
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"警告: 结束旧 Review 进程失败: {exc}", flush=True)
    else:
        try:
            r = subprocess.run(
                ["pgrep", "-f", VIEWER_PROC_MARK],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in (r.stdout or "").splitlines():
                pid_s = line.strip()
                if not pid_s.isdigit():
                    continue
                pid = int(pid_s)
                if pid == keep:
                    continue
                try:
                    os.kill(pid, 15)
                    killed += 1
                except OSError:
                    pass
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"警告: 结束旧 Review 进程失败: {exc}", flush=True)
    return killed


def wait_port_free(host: str, port: int, *, timeout_s: float = 8.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _port_free(host, port):
            return True
        time.sleep(0.15)
    return _port_free(host, port)


def pick_port(host: str, preferred: int, tries: int = 20) -> int:
    for i in range(tries):
        port = preferred + i
        if _port_free(host, port):
            return port
    raise SystemExit(f"端口 {preferred}–{preferred + tries - 1} 均被占用，请用 --port 指定")


def serve_report(
    skills_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    initial_folder: str | None = None,
    open_browser: bool = True,
    restart: bool = True,
) -> str:
    """Serve Review HTML. /skills-check and -review restart old servers so script code is fresh.
    Browser refresh only re-scans skill files (not this .py).
    """
    if restart:
        n = stop_previous_review_servers()
        if n:
            print(f"已结束旧 Review 进程: {n} 个（加载最新脚本）", flush=True)
        if not wait_port_free(host, port):
            print(
                f"警告: 端口 {port} 仍被占用，将尝试顺延",
                flush=True,
            )

    port = pick_port(host, port)
    lock = threading.Lock()

    write_token = secrets.token_urlsafe(18)
    allowed_origins = {
        f"http://{host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }

    def build_body() -> bytes:
        with lock:
            data = scan_skills(skills_root)
            data["initial_folder"] = initial_folder
            return render_html(data, write_token).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path != "/api/tag":
                self.send_error(404, "Not Found")
                return
            if self.headers.get("X-Skills-Check-Token") != write_token:
                self._send_json(403, {"error": "token 不匹配，请重开 Review 页"})
                return
            site = self.headers.get("Sec-Fetch-Site")
            if site and site not in ("same-origin", "same-site", "none"):
                self._send_json(403, {"error": "拒绝跨站写入"})
                return
            origin = self.headers.get("Origin")
            if origin and origin not in allowed_origins:
                self._send_json(403, {"error": "拒绝跨站写入"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > 64 * 1024:
                self._send_json(400, {"error": "请求体长度不合法"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                with lock:
                    tags = write_skill_tags(
                        skills_root, payload.get("folder"), payload.get("tags")
                    )
                    data = scan_skills(skills_root)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})
                return
            data["initial_folder"] = initial_folder
            self._send_json(200, {"ok": True, "tags": tags, "data": data})

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path == "/api/skills":
                try:
                    with lock:
                        data = scan_skills(skills_root)
                        data["initial_folder"] = initial_folder
                    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                except Exception as exc:  # noqa: BLE001
                    msg = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(msg)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(msg)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if path in ("/", "/index.html", "/review"):
                try:
                    body = build_body()
                except Exception as exc:  # noqa: BLE001 — surface scan errors in browser
                    msg = f"扫描失败: {exc}".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(msg)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(msg)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404, "Not Found")

        def log_message(self, fmt: str, *args) -> None:
            if args and str(args[0]).startswith(("4", "5")):
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    if initial_folder:
        open_url = url + "#/skill/" + initial_folder
    else:
        open_url = url

    print(
        f"本地服务: {url}  （浏览器刷新=重扫 skill 文件；"
        f"/skills-check 或 -review=重启服务加载最新 .py；Ctrl+C 结束）",
        flush=True,
    )
    if initial_folder:
        print(f"单 skill: {open_url}", flush=True)
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(open_url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务")
    finally:
        server.server_close()
    return url


def print_summary(data: dict) -> None:
    s = data["summary"]
    print(f"根目录: {data['skills_root']}")
    print(f"Skill 数: {s['total']}")
    print(f"通过: {s['pass']} · 需关注: {s['warn']} · 缺件: {s['fail']}")
    print(
        f"缺 README: {s['missing_readme']} · 缺 review-usage: {s['missing_review_usage']}"
    )
    print("-" * 56)
    for sk in data["skills"]:
        flag = {"pass": "OK", "warn": "!!", "fail": "XX"}[sk["status"]]
        print(
            f"[{flag}] {sk['folder']:<28} "
            f"P{sk['counts']['pass']} W{sk['counts']['warn']} F{sk['counts']['fail']}"
        )
        print(f"      简介: {sk['intro']}")
        for issue in sk["issues"]:
            print(f"      - {issue['level']}: {issue['text']}")


def resolve_skill_arg(skill_arg: str) -> tuple[Path, Path]:
    """Return (skills_root, skill_folder)."""
    skill = Path(skill_arg).expanduser().resolve()
    if skill.is_file() and skill.name.lower() == "skill.md":
        skill = skill.parent
    if not (skill / "SKILL.md").is_file():
        raise SystemExit(f"不是 skill 目录（缺 SKILL.md）: {skill}")
    root = skill.parent
    return root, skill


OPEN_REVIEW_PS1 = r"""# Open Feishu-style Review for this skill (sibling switcher included).
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\open-review.ps1
$ErrorActionPreference = 'Stop'
$SkillRoot = Split-Path -Parent $PSScriptRoot
$SkillsRoot = Split-Path -Parent $SkillRoot
$Viewer = Join-Path $SkillsRoot 'skills-check\scripts\skills-check-viewer.py'
if (-not (Test-Path -LiteralPath $Viewer)) {
    throw "找不到 skills-check-viewer.py: $Viewer"
}
python $Viewer --skill $SkillRoot
"""


def ensure_open_review_scripts(skills_root: Path) -> list[str]:
    """Write/update scripts/open-review.ps1 in each skill. Returns written folders."""
    written: list[str] = []
    for skill in list_skill_dirs(skills_root):
        scripts = skill / "scripts"
        scripts.mkdir(exist_ok=True)
        path = scripts / "open-review.ps1"
        path.write_text(OPEN_REVIEW_PS1.lstrip("\n"), encoding="utf-8", newline="\n")
        written.append(skill.name)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="扫描个人 Agent skills → 飞书风格总览 + 单 skill Review"
    )
    parser.add_argument(
        "root",
        nargs="?",
        help="skills 根目录（默认：本脚本所在 skill 的上一级）；与 --skill 二选一优先 --skill",
    )
    parser.add_argument(
        "--skill",
        help="某个 skill 目录：打开总览数据并直接进入该 skill 单页",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="只打印摘要，不打开浏览器、不启服务",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"本地 HTTP 端口（默认 {DEFAULT_PORT}；先结束旧 Review 后再占用）",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="只启服务，不自动打开浏览器",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="不结束已有 Review 进程（默认会结束旧进程以加载最新脚本）",
    )
    parser.add_argument(
        "--write-open-scripts",
        action="store_true",
        help="在每个 skill 下写入/更新 scripts/open-review.ps1 后退出（可与扫描合用）",
    )
    args = parser.parse_args()

    initial_folder: str | None = None
    if args.skill:
        root, skill = resolve_skill_arg(args.skill)
        initial_folder = skill.name
    elif args.root:
        root = Path(args.root).expanduser().resolve()
    else:
        root = default_skills_root()

    if not root.is_dir():
        raise SystemExit(f"找不到 skills 目录: {root}")

    if args.write_open_scripts:
        written = ensure_open_review_scripts(root)
        print(f"已写入 open-review.ps1: {len(written)} 个 → {', '.join(written)}")

    data = scan_skills(root)
    data["initial_folder"] = initial_folder
    print_summary(data)

    if args.print:
        return

    serve_report(
        root,
        host=args.host,
        port=args.port,
        initial_folder=initial_folder,
        open_browser=not args.no_browser,
        restart=not args.no_restart,
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
