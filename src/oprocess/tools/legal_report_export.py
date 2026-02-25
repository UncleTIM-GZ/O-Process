"""Export Demo 5 legal DD report to Word (body/appendix separated).

Parses a Demo 5 markdown report and generates a Dentons China (大成)
format Word document where:
- Cover page with firm branding
- Main body contains only business content (事实核查, 法律意见, 风险判断)
- Appendix A contains PCF node mapping (x.1 MCP sections)
- Appendix B contains ProvenanceChain data (x.N 溯源链 sections)
- Signature page
"""

from __future__ import annotations

import re
from pathlib import Path

from oprocess.tools._docx_builder import build_docx

# Pre-compiled regex patterns
_RE_CODE_BLOCK = re.compile(r"^```[^\n]*\n.*?\n```", re.MULTILINE | re.DOTALL)
_RE_CODE_PLACEHOLDER = re.compile(r"__CODE_(\d+)__")
_RE_CHAPTER = re.compile(r"^## (.+)$", re.MULTILINE)
_RE_SUBSECTION = re.compile(r"^### (.+)$", re.MULTILINE)
_RE_BLOCKQUOTE_FIELD = re.compile(r">\s*\*\*(.+?)[：:]\*\*\s*(.+)")
_RE_H1_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def export_legal_report(md_path: str, output_path: str) -> dict:
    """Export Demo 5 markdown to Dentons-format Word document."""
    md = Path(md_path).read_text(encoding="utf-8")
    sections = _split_sections(md)
    doc = build_docx(sections)
    doc.save(output_path)
    return {
        "chapters": len(sections["body"]),
        "appendix_a_items": len(sections["appendix_a"]),
        "appendix_b_items": len(sections["appendix_b"]),
    }


# ========== Parsing Layer ==========


def _split_sections(md: str) -> dict:
    """Split markdown into body + appendix content."""
    # Stash code blocks to avoid false heading matches
    stash: list[str] = []

    def _stash(m: re.Match) -> str:
        stash.append(m.group(0))
        return f"__CODE_{len(stash) - 1}__"

    cleaned = _RE_CODE_BLOCK.sub(_stash, md)

    # Extract header (everything before first ## chapter)
    first_h2 = _RE_CHAPTER.search(cleaned)
    header = cleaned[: first_h2.start()].strip() if first_h2 else ""

    # Split by H2 headings into [title, content, title, content, ...]
    parts = _RE_CHAPTER.split(cleaned)
    # parts[0] = before first H2, then alternating title/content

    result: dict = {
        "header": _restore(header, stash),
        "title": _extract_title(header),
        "metadata": _extract_metadata(header),
        "body": [],
        "appendix_a": [],
        "appendix_b": [],
        "tail_sections": [],
    }

    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        full_chapter = f"## {title}\n{content}"

        if title.startswith("第") and "章" in title:
            _classify_chapter(title, full_chapter, stash, result)
        elif title.startswith("附录"):
            result["tail_sections"].append(_restore(full_chapter, stash))
        else:
            result["body"].append(_restore(full_chapter, stash))

    return result


def _classify_chapter(
    title: str, chapter_md: str, stash: list[str], result: dict,
) -> None:
    """Classify subsections of a chapter into body vs appendix."""
    # Split by H3 subsections
    sub_parts = _RE_SUBSECTION.split(chapter_md)
    # sub_parts[0] = chapter heading line, then alternating sub_title/sub_content

    body_parts = [sub_parts[0]]  # Always keep chapter heading
    for j in range(1, len(sub_parts), 2):
        sub_title = sub_parts[j].strip()
        sub_content = sub_parts[j + 1] if j + 1 < len(sub_parts) else ""
        full_sub = f"### {sub_title}\n{sub_content}"

        if _is_mcp_section(sub_title):
            result["appendix_a"].append({
                "chapter": title,
                "content": _restore(full_sub, stash),
            })
        elif _is_provenance_section(sub_title):
            result["appendix_b"].append({
                "chapter": title,
                "content": _restore(full_sub, stash),
            })
        elif _is_oprocess_explanation(sub_title):
            result["appendix_a"].append({
                "chapter": title,
                "content": _restore(full_sub, stash),
            })
        else:
            body_parts.append(full_sub)

    result["body"].append(_restore("\n".join(body_parts), stash))


def _is_mcp_section(title: str) -> bool:
    return "MCP" in title and "流程定位" in title


def _is_provenance_section(title: str) -> bool:
    return "溯源链" in title


def _is_oprocess_explanation(title: str) -> bool:
    return "O'Process" in title and "流程框架" in title


def _restore(text: str, stash: list[str]) -> str:
    """Restore stashed code blocks (single-pass regex replacement)."""
    if not stash:
        return text
    return _RE_CODE_PLACEHOLDER.sub(lambda m: stash[int(m.group(1))], text)


def _extract_title(header: str) -> str:
    """Extract H1 title from header section."""
    m = _RE_H1_TITLE.search(header)
    return m.group(1).strip() if m else ""


def _extract_metadata(header: str) -> dict[str, str]:
    """Extract metadata fields from blockquote lines in header.

    Parses lines like: > **委托方:** 广东广盐...
    Returns dict with keys: 委托方, 目标公司, 律所, 基准日, 报告出具日, etc.
    """
    meta: dict[str, str] = {}
    for m in _RE_BLOCKQUOTE_FIELD.finditer(header):
        meta[m.group(1).strip()] = m.group(2).strip()
    return meta
