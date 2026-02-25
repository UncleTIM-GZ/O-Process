---
title: "feat: 报表报告输出工具（正文/附录分离版）"
type: feat
status: completed
date: 2026-02-25
deepened: 2026-02-25
---

# feat: 报表报告输出工具（正文/附录分离版）

## Enhancement Summary

**Deepened on:** 2026-02-25
**Research agents used:** 7（python-docx CJK、Markdown regex、架构审查、简化审查、性能审查、API 文档、模式审查）

### Key Improvements
1. **简化为单文件架构** — 从 2 文件 ~450 行简化为 1 文件 ~200 行（-55%），去掉数据类和冗余 extract_* 函数
2. **CJK 字体方案确认** — 必须通过 `run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')` 设置，样式级别预设避免逐 run 操作
3. **Markdown 解析防御策略** — 先移除代码块再解析标题，避免代码块内 `##` 被误识别

### New Considerations Discovered
- python-docx v1.2.0 最新稳定版（2025-06-16），需要 `>=1.1.0` 以支持 Python 3.12+
- 附录 C（MCP 工具调用）可延迟实现 — x.1 的 MCP 调用已包含在附录 A 材料中
- TOC 用简单字段插入即可，SDT 结构过度复杂
- 表格生成是主要性能瓶颈（~88% 耗时），需预分配行而非逐行 add_row()

---

## Overview

开发一个报表报告输出工具，将 Demo 5 的法律尽调 Markdown 报告转换为正式 Word (.docx) 文档。**核心逻辑**：将 O'Process 的分析和溯源内容（MCP 工具调用、ProvenanceChain JSON、PCF 节点映射）移至附录，正文仅保留法律业务内容（事实核查、法律意见、风险判断），行文不披露分析方法论。

## Problem Statement / Motivation

1. Demo 5 报告（`docs/demos/demo-05-jinyuan-legal-dd-report.md`）是"O'Process 能力展示"格式，每章含 MCP 工具调用和溯源链
2. 正式交付给客户的法律报告不应暴露技术分析方法
3. 需要一个自动化工具将 Markdown 报告按内容类型分离，输出专业的 Word 文档

## Proposed Solution（简化版）

**单文件架构**：`legal_report_export.py`（~200 行），一个公开 API 函数。

```python
def export_legal_report(md_path: str, output_path: str) -> dict:
    """Export Demo 5 markdown to Word with appendix separation.

    Returns: {"chapters": 13, "pcf_nodes": 14, "provenance_chains": 13}
    """
```

**数据流**：
```
Markdown 文件 → _split_sections() → dict → _build_docx() → .docx 文件
```

### 内容分离规则

Demo 5 每章结构：

| 子章节 | 内容类型 | 分类 | 目标位置 |
|--------|---------|------|---------|
| `x.1 MCP 流程定位` | 技术：工具调用示例 + PCF 节点 | `appendix` | 附录 A |
| `x.2 法律事实核查` | 业务：数据表格 + 事实描述 | `body` | 正文 |
| `x.3 法律意见` | 业务：法律分析 | `body` | 正文 |
| `x.4 风险判断` | 业务：风险评级表 | `body` | 正文 |
| `x.5 溯源链` | 技术：ProvenanceChain JSON | `appendix` | 附录 B |

**识别规则（预编译正则）：**
```python
# 模块级别预编译
_RE_MCP = re.compile(r'### \d+\.1\s+MCP\s*流程定位')
_RE_PROV = re.compile(r'### \d+\.5\s+溯源链')
_RE_CHAPTER = re.compile(r'^## 第(.+?)章\s+(.+)$', re.MULTILINE)
_RE_CODE_BLOCK = re.compile(r'^```.*?\n.*?\n```\s*$', re.MULTILINE | re.DOTALL)
```

## Technical Considerations

### 架构决策（更新后）

