---
title: "feat: Build O'Process Framework (OPF) Data Files"
type: feat
status: active
date: 2026-02-23
---

# Build O'Process Framework (OPF) Data Files

## Enhancement Summary

**Deepened on:** 2026-02-23
**Research agents used:** architecture-strategist, performance-oracle, security-sentinel, kieran-python-reviewer, code-simplicity-reviewer, data-integrity-guardian, best-practices-researcher, framework-docs-researcher

### Key Improvements
1. **P0 安全**: 必须先创建 `.gitignore`，防止 API Key 和版权文件误提交
2. **依赖优化**: 移除 `pandas`，改用 `fastjsonschema` 替代 `jsonschema`（100x 性能提升）
3. **Level 计算修正**: PCF L1 节点使用 `X.0` 格式，需特殊处理（非简单 dot-count）
4. **ID 冲突实时检测**: 引入 `IdRegistry` 在写入时即时验证，而非仅在最终阶段
5. **翻译优化**: 使用 Anthropic Batch API + 术语表，chunk_size=50，成本 ~$0.60
6. **JSON 输出**: `ensure_ascii=False` 必须启用，CJK 内容体积减少 1.84x
7. **新增**: `scripts/shared/io.py`（IO 工具）、`scripts/run_pipeline.py`（编排器）

### Verified Benchmarks (实测)
- Excel 读取 (read_only): 0.34s, 内存 9.9MB
- 树构建 (2743 nodes): 0.04s
- JSON 序列化: 0.30s, 文件 ~3.8MB
- Schema 验证 (fastjsonschema): ~5ms
- 翻译 (Batch API): ~3.6min, ~$0.60

---

## Overview

Construct O'Process's proprietary process classification framework by merging APQC PCF 7.4 (1921 entries), ITIL 4 (34 practices), and SCOR 12.0 (200+ L3 processes), plus ~135 AI-era additions. Output bilingual (zh+en) JSON files with Blueprint v1.0 five-pillar schema to `docs/oprocess-framework/`.

## Problem Statement / Motivation

O'Process MCP Server needs a structured knowledge base. No code exists yet — this is the M-1/M0 data preparation step that feeds `scripts/ingest.py` → SQLite → 7 MCP Tools.

## Proposed Solution

A Python data pipeline of 7 scripts + 1 orchestrator that:
1. Parse PCF Excel → JSON baseline (1921 entries)
2. Parse PCF Metrics → KPI file (3910 entries)
3. Merge ITIL practices as new/enriched nodes
4. Merge SCOR processes as new/enriched nodes
5. Add AI-era processes
6. Translate all content to bilingual zh+en
7. Validate against JSON Schema + quality gates

## Technical Considerations

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Level numbering | 1-based (`1.0` = level 1) | Matches Blueprint example `"level": 3` for `"id": "4.4.3"` |
| Level calculation | Special `.0` suffix handling | PCF L1 uses `X.0`(e.g. `1.0`), dot-count alone失效; `1.0` 和 `1.1` 都有 1 个 dot |
| ITIL/SCOR merge strategy | Hybrid: enrich existing + create new | PCF has nodes → add to `source`; PCF missing → new child node |
| AI process IDs | Distributed into existing categories (8.5, 11.2, 13.5) | Not a new category 14.0; follows Blueprint structure |
| `domain` field | `operating` (Cat 1-6), `management_support` (Cat 7-13) | PCF convention: 1-5 operating + 6 customer service = operating |
| KPI `direction`/`scor_attribute` | null for v1 | 3910 entries too many to manually classify now |
| `ai_context` field | Auto-generated from description (first 200 chars) | Placeholder; Tim O refines later |
| `tags` field | Auto-generated from category name + source labels | e.g. `["it_management", "pcf", "itil"]` |
| JSON format | UTF-8 no BOM, 2-space indent, sorted keys, `ensure_ascii=False` | CJK 内容减少 1.84x 体积 |
| NBSP handling | Normalize to regular space | Prevents search/matching inconsistencies |
| Smart quotes | Preserve as-is | Valid Unicode, no functional impact |
| Data modeling | `dataclasses` + 自定义 `to_dict()` | 简单可控，不引入额外依赖 |
| Schema validation | `fastjsonschema.compile()` | 100x faster than stdlib `jsonschema` |
| ID collision detection | `IdRegistry` 实时验证 | 每次注册即检查，fail-fast |

