# Changelog

All notable changes to the O'Process MCP Server.

## [0.3.0] — 2026-02-25

### MCP Spec Compliance (P4–P7)

Full compliance with MCP Specification 2025-11-25.

- **MUST**: 11/11 requirements met
- **SHOULD**: 12/12 requirements met
- **MAY**: 1/6 implemented (server icon)

#### P4: Baseline Compliance

- feat(compliance): P0 + P1 MCP spec compliance fixes (`b71497b`)
- feat(compliance): P2 performance + quality improvements (`07d12be`)

#### P5: Robustness

- fix(compliance): MCP error types + input validation + exception handling (`23292d1`)
- fix(compliance): docstrings + rate limit config + health check vec status (`7d2c44a`)
- fix(compliance): todo cleanup + plan files archive (`323d9b1`)

#### P6: Correctness

- fix(compliance): P0 correctness fixes (version + gateway + README) (`a499cfa`)
- fix(compliance): SHOULD compliance + test coverage (`cea0143`)
- fix(compliance): MCP Prompts + logging capability (`1667d06`)

#### P7: Polish

- fix(compliance): SHOULD compliance (tool/prompt title fields) (`ea3740a`)
- fix(compliance): P2/P3 polish (dead code + docs + perf + config) (`51e954a`)
- feat(server): add SVG server icon — MCP MAY Y3 (`a4c776f`)

### MCP Certification (P0–P3)

- feat(certification): P0 — input validation, ToolError, README (`b2db1af`)
- feat(certification): P1 — multi-transport, LIKE search, singleton, ping (`cda7477`)
- feat(certification): P2 — logging, idempotency, auth (`799e765`)
- fix(security): constant-time token comparison + DRY auth logic (`61c698b`)
- feat(certification): P3.1 — SessionAuditLog activation + DRY refactor (`41cf7b3`)
- feat(certification): P3.2 — resource annotations, descriptions & mimeType (`38dc17e`)
- feat(certification): P3.3 — rate limiting middleware + LIKE escape (`9b54ab5`)
- feat(certification): P3.4 — README enhancements + registry test coverage (`568a694`)

## [0.2.0] — 2026-02-23

### PRD v2.0 Alignment (Phase 1–6)

- feat(search): Phase 1 — integrate vector search engine + real boundary scores (`bf212ec`)
- fix(provenance): Phase 2 — rewrite ProvenanceChain to PRD-compliant ProvenanceNode (`ec631aa`)
- fix(audit): Phase 3 — align SessionAuditLog schema to PRD v2.0 §5.3 (`de5eb7a`)
- feat(resources): Phase 4 — implement 5 PRD resources + role_mappings table (`8966a43`)
- feat(tools): Phase 5 — align tool signatures to PRD v2.0 §4.1 (`14095cf`)
- feat(quality): Phase 6 — quality gates & performance benchmarks (`0daebdf`)
- refactor: split server.py + integrate audit/boundary/config (`f6b724b`)

## [0.1.0] — 2026-02-22

### Initial Release (Spec 02–07)

- feat(data): Spec 02 — SQLite ingestion + TF-IDF embeddings (`519a8fe`)
- feat(server): Spec 03 — MCP Server skeleton with 7 tools (`253f60e`)
- feat(tools): Spec 04 — core query tools + vector search + 20 tests (`c14e4f6`)
- feat(tools): Spec 05 — KPI and role tools tests (9 tests) (`c9ef9b5`)
- feat(governance): Spec 06 — Governance-Lite (audit + boundary + provenance) (`e4e5791`)
- feat(release): Spec 07 — integration tests + lint + packaging (`a7ff322`)

### O'Process Framework Construction

- feat(framework): Phase 0+1 — schema, shared utils, PCF baseline (1921 nodes) (`984c431`)
- feat(framework): Phase 1b+2 — KPIs, ITIL, SCOR, AI-era enrichment (2325 nodes) (`607a6c3`)
- feat(framework): Phase 3+4 — translation, export, validation pipeline (`3fbe5da`)
- feat(translation): high-quality Chinese translation via Gemini 2.5 Pro (`b4ee7d5`)
- fix(review): address P1/P2 code review findings (`4ea9001`)