| 决策 | 选择 | 理由 |
|------|------|------|
| 架构 | **单文件** `legal_report_export.py` | 简化审查确认：解析+构建是紧耦合的单一用途，无需拆分 |
| 数据结构 | **dict** 而非 dataclass | 只做"按正则分割文本"，字典足够，减少 35 行 |
| Word 库 | `python-docx>=1.1.0` | v1.2.0 最新稳定版，v1.1.0+ 修复了 OxmlElement 路径 |
| Markdown 解析 | 正则 + 行级 + **代码块预处理** | 先 strip 代码块避免误匹配，模式预编译 |
| 依赖组 | `[report]` | 区别于现有 `[embed]`，语义更明确 |
| CJK 字体 | **样式级别预设** | 避免逐 run XML 操作，性能提升 6× |
| 附录 | **2 个附录**（A + B） | 附录 C（MCP 调用）延迟实现，内容已在附录 A 中 |

### 依赖变更

```toml
# pyproject.toml
[project.optional-dependencies]
report = ["python-docx>=1.1.0"]
```

### 文件结构

```
src/oprocess/tools/
├── export.py                  # 现有：Markdown 岗位说明书导出（不改动）
└── legal_report_export.py     # 新建：法律报告导出（~200 行）

tests/test_tools/
└── test_legal_report_export.py  # 新建：导出测试
```

### 核心设计（简化后）

```python
"""Export Demo 5 legal DD report to Word (body/appendix separated)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

# ========== 预编译正则 ==========
_RE_CODE_BLOCK = re.compile(r'^```.*?\n.*?\n```\s*$', re.MULTILINE | re.DOTALL)
_RE_CHAPTER = re.compile(r'^## (第.+?章\s+.+)$', re.MULTILINE)
_RE_H3 = re.compile(r'^### (.+)$', re.MULTILINE)
_RE_MCP = re.compile(r'### \d+\.1\s+MCP')
_RE_PROV = re.compile(r'### \d+\.5\s+溯源链')
_RE_TABLE_ROW = re.compile(r'^\|(.+)\|$', re.MULTILINE)
_RE_BOLD = re.compile(r'\*\*(.+?)\*\*')

# ========== 公开 API ==========

def export_legal_report(md_path: str, output_path: str) -> dict:
    """Export Demo 5 markdown to Word with body/appendix separation."""
    md = Path(md_path).read_text(encoding='utf-8')
    sections = _split_sections(md)
    doc = _build_docx(sections)
    doc.save(output_path)
    return {
        "chapters": len(sections["body"]),
        "pcf_nodes": len(sections["appendix_a"]),
        "provenance_chains": len(sections["appendix_b"]),
    }

# ========== 解析层 ==========

def _split_sections(md: str) -> dict:
    """Split markdown into body + appendix. Single-pass with code block safety."""
    # 1. 预处理：标记代码块避免误匹配
    code_blocks = []
    def _stash_code(m):
        code_blocks.append(m.group(0))
        return f"__CODE_{len(code_blocks) - 1}__"
    cleaned = _RE_CODE_BLOCK.sub(_stash_code, md)

    # 2. 提取头部（标题 + 引用块）
    first_chapter = _RE_CHAPTER.search(cleaned)
    header = cleaned[:first_chapter.start()] if first_chapter else ""

    # 3. 按 H2 分割章节，分类 body/appendix
    result = {"header": header, "body": [], "appendix_a": [], "appendix_b": []}
    chapters = _RE_CHAPTER.split(cleaned)[1:]  # [title, content, title, content, ...]

    for i in range(0, len(chapters), 2):
        title = chapters[i]
        content = chapters[i + 1] if i + 1 < len(chapters) else ""
        full = f"## {title}\n{content}"

        # 提取 x.1 MCP → appendix_a
        mcp_match = re.search(r'### \d+\.1\s+MCP.+?(?=### |\Z)', full, re.DOTALL)
        if mcp_match:
            result["appendix_a"].append({"chapter": title.strip(), "content": mcp_match.group(0)})

        # 提取 x.5 溯源链 → appendix_b
        prov_match = re.search(r'### \d+\.5\s+溯源链.+?(?=### |\Z)', full, re.DOTALL)
        if prov_match:
            result["appendix_b"].append({"chapter": title.strip(), "content": prov_match.group(0)})

        # 删除 x.1 和 x.5，剩余 → body
        body = re.sub(r'### \d+\.[15]\s+(MCP|溯源链).+?(?=### |\Z)', '', full, flags=re.DOTALL)
        result["body"].append(body)

    # 4. 还原代码块
    for key in ("header", "body", "appendix_a", "appendix_b"):
        if isinstance(result[key], str):
            for j, block in enumerate(code_blocks):
                result[key] = result[key].replace(f"__CODE_{j}__", block)
        elif isinstance(result[key], list):
            for item in result[key]:
                if isinstance(item, str):
                    for j, block in enumerate(code_blocks):
                        item = item.replace(f"__CODE_{j}__", block)
                elif isinstance(item, dict):
                    for j, block in enumerate(code_blocks):
                        item["content"] = item["content"].replace(f"__CODE_{j}__", block)

    return result

# ========== Word 构建层 ==========

def _build_docx(sections: dict) -> Document:
    """Build Word document from parsed sections."""
    doc = Document()
    _setup_styles(doc)
    _setup_page(doc)
    _add_header(doc, sections["header"])
    _add_toc(doc)
    for chapter_md in sections["body"]:
        _add_markdown(doc, chapter_md)
    doc.add_section(WD_SECTION.NEW_PAGE)
    _add_appendix(doc, "附录 A：流程分类节点映射表", sections["appendix_a"])
    _add_appendix(doc, "附录 B：数据溯源链", sections["appendix_b"])
    return doc

def _setup_styles(doc: Document) -> None:
    """Set CJK fonts at style level (avoids per-run XML ops)."""
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    rPr = style.element.get_or_add_rPr()
    rPr.rFonts.set(qn('w:eastAsia'), '宋体')

def _setup_page(doc: Document) -> None:
    """A4 page with legal margins (GB/T 9704-2012)."""
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)
```