### PCF Excel Parsing Edge Cases

- **Combined sheet only** (1921 rows) — skip Introduction/About/Copyright/Categories sheets
- **WMF image warnings**: suppress with `warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')`
- **NBSP (U+00A0)**: replace with space in all text fields
- **2 KPIs with null units**: set to `"unknown"` (rows 389 and 2093 in Metrics sheet)
- **No merged cells** in Combined/Metrics sheets (verified)
- **openpyxl flags**: `read_only=True, data_only=True` mandatory (1.7x faster, 3x less memory)
- **Header-based access**: use first row as column names → dict per row, not positional index

### Level Calculation (Critical)

PCF L1 节点使用 `X.0` 格式（如 `1.0`, `2.0`, ... `13.0`），而 L2 使用 `X.Y`（如 `1.1`）。两者都有 1 个 dot，简单的 dot-counting 失效。

```python
def compute_level(hierarchy_id: str) -> int:
    """计算层级，处理 L1 的 .0 后缀。"""
    if hierarchy_id.endswith('.0') and hierarchy_id.count('.') == 1:
        return 1  # e.g., "1.0", "13.0"
    return hierarchy_id.count('.') + 1
```

实测 PCF 数据层级分布：L1=0(均为X.0), L2=85, L3=350, L4=1297, L5=189, 总计=1921。

### ID System

```
Level 1:  1.0, 2.0, ..., 13.0        (PCF categories, 注意 .0 后缀)
Level 2:  1.1, 8.5                    (process groups)
Level 3:  1.1.1, 8.5.3               (processes)
Level 4:  1.1.1.1, 8.5.3.1           (activities)
Level 5:  1.1.1.1.1, 8.5.3.1.2       (tasks)
```

New ITIL/SCOR/AI nodes get next available number under their parent via `IdRegistry.allocate_child_id()`. Parent-child: derived from ID prefix (e.g., `4.4.3` parent = `4.4`). Root nodes have `parent_id: null`.

### ID 冲突预防 — IdRegistry

```python
class IdRegistry:
    """全局 ID 注册表，每次注册即验证唯一性。"""
    def __init__(self) -> None:
        self._ids: set[str] = set()
        self._next_child: dict[str, int] = {}

    def register(self, node_id: str) -> None:
        if node_id in self._ids:
            raise ValueError(f"ID collision: {node_id}")
        self._ids.add(node_id)
        parent_id = self._get_parent_id(node_id)
        if parent_id is not None:
            seq = int(node_id.rsplit(".", 1)[-1])
            self._next_child[parent_id] = max(
                self._next_child.get(parent_id, 0), seq + 1
            )

    def allocate_child_id(self, parent_id: str) -> str:
        seq = self._next_child.get(parent_id, 1)
        new_id = f"{parent_id}.{seq}"
        while new_id in self._ids:
            seq += 1
            new_id = f"{parent_id}.{seq}"
        self._next_child[parent_id] = seq + 1
        self.register(new_id)
        return new_id
```

三阶验证：P1(PCF注册) → P2(ITIL/SCOR分配) → P4(全局最终验证)

### Tree Building Pattern

```python
def build_process_tree(flat_nodes: list[ProcessNode]) -> list[ProcessNode]:
    lookup: dict[str, ProcessNode] = {node.id: node for node in flat_nodes}
    roots: list[ProcessNode] = []
    for node in flat_nodes:
        if node.parent_id is None:
            roots.append(node)
        elif parent := lookup.get(node.parent_id):
            parent.children.append(node)
        else:
            raise ValueError(f"Orphan node {node.id}: parent {node.parent_id} not found")
    return roots
```

