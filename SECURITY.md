# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| < 0.3   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in O'Process, please report it responsibly.

**Do NOT open a public issue.**

Instead, please email: **security@example.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide an initial assessment within 5 business days.

## Security Features

### Input Validation

All tool inputs are validated at the MCP boundary using Pydantic `Annotated[..., Field(...)]` constraints:

- String length limits (`min_length`, `max_length`)
- Integer ranges (`ge`, `le`)
- Regex patterns for IDs (`^\d+(\.\d+)*$`)
- Enum validation for language (`"zh" | "en"`)

### Authentication

- **Bearer token auth** for HTTP transports (SSE, streamable-http)
- Timing-safe comparison via `hmac.compare_digest`
- Disabled by default for stdio transport (no network exposure)

### Rate Limiting

- Per-client rate limiting via FastMCP Middleware
- Default: 60 calls per 60-second window
- Configurable via `pyproject.toml`

### SQL Injection Prevention

- All database queries use parameterized placeholders (`?`)
- LIKE wildcards escaped via `_escape_like()`
- Language parameter validated against a frozen whitelist

### Prompt Injection Prevention

- `_sanitize_role_name()` strips control characters and collapses whitespace
- 100-character limit enforced on user-supplied role names
- All prompt parameters validated before template rendering

### Audit Log Integrity

- Append-only table with SQLite `TRIGGER` preventing `UPDATE` and `DELETE`
- `INSERT OR IGNORE` with unique `request_id` index for idempotency
- Write failures silently caught — never block the main tool flow

### Origin Validation

- `OPROCESS_ALLOWED_ORIGINS` environment variable for CORS-style origin filtering
- Returns `403 Forbidden` for disallowed origins
- Configurable per deployment

### Transport Security

- HTTP transports bind to `127.0.0.1` by default (localhost only)
- stdio transport has no network exposure
- Bearer auth middleware applied automatically on non-stdio transports
