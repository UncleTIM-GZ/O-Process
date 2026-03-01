"""AI Impact Scanner — database schema (4 tables).

Tables are created by the CLI, NOT by connection.py's SCHEMA_SQL.
This keeps scanner concerns isolated from the MCP runtime.
"""

from __future__ import annotations

import sqlite3

SCAN_SCHEMA_SQL = """
-- Scan results: 6-dimension structured output per node
CREATE TABLE IF NOT EXISTS ai_impact_scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    scan_timestamp TEXT NOT NULL,

    -- Dimension 1: AI penetration
    penetration_decision_replaceability TEXT,
    penetration_decision_basis TEXT,
    penetration_processing_acceleration TEXT,
    penetration_processing_basis TEXT,
    penetration_tacit_knowledge TEXT,
    penetration_tacit_basis TEXT,
    penetration_overall TEXT,

    -- Dimension 2: Change status
    change_status TEXT,
    change_evidence_type TEXT,
    change_evidence_source TEXT,
    change_basis_description TEXT,

    -- Dimension 3: Change nature
    change_nature_applicable INTEGER,
    change_nature_types TEXT,
    change_nature_type_a TEXT,
    change_nature_type_b TEXT,
    change_nature_type_c TEXT,
    change_nature_type_d TEXT,

    -- Dimension 4: Human-AI boundary
    boundary_current_type TEXT,
    boundary_description TEXT,
    boundary_stability TEXT,
    boundary_stability_note TEXT,

    -- Dimension 5: Uncertainty
    uncertainty_confidence TEXT,
    uncertainty_sources TEXT,
    uncertainty_special_note TEXT,

    -- Dimension 6: Signal quality
    signal_information_period TEXT,
    signal_academic TEXT,
    signal_industry_media TEXT,
    signal_corporate_disclosure TEXT,
    signal_consulting_reports TEXT,
    signal_regulatory TEXT,
    signal_potential_bias TEXT,

    -- Summary
    summary_one_line TEXT,
    summary_priority_flag TEXT,
    summary_priority_reason TEXT,

    -- Multi-model agreement
    model_agreement_status TEXT,
    model_agreement_change_status INTEGER,
    model_agreement_penetration INTEGER,
    models_used TEXT,

    -- Processing status
    processing_status TEXT DEFAULT 'pending',
    divergence_detail TEXT,

    FOREIGN KEY (node_id) REFERENCES processes(id)
);

CREATE INDEX IF NOT EXISTS idx_scan_results_node
    ON ai_impact_scan_results(node_id);
CREATE INDEX IF NOT EXISTS idx_scan_results_batch
    ON ai_impact_scan_results(batch_id);

-- Raw LLM responses for audit trail
CREATE TABLE IF NOT EXISTS ai_scan_raw_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    scan_timestamp TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    raw_response TEXT,
    parsed_success INTEGER DEFAULT 0,
    parse_error TEXT,
    response_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_raw_responses_batch
    ON ai_scan_raw_responses(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_responses_node
    ON ai_scan_raw_responses(node_id);

-- Execution audit log
CREATE TABLE IF NOT EXISTS ai_scan_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    node_id TEXT,
    model_id TEXT,
    duration_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    status TEXT,
    detail TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_audit_batch
    ON ai_scan_audit_log(batch_id);

-- Batch execution summary
CREATE TABLE IF NOT EXISTS ai_scan_batch_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    execution_start TEXT,
    execution_end TEXT,
    total_duration_minutes REAL,
    nodes_total INTEGER DEFAULT 0,
    nodes_completed INTEGER DEFAULT 0,
    nodes_failed INTEGER DEFAULT 0,
    nodes_skipped INTEGER DEFAULT 0,
    models_used TEXT,
    total_api_calls INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL DEFAULT 0,
    full_agreement_count INTEGER DEFAULT 0,
    partial_agreement_count INTEGER DEFAULT 0,
    divergent_count INTEGER DEFAULT 0,
    divergent_node_ids TEXT,
    high_confidence_count INTEGER DEFAULT 0,
    medium_confidence_count INTEGER DEFAULT 0,
    low_confidence_count INTEGER DEFAULT 0,
    already_changed_count INTEGER DEFAULT 0,
    will_change_count INTEGER DEFAULT 0,
    stable_count INTEGER DEFAULT 0,
    failed_node_ids TEXT,
    parse_failure_count INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    batch_status TEXT DEFAULT 'running'
);
"""


def init_scan_schema(conn: sqlite3.Connection) -> None:
    """Create scanner tables if they don't exist."""
    conn.executescript(SCAN_SCHEMA_SQL)
    _migrate_raw_responses_prompts(conn)


def _migrate_raw_responses_prompts(conn: sqlite3.Connection) -> None:
    """Add prompt/config columns to ai_scan_raw_responses (idempotent).

    Also backfills system_prompt for existing records since the
    SYSTEM_PROMPT constant has not changed.
    """
    existing = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(ai_scan_raw_responses)"
        ).fetchall()
    }

    new_cols = {
        "system_prompt": "TEXT",
        "user_prompt": "TEXT",
        "model_config": "TEXT",
    }

    for col, col_type in new_cols.items():
        if col not in existing:
            conn.execute(
                f"ALTER TABLE ai_scan_raw_responses ADD COLUMN {col} {col_type}"
            )

    # Backfill system_prompt for pre-migration records (constant unchanged)
    from scripts.scanner.models import SYSTEM_PROMPT

    conn.execute(
        "UPDATE ai_scan_raw_responses SET system_prompt = ? "
        "WHERE system_prompt IS NULL",
        (SYSTEM_PROMPT,),
    )
    conn.commit()
