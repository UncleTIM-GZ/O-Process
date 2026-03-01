"""AI Impact Scanner — scan orchestration, consistency checks, DB writes.

This module coordinates: node loading, LLM dispatch, agreement
checking, result merging, and transactional database writes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from scripts.scanner.models import MODEL_DISPATCH, LLMResponse

logger = logging.getLogger("scanner")


# ---------------------------------------------------------------------------
# Node loading
# ---------------------------------------------------------------------------


def load_pending_nodes(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    limit: int | None = None,
    node_id: str | None = None,
) -> list[dict]:
    """Load process nodes that haven't been completed yet.

    Skips nodes with processing_status='completed' in scan_results.
    """
    completed: set[str] = set()
    try:
        rows = conn.execute(
            "SELECT DISTINCT node_id FROM ai_impact_scan_results "
            "WHERE processing_status = 'completed'",
        ).fetchall()
        completed = {r["node_id"] for r in rows}
    except sqlite3.OperationalError:
        pass  # Table may not exist on first run

    if node_id:
        row = conn.execute(
            "SELECT * FROM processes WHERE id = ?", (node_id,),
        ).fetchone()
        if not row:
            logger.warning("Node %s not found", node_id)
            return []
        if node_id in completed:
            _log_skip(conn, batch_id, node_id)
            return []
        return [build_node_context(conn, row)]

    sql = "SELECT * FROM processes ORDER BY id"
    all_rows = conn.execute(sql).fetchall()

    nodes = []
    for row in all_rows:
        pid = row["id"]
        if pid in completed:
            _log_skip(conn, batch_id, pid)
            continue
        nodes.append(build_node_context(conn, row))
        if limit and len(nodes) >= limit:
            break

    return nodes


def _log_skip(conn: sqlite3.Connection, batch_id: str, node_id: str) -> None:
    """Record a NODE_SKIP audit event."""
    _write_audit(conn, batch_id, "NODE_SKIP", node_id=node_id,
                 detail="already_completed")


def build_node_context(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    """Convert a processes row to a standardized node dict for prompts."""
    d = dict(row)
    source = json.loads(d.get("source", "[]"))
    framework = _extract_framework(source)
    tags = json.loads(d.get("tags", "[]"))
    path = _build_path(conn, d["id"])

    return {
        "node_id": d["id"],
        "node_name_zh": d.get("name_zh", ""),
        "node_name_en": d.get("name_en", ""),
        "source_framework": framework,
        "taxonomy_path": path,
        "node_level": f"L{d.get('level', '')}",
        "node_description": d.get("description_zh", "")
            or d.get("description_en", ""),
        "domain_tags": " | ".join(tags) if tags else "",
    }


def _extract_framework(source: list) -> str:
    """Extract framework name from source JSON list."""
    if not source:
        return "APQC"
    first = source[0] if isinstance(source[0], str) else str(source[0])
    for fw in ("ITIL", "SCOR", "AI-era", "PCF", "APQC"):
        if fw.lower() in first.lower():
            return fw
    return "APQC"


def _build_path(conn: sqlite3.Connection, process_id: str) -> str:
    """Build ancestor path string like '1.0 > 1.1 > 1.1.2'."""
    chain: list[str] = []
    current_id: str | None = process_id
    while current_id:
        row = conn.execute(
            "SELECT id, parent_id, name_zh FROM processes WHERE id = ?",
            (current_id,),
        ).fetchone()
        if not row:
            break
        chain.append(f"{row['id']} {row['name_zh']}")
        current_id = row["parent_id"]
    chain.reverse()
    return " > ".join(chain)


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------


def check_agreement(responses: list[LLMResponse]) -> dict:
    """Check agreement between model responses on key fields.

    Returns dict with status, divergent_fields, and per-model judgments.
    """
    successful = [r for r in responses if r.parsed_success and r.parsed_json]
    if len(successful) < 2:
        return {"status": "single_model", "divergent_fields": []}

    divergent: list[str] = []
    judgments: dict[str, dict] = {}

    for r in successful:
        j = r.parsed_json or {}
        d2 = j.get("dimension_2_change_status", {})
        d1 = j.get("dimension_1_ai_penetration", {})
        judgments[r.model_id] = {
            "change_status": d2.get("status", ""),
            "overall_penetration": d1.get("overall_penetration", ""),
        }

    model_ids = list(judgments.keys())
    first = judgments[model_ids[0]]
    for mid in model_ids[1:]:
        other = judgments[mid]
        if first["change_status"] != other["change_status"]:
            divergent.append("change_status")
        if first["overall_penetration"] != other["overall_penetration"]:
            divergent.append("overall_penetration")

    status = "divergent" if divergent else "agreement"
    result = {
        "status": status,
        "divergent_fields": list(set(divergent)),
    }
    if status == "divergent":
        result["judgments"] = judgments
        result["interpretation_hint"] = "中美视角差异，需人工判断"
    return result


# ---------------------------------------------------------------------------
# Result merging
# ---------------------------------------------------------------------------


def merge_results(
    responses: list[LLMResponse],
    agreement: dict,
) -> dict:
    """Merge parsed LLM outputs into a single scan_results row.

    Agreement: take consensus values.
    Divergent: keep first model's values + divergence_detail.
    """
    successful = [r for r in responses if r.parsed_success and r.parsed_json]
    if not successful:
        return {}

    primary = successful[0].parsed_json or {}
    row = _extract_result_fields(primary)

    row["models_used"] = json.dumps(
        [r.model_id for r in successful], ensure_ascii=False,
    )
    row["model_agreement_status"] = agreement["status"]
    row["model_agreement_change_status"] = int(
        "change_status" not in agreement.get("divergent_fields", []),
    )
    row["model_agreement_penetration"] = int(
        "overall_penetration" not in agreement.get("divergent_fields", []),
    )

    if agreement["status"] == "divergent":
        row["divergence_detail"] = json.dumps(
            agreement, ensure_ascii=False,
        )
    else:
        row["divergence_detail"] = None

    row["processing_status"] = "completed"
    return row


def _extract_result_fields(j: dict) -> dict:
    """Extract flat columns from parsed JSON for scan_results table."""
    d1 = j.get("dimension_1_ai_penetration", {})
    d2 = j.get("dimension_2_change_status", {})
    d3 = j.get("dimension_3_change_nature", {})
    d4 = j.get("dimension_4_boundary", {})
    d5 = j.get("dimension_5_uncertainty", {})
    d6 = j.get("dimension_6_signal_quality", {})
    dist = d6.get("source_distribution", {})
    summ = j.get("scan_summary", {})

    types_desc = d3.get("type_descriptions", {})

    return {
        # D1
        "penetration_decision_replaceability":
            (d1.get("decision_replaceability") or {}).get("rating"),
        "penetration_decision_basis":
            (d1.get("decision_replaceability") or {}).get("basis"),
        "penetration_processing_acceleration":
            (d1.get("processing_acceleration") or {}).get("rating"),
        "penetration_processing_basis":
            (d1.get("processing_acceleration") or {}).get("basis"),
        "penetration_tacit_knowledge":
            (d1.get("tacit_knowledge_dependency") or {}).get("rating"),
        "penetration_tacit_basis":
            (d1.get("tacit_knowledge_dependency") or {}).get("basis"),
        "penetration_overall": d1.get("overall_penetration"),
        # D2
        "change_status": d2.get("status"),
        "change_evidence_type": d2.get("evidence_type"),
        "change_evidence_source": d2.get("evidence_source"),
        "change_basis_description": d2.get("basis_description"),
        # D3
        "change_nature_applicable": int(d3.get("applicable", False)),
        "change_nature_types": json.dumps(
            d3.get("types_selected", []), ensure_ascii=False,
        ),
        "change_nature_type_a": types_desc.get("A"),
        "change_nature_type_b": types_desc.get("B"),
        "change_nature_type_c": types_desc.get("C"),
        "change_nature_type_d": types_desc.get("D"),
        # D4
        "boundary_current_type": d4.get("current_type"),
        "boundary_description": d4.get("boundary_description"),
        "boundary_stability": d4.get("stability"),
        "boundary_stability_note": d4.get("stability_note"),
        # D5
        "uncertainty_confidence": d5.get("overall_confidence"),
        "uncertainty_sources": json.dumps(
            d5.get("uncertainty_sources", []), ensure_ascii=False,
        ),
        "uncertainty_special_note": d5.get("special_note"),
        # D6
        "signal_information_period": d6.get("information_period"),
        "signal_academic": dist.get("academic"),
        "signal_industry_media": dist.get("industry_media"),
        "signal_corporate_disclosure": dist.get("corporate_disclosure"),
        "signal_consulting_reports": dist.get("consulting_reports"),
        "signal_regulatory": dist.get("regulatory"),
        "signal_potential_bias": d6.get("potential_bias"),
        # Summary
        "summary_one_line": summ.get("one_line_judgment"),
        "summary_priority_flag": summ.get("priority_flag"),
        "summary_priority_reason": summ.get("priority_reason"),
    }


# ---------------------------------------------------------------------------
# Database writes (transactional)
# ---------------------------------------------------------------------------


def write_node_results(
    conn: sqlite3.Connection,
    node_id: str,
    batch_id: str,
    responses: list[LLMResponse],
    merged: dict,
    timestamp: str,
) -> bool:
    """Write all results for a single node in one transaction.

    Returns True on success, False on failure (rollback).
    """
    try:
        conn.execute("BEGIN")

        # 1. Raw responses
        for r in responses:
            conn.execute(
                "INSERT INTO ai_scan_raw_responses "
                "(batch_id, node_id, model_id, scan_timestamp, "
                "prompt_tokens, completion_tokens, total_tokens, "
                "raw_response, parsed_success, parse_error, response_time_ms, "
                "system_prompt, user_prompt, model_config) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (batch_id, node_id, r.model_id, timestamp,
                 r.prompt_tokens, r.completion_tokens, r.total_tokens,
                 r.raw_response, int(r.parsed_success), r.parse_error or None,
                 r.response_time_ms,
                 r.system_prompt or None, r.user_prompt or None,
                 r.model_config or None),
            )

        # 2. Merged scan result
        if merged:
            cols = ["node_id", "batch_id", "scan_timestamp"] + list(merged.keys())
            vals = [node_id, batch_id, timestamp] + list(merged.values())
            placeholders = ", ".join("?" for _ in cols)
            col_names = ", ".join(cols)
            conn.execute(
                f"INSERT INTO ai_impact_scan_results ({col_names}) "
                f"VALUES ({placeholders})",
                vals,
            )

        # 3. Audit events (inside transaction, no auto-commit)
        for r in responses:
            status = "success" if r.parsed_success else "parse_fail"
            if r.api_error:
                status = "api_error"
            _write_audit(
                conn, batch_id, "MODEL_CALL",
                node_id=node_id, model_id=r.model_id,
                duration_ms=r.response_time_ms,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens,
                status=status,
                detail=r.parse_error or None,
                error=r.api_error or None,
                _commit=False,
            )

        _write_audit(conn, batch_id, "NODE_COMPLETE",
                     node_id=node_id, status="completed",
                     _commit=False)

        conn.execute("COMMIT")
        return True

    except Exception as exc:
        conn.execute("ROLLBACK")
        logger.error("Write failed for %s: %s", node_id, exc)
        _write_audit(conn, batch_id, "NODE_FAIL",
                     node_id=node_id, error=str(exc))
        try:
            conn.commit()
        except Exception:
            pass
        return False


def _write_audit(
    conn: sqlite3.Connection,
    batch_id: str,
    event_type: str,
    *,
    node_id: str | None = None,
    model_id: str | None = None,
    duration_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    status: str | None = None,
    detail: str | None = None,
    error: str | None = None,
    _commit: bool = True,
) -> None:
    """Write a single audit log entry (best-effort).

    Set _commit=False when called inside an explicit transaction.
    """
    try:
        conn.execute(
            "INSERT INTO ai_scan_audit_log "
            "(event_id, event_type, timestamp, batch_id, node_id, model_id, "
            "duration_ms, prompt_tokens, completion_tokens, total_tokens, "
            "status, detail, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), event_type, _utcnow(), batch_id,
             node_id, model_id, duration_ms, prompt_tokens,
             completion_tokens, total_tokens, status, detail, error),
        )
        if _commit:
            conn.commit()
    except Exception as exc:
        logger.debug("Audit write failed: %s", exc)


# ---------------------------------------------------------------------------
# Batch scanning
# ---------------------------------------------------------------------------


def scan_batch(
    conn: sqlite3.Connection,
    nodes: list[dict],
    batch_id: str,
    model_names: list[str],
) -> dict:
    """Process a batch of nodes through selected models.

    Returns batch statistics dict.
    """
    stats = {
        "completed": 0, "failed": 0, "skipped": 0,
        "api_calls": 0, "total_tokens": 0,
    }

    for i, node in enumerate(nodes, 1):
        nid = node["node_id"]
        logger.info("[%d/%d] Scanning %s ...", i, len(nodes), nid)

        timestamp = _utcnow()
        responses: list[LLMResponse] = []

        for model_name in model_names:
            caller = MODEL_DISPATCH.get(model_name)
            if not caller:
                logger.warning("Unknown model: %s", model_name)
                continue
            resp = caller(node)
            responses.append(resp)
            stats["api_calls"] += 1
            stats["total_tokens"] += resp.total_tokens

        agreement = check_agreement(responses)
        merged = merge_results(responses, agreement)

        if not merged:
            stats["failed"] += 1
            _write_audit(conn, batch_id, "NODE_FAIL",
                         node_id=nid, error="no successful parse")
            continue

        ok = write_node_results(conn, nid, batch_id, responses,
                                merged, timestamp)
        if ok:
            stats["completed"] += 1
            logger.info("  -> %s completed (%s)", nid,
                        agreement["status"])
        else:
            stats["failed"] += 1

    return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