### JSON Output Pattern

```python
def write_json(data: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
```

### Schema Design — Recursive `$ref`

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "localized_text": {
      "type": "object",
      "properties": {
        "zh": { "type": "string", "minLength": 1 },
        "en": { "type": "string", "minLength": 1 }
      },
      "required": ["zh", "en"]
    },
    "process_node": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "pattern": "^\\d+(\\.\\d+)*$" },
        "children": {
          "type": "array",
          "items": { "$ref": "#/$defs/process_node" }
        }
        // ... all five-pillar fields
      }
    }
  }
}
```

## System-Wide Impact

- **Data files feed**: `scripts/ingest.py` → SQLite `processes` table + `kpis` table
- **framework.json** is source of truth; language exports are derived
- **schema.json** defines the contract for all downstream code

## Acceptance Criteria

### Functional Requirements

- [ ] `framework.json`: tree structure with ~2400 nodes, all five pillar fields present
- [ ] `framework-zh.json`: flat array, Chinese only (id, level, parent_id, name, description)
- [ ] `framework-en.json`: flat array, English only
- [ ] `kpis.json`: 3910+ KPI entries from PCF Metrics sheet
- [ ] `sources_mapping.json`: all 1921 PCF entries traceable by hierarchy_id
- [ ] `schema.json`: JSON Schema (Draft 2020-12) with all five pillar fields defined
- [ ] `roles.json`, `outcome_graph.json`, `interference_graph.json`, `genome_library.json`: empty placeholder structures
- [ ] `.gitignore` created with comprehensive rules

### Quality Gates

- [ ] Total framework entries >= 1921 (PCF baseline)
- [ ] No duplicate IDs in framework.json (enforced by IdRegistry)
- [ ] All `name.zh`, `name.en`, `description.zh`, `description.en` non-empty
- [ ] All nodes have: contract, genome, temporal, interference_refs, contributes_to_outcomes fields
- [ ] `temporal.evolution_log` is `[]` (empty array, ready for append)
- [ ] JSON Schema validation passes for all output files (fastjsonschema)
- [ ] Each script file <= 300 lines
- [ ] KPI entries >= 3910

### Non-Functional Requirements

- [ ] All scripts idempotent (re-run produces same output)
- [ ] UTF-8 encoding, no BOM
- [ ] 2-space JSON indentation, sorted keys, `ensure_ascii=False`
- [ ] `ensure_ascii=False` for all JSON output (CJK content)

## Implementation Phases

### Phase 0: Security Baseline (必须先行)

**P0: 创建 `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
venv/

# Environment & Secrets
.env
.env.*
*.key

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Project-specific: copyright content NEVER committed
oprocess_content.xlsx