### Word 文档结构

```
┌─────────────────────────────────┐
│  头部信息（标题 + 委托方引用块）    │
├─────────────────────────────────┤
│  目录（TOC 域，右键更新）          │
├─────────────────────────────────┤
│  第一章 报告概述与声明              │  ← body
│  第二章 主体基本情况               │
│  ...                             │
│  第十三章 结论与合作建议            │
├───────── 分节符 ─────────────────┤
│  附录 A：流程分类节点映射表         │  ← x.1 内容
│  附录 B：数据溯源链                │  ← x.5 内容
├─────────────────────────────────┤
│  O'Process 知识库引用声明          │
└─────────────────────────────────┘
```

### Word 样式规范

| 元素 | 字体 | 字号 | 行距 | 实现方式 |
|------|------|------|------|---------|
| 报告标题 | 黑体 | 22pt | 1.5 | Heading 1 + XML eastAsia |
| 章标题（H2） | 黑体 | 16pt | 1.5 | Heading 2 + XML eastAsia |
| 节标题（H3） | 黑体 | 14pt | 1.5 | Heading 3 + XML eastAsia |
| 正文 | 宋体 | 12pt | 1.5 | Normal 样式预设（style 级别） |
| 表格内容 | 宋体 | 10.5pt | 1.2 | 表格单元格 run |
| 代码块 | Consolas | 9pt | 1.0 | 单单元格表格 + 灰色背景 |
| 页面 | A4 | 上下 2.54cm，左右 3.17cm | — | GB/T 9704-2012 标准 |

### CJK 字体关键代码

