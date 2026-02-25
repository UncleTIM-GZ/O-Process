# O'Process

AI-native process classification MCP Server. Query 2,325 processes and 3,910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0 + AI-era extensions.

**Version**: 0.3.0 | **MCP Spec**: 2025-11-25 | **MUST**: 11/11 | **SHOULD**: 12/12 | **Coverage**: 94.72%

## What It Does

O'Process gives AI assistants (Claude, GPT, etc.) real-time access to enterprise process knowledge. Connect it as an MCP Server, then ask natural language questions — the AI will call the right tools automatically.

**Core capabilities:**

- **Process Search** — "采购流程有哪些?" → returns matching process nodes with hierarchy, description, and confidence score
- **Process Tree Navigation** — browse the 5-level taxonomy (L1 categories → L5 activities)
- **KPI Recommendations** — get metrics for any process node (name, unit, formula, direction)
- **Role-Process Mapping** — "HRBP manages which processes?" → ranked list with confidence scores
- **Process Comparison** — side-by-side diff of 2+ process nodes across all attributes
- **Responsibility Document** — generate complete job descriptions with provenance appendix

## Why It Matters

| Without O'Process | With O'Process |
|-------------------|----------------|
| Manually search APQC PCF Excel (1921 rows) | Natural language query, instant results |
| Guess which KPIs apply to a process | Structured KPI suggestions from 3910 metrics |
| Write job descriptions from scratch | Auto-generated with process-backed provenance |
| Cross-reference APQC + ITIL + SCOR manually | Unified 2325-node taxonomy, one query |

## Use Cases

**Management Consulting** — Process diagnostics. A manufacturing company's delivery cycle is 30% slower than competitors. Use `search_process` to locate SCOR Plan/Deliver/Make nodes, then `get_kpi_suggestions` to build a measurement framework.

**HR Digital Transformation** — Role-process mapping. CHRO needs to know what processes HR actually owns. Use `get_process_tree` on node `7.0` (Human Capital) to get the full L1→L4 hierarchy, then `map_role_to_processes` to map "HRBP" to standard processes.

**Legal Due Diligence** — Compliance audit. Cross-border M&A requires checking 12+ regulatory domains. Use `search_process` to locate relevant PCF nodes (corporate governance, tax, labor, environmental), then `compare_processes` to identify coverage gaps.

**Internal Audit** — KPI system design. Use `get_kpi_suggestions` for each process node, review coverage across efficiency/quality/cost/timeliness dimensions, identify missing metrics.

## Quick Start

```bash
# Install
uv sync

# Run MCP Server (stdio — default)
uv run python -m oprocess.server

# Run with SSE transport
uv run python -m oprocess.server --transport sse --port 8000

# Run with streamable-http transport
uv run python -m oprocess.server --transport streamable-http --port 8000
```

## Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "oprocess": {
      "command": "uv",
      "args": ["run", "python", "-m", "oprocess.server"],
      "cwd": "/path/to/O-Process"
    }
  }
}
```

## Tools

8 MCP tools with full input validation (Pydantic `Annotated[..., Field(...)]`):

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `search_process` | Semantic search for process nodes | `query` (1-500 chars), `lang` (zh/en), `limit` (1-50), `level` (1-5) |
| `get_process_tree` | Get process subtree with children | `process_id` (e.g. "1.0"), `max_depth` (1-5) |
| `get_kpi_suggestions` | Get KPIs for a process node | `process_id` |
| `compare_processes` | Compare 2+ process nodes side-by-side | `process_ids` (comma-separated, 2+) |
| `get_responsibilities` | Generate role responsibilities | `process_id`, `lang`, `output_format` (json/markdown) |
| `map_role_to_processes` | Map job role to relevant processes | `role_description` (1-500 chars), `lang`, `limit`, `industry` |
| `export_responsibility_doc` | Export full responsibility document | `process_ids` (1+), `lang`, `role_name` |
| `health_check` | Health check — server status and data counts | _(none)_ |

All tools return `ToolResponse` JSON with `result`, `provenance_chain`, `session_id`, and `response_ms`.

Invalid inputs raise `ToolError` with descriptive messages. All tools are annotated with `readOnlyHint` and `idempotentHint`.

## Prompts

3 guided prompt templates for common workflows:

| Prompt | Description | Parameters |
|--------|-------------|------------|
| `analyze_process` | Step-by-step process analysis workflow | `process_id`, `lang` |
| `generate_job_description` | Role responsibility document generation | `process_ids`, `role_name`, `lang` |
| `kpi_review` | KPI review and gap analysis workflow | `process_id`, `lang` |

## Resources

6 MCP resources for direct data access:

| URI | Description |
|-----|-------------|
| `oprocess://process/{id}` | Complete process node data |
| `oprocess://category/list` | All L1 process categories |
| `oprocess://role/{role_name}` | Process mappings for a role |
| `oprocess://audit/session/{id}` | Audit log for a session |
| `oprocess://schema/sqlite` | SQLite schema definition |
| `oprocess://stats` | Framework statistics |