# Build artifacts
*.db
*.sqlite
```

### Phase 1: Schema + PCF Baseline

**Files to create:**

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `scripts/shared/__init__.py` | Package init | 1 |
| `scripts/shared/types.py` | Dataclasses: ProcessNode, KPI, LocalizedText | ~120 |
| `scripts/shared/text.py` | Text normalization (NBSP, strip) | ~30 |
| `scripts/shared/io.py` | JSON read/write + IdRegistry | ~80 |
| `scripts/parse_pcf.py` | PCF Excel Combined → framework.json (English only) | ~200 |
| `scripts/parse_metrics.py` | PCF Metrics → kpis.json | ~150 |
| `docs/oprocess-framework/schema.json` | JSON Schema (Draft 2020-12, five pillars, recursive $ref) | ~200 |

**Steps:**
1. Create `.gitignore` (Phase 0)
2. Create `schema.json` with complete five-pillar node definition using recursive `$ref` + `$defs`
3. Create `scripts/shared/types.py` with dataclasses for ProcessNode, KPI, LocalizedText
   - ProcessNode: ~20 fields, 自定义 `to_dict()` 递归序列化
   - LocalizedText: `zh` + `en` fields with `to_dict()`
4. Create `scripts/shared/text.py`: `normalize_text()` (NBSP→space, strip)
5. Create `scripts/shared/io.py`:
   - `write_json()`: `ensure_ascii=False`, 2-space indent, sorted keys, trailing newline
   - `read_json()`: UTF-8 explicit encoding
   - `IdRegistry`: register + allocate_child_id + collision detection
6. Create `scripts/parse_pcf.py`:
   - `read_only=True, data_only=True` for openpyxl
   - Suppress WMF warnings with `warnings.filterwarnings`
   - Header-based dict access (not positional)
   - `compute_level()` with `.0` suffix special handling
   - Build tree via flat dict lookup + single-pass child attachment
   - Assign: `domain` (operating/management_support), `source: ["PCF:{hierarchy_id}"]`
   - Set all five-pillar fields to empty defaults
   - Set `ai_context` from description[:200]
   - Set `tags` from category keywords
   - Register all IDs in IdRegistry
   - Output `framework.json` (tree) + `sources_mapping.json`
7. Create `scripts/parse_metrics.py`:
   - Read Metrics sheet with same openpyxl flags
   - Transform to KPI structure with `kpi.{hierarchy_id}.{seq}` IDs
   - Handle 2 null-unit entries (rows 389, 2093) → set to `"unknown"`
   - Output `kpis.json`
8. Link KPI refs back into framework.json nodes

### Phase 2: ITIL + SCOR + AI Enrichment

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `scripts/merge_itil.py` | Add ITIL practice nodes to framework | ~250 |
| `scripts/merge_scor.py` | Add SCOR process nodes to framework | ~200 |
| `scripts/add_ai_processes.py` | Add AI-era process nodes | ~200 |

**Steps:**
1. `scripts/merge_itil.py`:
   - Define ITIL 34 practices as structured data (inline dict, not external file)
   - Map each practice to target PCF category/process group
   - For existing PCF nodes: append to `source` array
   - For missing nodes: use `IdRegistry.allocate_child_id()` for collision-free IDs
   - Focus on Category 8 (IT) with ~120 new nodes
   - Secondary: Categories 1, 5, 6, 7, 11, 12, 13

2. `scripts/merge_scor.py`:
   - Define SCOR L1-L3 processes as structured data
   - Map to Category 4 (Supply Chain) primarily
   - Create new Process Groups: 4.6 (Enable SC), 4.7 (AI SC)
   - Add SCOR L3 activities as L4 children
   - Secondary: Category 5 (Services)

3. `scripts/add_ai_processes.py`:
   - Create Process Group 8.5 (AI & Intelligent Ops): MLOps, LLMOps, AIOps, RPA
   - Create Process Group 11.2 (AI Governance): Ethics, Risk, Safety
   - Create Process Group 13.5 (AI Capabilities): Maturity, Skills, Decision
   - Scatter AI activities across other categories

### Phase 3: Translation + Export

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `scripts/translate.py` | Batch translate en→zh using Anthropic Batch API | ~200 |
| `scripts/export_languages.py` | Generate framework-zh.json, framework-en.json | ~100 |

**Steps:**
1. `scripts/translate.py`:
   - Load framework.json, flatten all nodes
   - Use Anthropic Message Batches API (50% cost saving vs standard)
   - `chunk_size=50` (48 API calls for ~2400 nodes)
   - Claude Haiku for cost efficiency (~$0.60 total)
   - System prompt 注入术语表 (13 Category 名称 + 50 高频动词)
   - Checkpoint/resume: 已翻译的节点写入临时文件，中断后可续
   - Output updated framework.json with bilingual content

   **术语表核心 (确保一致性):**
   ```
   Develop Vision and Strategy → 制定愿景与战略
   Manage Information Technology → 管理信息技术
   Manage Financial Resources → 管理财务资源
   Define → 定义, Manage → 管理, Develop → 开发
   Establish → 建立, Monitor → 监控, Evaluate → 评估
   ```

2. `scripts/export_languages.py`:
   - Flatten tree → array recursively
   - Strip to single language fields (id, level, parent_id, name, description)
   - Output framework-zh.json and framework-en.json

### Phase 4: Placeholders + Validation

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `scripts/create_placeholders.py` | Generate empty v2+ structure files | ~50 |
| `scripts/validate.py` | Full quality gate validation | ~200 |
| `scripts/run_pipeline.py` | Pipeline orchestrator | ~80 |

**Steps:**
1. Create placeholder files:
   - `roles.json`: `{"version": "v2", "roles": []}`
   - `outcome_graph.json`: `{"version": "v2", "nodes": [], "edges": []}`
   - `interference_graph.json`: `{"version": "v3", "nodes": [], "edges": []}`
   - `genome_library.json`: `{"version": "v2", "genes": []}`
2. Run validation (`scripts/validate.py`):
   - Total entries >= 1921
   - No duplicate IDs (final verification, 与 IdRegistry 双重保险)
   - All bilingual fields non-empty
   - Five pillar fields present on every node
   - `fastjsonschema.compile()` schema validation
   - sources_mapping.json covers all 1921 PCF entries
   - kpis.json >= 3910 entries
   - Script line counts <= 300
3. Create `scripts/run_pipeline.py`:
   - Sequential execution: parse_pcf → parse_metrics → merge_itil → merge_scor → add_ai → translate → export → placeholders → validate
   - Each step prints timing and node count
   - Exit on first failure

## Dependencies & Prerequisites

```toml
[project]
dependencies = [
    "openpyxl>=3.1.4",       # Excel parsing (read_only mode)
    "fastjsonschema>=2.20",   # Schema validation (100x faster than stdlib)
    "anthropic>=0.40",        # Claude Batch API for translation
]
```

**Removed:**
- ~~`pandas`~~ — openpyxl 直接读取 Excel 完全够用，pandas 是过度设计
- ~~`jsonschema`~~ — `fastjsonschema` 完全替代且快 100 倍

**Prerequisites:**
- PCF Excel file at `docs/K014749_APQC Process Classification Framework (PCF) - Cross-Industry - Excel Version 7.4.xlsx`
- `ANTHROPIC_API_KEY` environment variable for batch translation
- Python 3.11+

## Risk Analysis & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| API key/copyright file committed | **P0** | `.gitignore` 先于所有代码创建 |
| PCF L1 `.0` format mishandled | High | `compute_level()` 特殊处理 + 单元测试 |
| ITIL/SCOR data not structured | High | Define inline as Python dicts in merge scripts |
| ID collisions during merge | High | `IdRegistry` 实时检测 + 三阶验证 |
| Translation API failure midway | Medium | Checkpoint/resume: 每 chunk 写入临时文件 |
| Translation quality for 2400+ entries | Medium | 术语表 + human review of L1/L2 |
| framework.json too large (>10MB) | Low | 实测 ~3.8MB (2-space indent, ensure_ascii=False) |
| 300-line script limit | Low | 10 focused scripts, shared utilities extracted |

## Sources & References

### Internal References

- Plan: `/home/timou/.claude/plans/cuddly-herding-whisper.md`
- CLAUDE.md: `/home/timou/repos/O'Process/CLAUDE.md`
- Blueprint: `/home/timou/repos/O'Process/OProcess-Blueprint-v1.0.docx`
- PRD: `/home/timou/repos/O'Process/OProcess-PRD-v2.0.docx`
- PCF Excel: `/home/timou/repos/O'Process/docs/K014749_APQC Process Classification Framework (PCF) - Cross-Industry - Excel Version 7.4.xlsx`
- Rules: `/home/timou/repos/O'Process/.claude/rules.md`
- Patterns: `/home/timou/repos/O'Process/.claude/patterns.md`
- Anti-patterns: `/home/timou/repos/O'Process/.claude/anti-patterns.md`

### External References (from research agents)

- [openpyxl Optimised Modes](https://openpyxl.readthedocs.io/en/stable/optimized.html)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/schema)
- [fastjsonschema Documentation](https://horejsek.github.io/python-fastjsonschema/)
- [Anthropic Batch Processing](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)
