# O'Process

AI-native process classification MCP Server. Query 2,325 processes and 3,910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0 + AI-era extensions.

## Quick Start

```bash
# Install (includes embedding + dev dependencies)
uv sync --all-extras

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

Invalid inputs raise `ToolError` with descriptive messages.

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
| `GOOGLE_API_KEY` | For embedding | Google AI Studio API key (gemini-embedding-001) |
| `OPROCESS_API_KEY` | For HTTP auth | Bearer token for SSE/HTTP transports |
| `OPROCESS_ALLOWED_ORIGINS` | No | Comma-separated allowed origins for CORS (e.g. `http://localhost:3000,https://app.example.com`) |
| `LOG_LEVEL` | No | Logging level (default: WARNING) |

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
# Install all dependencies
uv sync --all-extras

# Lint
ruff check .

# Test
pytest

# Full check (lint + test + benchmark)
ruff check . && pytest && pytest --benchmark-only
```

## Tech Stack

- **Runtime**: Python 3.10+
- **MCP Framework**: FastMCP 3.x
- **Validation**: Pydantic 2.x (`Annotated[..., Field(...)]`)
- **Database**: SQLite + sqlite-vec (vector search)
- **Embeddings**: gemini-embedding-001 (768-dim, via Google AI Studio)
- **Packaging**: uv + hatchling

## License

MIT