## Authentication

HTTP transports (SSE, streamable-http) support Bearer token authentication:

```bash
# Set API key
export OPROCESS_API_KEY="your-secret-key"

# Client requests must include:
#   Authorization: Bearer your-secret-key
```

When `OPROCESS_API_KEY` is not set, authentication is disabled (safe for stdio mode).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | No | Enables semantic vector search (gemini-embedding-001). Without it, search falls back to SQL LIKE matching — all features still work. |
| `OPROCESS_API_KEY` | No | Bearer token for SSE/HTTP transports. Not needed for stdio mode. |
| `OPROCESS_ALLOWED_ORIGINS` | No | Comma-separated allowed origins for CORS (e.g. `http://localhost:3000,https://app.example.com`) |
| `LOG_LEVEL` | No | Logging level (default: WARNING) |

> **No API key is required to run the server.** All 8 tools work out of the box. Setting `GOOGLE_API_KEY` upgrades `search_process` and `map_role_to_processes` from text matching to semantic vector search.

## Logging

Structured logging via Python `logging` module:

```bash
# Set log level (default: WARNING)
export LOG_LEVEL=INFO   # DEBUG, INFO, WARNING, ERROR

# Logs include: tool name, session ID, response time (ms)
```

## Configuration

Server behavior can be tuned via `[tool.oprocess]` in `pyproject.toml`:

| Key | Default | Description |
|-----|---------|-------------|
| `boundary_threshold` | `0.45` | Cosine distance threshold for BoundaryResponse |
| `audit_log_enabled` | `true` | Enable/disable SessionAuditLog |
| `default_language` | `"zh"` | Default language (zh/en) |
| `rate_limit_max_calls` | `60` | Max tool calls per client per window |
| `rate_limit_window_seconds` | `60` | Rate limit window duration (seconds) |

Rate limiting is enforced per-client via `RateLimitMiddleware`. Exceeding the limit returns HTTP 429.

## Governance-Lite

Transparent governance layer (non-blocking):

- **SessionAuditLog** -- Append-only invocation log per session (idempotent via `request_id`)
- **BoundaryResponse** -- Structured fallback when semantic confidence is low (threshold: 0.45)
- **ProvenanceChain** -- Derivation trail attached to every tool response

## Data Sources

| Source | Entries |
|--------|---------|
| APQC PCF 7.4 | 1,921 processes |
| ITIL 4 | 141 nodes |
| SCOR 12.0 | 164 nodes |
| AI-era extensions | 99 nodes |
| **Total** | **2,325 processes** |
| KPI metrics | 3,910 |

Bilingual: Chinese (zh) + English (en).

## Blueprint v1.0

The framework schema reserves five structural pillars for future enhancement:

| Pillar | Status | Description |
|--------|--------|-------------|
| `contract` | Reserved | Process contract definitions |
| `genome` | Reserved | Process genome library |
| `temporal` | Reserved | Temporal patterns |
| `interference` | Reserved | Cross-process interference graph |
| `outcomes` | Reserved | Outcome dependency graph |

These fields are present in `schema.json` as required empty defaults. Content will be populated in v2.0.

## Development

```bash
# Install dependencies
uv sync

# Lint
ruff check .

# Test
pytest

# Full check (lint + test + benchmark)
ruff check . && pytest && pytest --benchmark-only
```

## Project Structure

```
src/oprocess/
├── server.py              # FastMCP entry point (stdio/SSE/HTTP)
├── gateway.py             # ToolGatewayInterface + PassthroughGateway
├── auth.py                # Bearer token auth middleware
├── config.py              # pyproject.toml config loader
├── validators.py          # Input validation + sanitization
├── prompts.py             # 3 MCP prompt templates
├── tools/
│   ├── registry.py        # 7 tool registrations
│   ├── search.py          # search_process + map_role_to_processes
│   ├── resources.py       # 6 MCP resources
│   ├── export.py          # Responsibility document builder
│   ├── helpers.py         # Provenance + comparison utilities
│   ├── serialization.py   # ToolResponse → JSON
│   └── rate_limit.py      # Per-client rate limiter
├── governance/
│   ├── audit.py           # SessionAuditLog
│   ├── boundary.py        # BoundaryResponse
│   └── provenance.py      # ProvenanceChain
└── db/
    ├── connection.py       # SQLite + sqlite-vec connection
    └── queries.py          # All SQL queries
```

## Tech Stack

- **Runtime**: Python 3.10+
- **MCP Framework**: FastMCP 2.x
- **Validation**: Pydantic 2.x (`Annotated[..., Field(...)]`)
- **Database**: SQLite + sqlite-vec (optional vector search)
- **Embeddings**: gemini-embedding-001 (768-dim, optional — falls back to LIKE search)
- **Packaging**: uv + hatchling

## License

MIT