```python
# ✅ 正确方式：样式级别设置（一次设置，全局生效）
style = doc.styles['Normal']
style.font.name = 'Times New Roman'  # 西文
rPr = style.element.get_or_add_rPr()
rPr.rFonts.set(qn('w:eastAsia'), '宋体')  # 中文

# ✅ 标题字体：单独设置 Heading 样式
for level in range(1, 4):
    h_style = doc.styles[f'Heading {level}']
    h_style.font.name = 'Times New Roman'
    h_rPr = h_style.element.get_or_add_rPr()
    h_rPr.rFonts.set(qn('w:eastAsia'), '黑体')

# ❌ 错误方式：font.name = '宋体' 对中文无效
```

### TOC 插入方案

```python
def _add_toc(doc: Document) -> None:
    """Insert simple TOC field (user updates in Word)."""
    p = doc.add_paragraph()
    run = p.add_run()
    r = run._r
    # begin
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    # instruction
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    # separate
    fld_sep = OxmlElement('w:fldChar')
    fld_sep.set(qn('w:fldCharType'), 'separate')
    # placeholder
    placeholder = OxmlElement('w:t')
    placeholder.text = '右键单击此处更新目录'
    # end
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    r.extend([fld_begin, instr, fld_sep, placeholder, fld_end])
```

### 代码块渲染（单单元格表格方案）

```python
def _add_code_block(doc: Document, code_text: str) -> None:
    """Render code block as single-cell table with gray background."""
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    table.columns[0].width = Cm(14.66)  # A4 - margins
    cell = table.cell(0, 0)
    # 灰色背景
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), 'F5F5F5')
    cell._tc.get_or_add_tcPr().append(shd)
    # 等宽字体
    p = cell.paragraphs[0]
    run = p.add_run(code_text)
    run.font.name = 'Consolas'
    run.font.size = Pt(9)
```

### Markdown → Word 转换规则

| Markdown 元素 | Word 渲染 | 实现细节 |
|---------------|-----------|---------|
| `## 标题` | Heading 2 | `doc.add_heading(text, level=2)` |
| `### 标题` | Heading 3 | `doc.add_heading(text, level=3)` |
| `**粗体**` | Bold run | 正则 `\*\*(.+?)\*\*` + `run.bold = True` |
| 表格 | Word Table | 预分配行 `add_table(rows=N)` + `Table Grid` 样式 |
| `` `code` `` | Consolas 内联 | `run.font.name = 'Consolas'` |
| 代码块 | 单单元格表格 + 灰色背景 | `_add_code_block()` |
| `> 引用` | 缩进段落 | `p.paragraph_format.left_indent = Cm(1)` |
| `- 列表` | List Bullet 样式 | `style='List Bullet'` |
| `1. 列表` | List Number 样式 | `style='List Number'` |

### 性能预估

| 操作 | 预估耗时 | 占比 |
|------|---------|------|
| 读取 Markdown（50KB） | 5ms | 0.3% |
| Regex 解析 + 分类 | 10ms | 0.5% |
| python-docx 构建 | 1.5s | 88% |
| CJK 字体设置（样式级别） | 50ms | 3% |
| 写入 .docx | 80ms | 5% |
| **总计** | **~1.7s** | — |

**性能优化要点：**
- 表格预分配行：`add_table(rows=N, cols=M)` 而非逐行 `add_row()`
- CJK 字体在样式级别设置（50ms vs 逐 run 500ms）
- 正则模块级别预编译

### 边界情况处理

| 场景 | 策略 |
|------|------|
| 代码块内含 `##` 标题 | 预处理 strip 代码块，解析后还原 |
| x.1 或 x.5 缺失 | 对应附录条目跳过，不报错 |
| ProvenanceChain JSON 格式错误 | 以原始文本放入附录 B |
| 业务内容含 PCF ID 引用 | 保持原样，不脱敏（用户明确要求） |
| 表格单元格含管道符 | Demo 5 模板生成，不含此情况 |

## Acceptance Criteria

- [x] `legal_report_export.py`: 单文件 ~300 行（含完整 Markdown→Word 渲染），解析 + 构建 + 导出
- [x] 唯一公开 API：`export_legal_report(md_path, output_path) -> dict`
- [x] 正文章节不包含 MCP 工具调用示例和 ProvenanceChain JSON
- [x] 附录 A 包含全部 PCF 节点映射内容（14 项）
- [x] 附录 B 包含全部章节的溯源链（13 项）
- [x] CJK 字体正确渲染（宋体正文 + 黑体标题）— 样式级别预设
- [x] 表格正确转换（Table Grid 样式 + 预分配行）
- [x] `pyproject.toml` 添加 `[report]` optional-deps
- [x] 通过 `ruff check` lint
- [x] 测试覆盖 17 个用例（解析分离 + 端到端 + 无技术泄露 + CJK 字体 + 附录完整性）
- [x] `from __future__ import annotations` 在文件开头

## Success Metrics

1. 以 Demo 5 金元物业报告为输入，成功输出 .docx 文件
2. 正文无技术内容泄露（MCP 调用 / ProvenanceChain / PCF 路径）
3. 附录完整（PCF 节点 + 溯源链）
4. Word 文档可在 Microsoft Word / WPS / LibreOffice 中正常打开
5. 处理时间 < 3 秒

## Dependencies & Risks

| 风险 | 影响 | 缓释 |
|------|------|------|
| python-docx CJK 字体需 XML 操作 | 代码复杂度增加 | 样式级别预设，仅 3 行 XML 代码 |
| TOC 域需用户手动更新 | UX 略差 | 占位文本"右键单击此处更新目录" |
| Demo 5 格式变更 | 解析正则失效 | 正则模式预编译 + 测试覆盖 |
| `_element.rPr.rFonts` 属性 API 变更 | 跨版本兼容 | 锁定 `python-docx>=1.1.0` |

## Implementation Plan

### Phase 1: 核心实现（`legal_report_export.py`）
1. 安装 `python-docx` 依赖，更新 `pyproject.toml`
2. 实现 `_split_sections()` — 代码块预处理 + 正则分割 + body/appendix 分类
3. 实现 `_build_docx()` — 样式预设 + 页面设置 + 正文渲染 + 附录渲染
4. 实现 `_add_markdown()` — 基础 Markdown→Word（H2/H3/粗体/表格/代码块/列表）
5. 实现 `export_legal_report()` — 组装公开 API

### Phase 2: 测试
1. `test_split_sections_demo5()` — 验证 13 章分离正确性
2. `test_no_technical_leakage()` — 验证正文无 MCP/ProvenanceChain
3. `test_appendix_completeness()` — 验证附录包含全部技术内容
4. `test_export_end_to_end()` — 生成 .docx 并用 python-docx 重新读取验证
5. `test_cjk_font_styles()` — 验证样式级别字体设置

### Phase 3: 集成验证
1. 人工打开 .docx 检查格式
2. 运行 `ruff check` + `pytest`

## Sources & References

### Internal References
- 现有导出工具: `src/oprocess/tools/export.py:98` (`build_responsibility_doc`)
- 溯源链实现: `src/oprocess/governance/provenance.py` (ProvenanceNode/Chain)
- Demo 5 报告: `docs/demos/demo-05-jinyuan-legal-dd-report.md` (1200 行)
- 项目约束: `CLAUDE.md` (单文件 ≤300 行，单函数 ≤50 行)

### External References
- python-docx 官方文档: https://python-docx.readthedocs.io/
- python-docx GitHub (CJK issue #346): https://github.com/python-openxml/python-docx/issues/346
- python-docx TOC (issue #36): https://github.com/python-openxml/python-docx/issues/36
- GB/T 9704-2012 中文公文格式标准: A4 + 上下 2.54cm + 左右 3.17cm + 1.5 倍行距

### Research Outputs
- python-docx CJK 最佳实践（7 个陷阱 + 完整代码示例）
- Markdown 正则解析模式（8 种元素 + 防御性预处理策略）
- 架构合规审查（8/10，文件约束 + SOLID 符合）
- 简化审查（从 450 行减至 200 行，-55%）
- 性能预估（~1.7s，表格生成是主瓶颈）
