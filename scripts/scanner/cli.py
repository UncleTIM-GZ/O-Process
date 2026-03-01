"""AI Impact Scanner — CLI entry point.

Usage:
    uv run python scripts/scanner/cli.py --dry-run
    uv run python scripts/scanner/cli.py --node-id 1.0 --models gemini
    uv run python scripts/scanner/cli.py --limit 10 --models gemini
    uv run python scripts/scanner/cli.py --status
    uv run python scripts/scanner/cli.py --resume
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add src/ to path so we can import oprocess
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from oprocess.db.connection import get_connection  # noqa: E402
from scripts.scanner.processor import scan_batch  # noqa: E402
from scripts.scanner.schema import init_scan_schema  # noqa: E402

logger = logging.getLogger("scanner")


def main() -> None:
    """Parse CLI args and dispatch to appropriate function."""
    parser = argparse.ArgumentParser(
        description="AI Impact Scanner — batch LLM analysis of process nodes",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Read-only statistics, no API calls")
    parser.add_argument("--status", action="store_true",
                        help="Show current scan statistics")
    parser.add_argument("--resume", action="store_true",
                        help="Show last batch summary and resume")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max nodes to process")
    parser.add_argument("--node-id", type=str, default=None,
                        help="Scan a single node by ID")
    parser.add_argument("--models", type=str, default="all",
                        help="Models: all/gemini/deepseek (comma-separated)")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Nodes per batch checkpoint")
    parser.add_argument("--db", type=str, default=None,
                        help="Database path (default: data/oprocess.db)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    db_path = Path(args.db) if args.db else None
    conn = get_connection(db_path)
    init_scan_schema(conn)

    if args.dry_run:
        run_dry_run(conn)
    elif args.status:
        show_status(conn)
    elif args.resume:
        show_resume(conn)
    else:
        run_scan(conn, args)

    conn.close()


def run_dry_run(conn) -> None:
    """Show node statistics without calling any API."""
    total = conn.execute("SELECT COUNT(*) FROM processes").fetchone()[0]

    completed = 0
    try:
        completed = conn.execute(
            "SELECT COUNT(DISTINCT node_id) FROM ai_impact_scan_results "
            "WHERE processing_status = 'completed'",
        ).fetchone()[0]
    except Exception:
        pass

    pending = total - completed

    # Framework distribution
    rows = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM processes GROUP BY source "
        "ORDER BY cnt DESC",
    ).fetchall()

    print(f"\n{'='*50}")
    print("AI Impact Scanner — Dry Run")
    print(f"{'='*50}")
    print(f"  Total nodes:     {total}")
    print(f"  Completed:       {completed}")
    print(f"  Pending:         {pending}")
    print("\n  Framework distribution:")

    fw_counts: dict[str, int] = {}
    for row in rows:
        source = json.loads(row["source"]) if row["source"] else []
        fw = _framework_label(source)
        fw_counts[fw] = fw_counts.get(fw, 0) + row["cnt"]

    for fw, cnt in sorted(fw_counts.items(), key=lambda x: -x[1]):
        print(f"    {fw:15s} {cnt:5d}")
    print()


def show_status(conn) -> None:
    """Show scan result statistics."""
    print(f"\n{'='*50}")
    print("AI Impact Scanner — Status")
    print(f"{'='*50}")

    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM ai_impact_scan_results",
        ).fetchone()[0]
    except Exception:
        print("  No scan results yet.")
        return

    completed = conn.execute(
        "SELECT COUNT(*) FROM ai_impact_scan_results "
        "WHERE processing_status = 'completed'",
    ).fetchone()[0]

    # Change status distribution
    rows = conn.execute(
        "SELECT change_status, COUNT(*) as cnt "
        "FROM ai_impact_scan_results "
        "WHERE processing_status = 'completed' "
        "GROUP BY change_status",
    ).fetchall()

    print(f"  Total results:   {total}")
    print(f"  Completed:       {completed}")
    print("\n  Change status:")
    for r in rows:
        print(f"    {r['change_status'] or 'N/A':10s} {r['cnt']:5d}")

    # Confidence distribution
    rows = conn.execute(
        "SELECT uncertainty_confidence, COUNT(*) as cnt "
        "FROM ai_impact_scan_results "
        "WHERE processing_status = 'completed' "
        "GROUP BY uncertainty_confidence",
    ).fetchall()

    print("\n  Confidence:")
    for r in rows:
        print(f"    {r['uncertainty_confidence'] or 'N/A':10s} {r['cnt']:5d}")

    # Divergent nodes
    rows = conn.execute(
        "SELECT node_id FROM ai_impact_scan_results "
        "WHERE model_agreement_status = 'divergent'",
    ).fetchall()
    if rows:
        ids = [r["node_id"] for r in rows]
        print(f"\n  Divergent nodes ({len(ids)}): {', '.join(ids[:20])}")
        if len(ids) > 20:
            print(f"    ... and {len(ids) - 20} more")

    print()


def show_resume(conn) -> None:
    """Show last batch summary."""
    try:
        row = conn.execute(
            "SELECT * FROM ai_scan_batch_summary "
            "ORDER BY id DESC LIMIT 1",
        ).fetchone()
    except Exception:
        print("  No batch history found.")
        return

    if not row:
        print("  No batch history found.")
        return

    d = dict(row)
    print(f"\n{'='*50}")
    print("Last Batch Summary")
    print(f"{'='*50}")
    print(f"  Batch ID:    {d['batch_id']}")
    print(f"  Status:      {d['batch_status']}")
    print(f"  Started:     {d['execution_start']}")
    print(f"  Completed:   {d['nodes_completed']}")
    print(f"  Failed:      {d['nodes_failed']}")
    print(f"  Skipped:     {d['nodes_skipped']}")
    print(f"  API calls:   {d['total_api_calls']}")
    print(f"  Tokens:      {d['total_tokens']}")
    print()


def run_scan(conn, args) -> None:
    """Run the scan process."""
    from scripts.scanner.processor import load_pending_nodes

    model_names = _parse_models(args.models)
    batch_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\n{'='*50}")
    print("AI Impact Scanner — Starting Scan")
    print(f"{'='*50}")
    print(f"  Batch ID:  {batch_id}")
    print(f"  Models:    {', '.join(model_names)}")
    print(f"  Limit:     {args.limit or 'all'}")

    # Create batch summary
    conn.execute(
        "INSERT INTO ai_scan_batch_summary "
        "(batch_id, execution_start, models_used, batch_status) "
        "VALUES (?, ?, ?, ?)",
        (batch_id, timestamp,
         json.dumps(model_names, ensure_ascii=False), "running"),
    )
    conn.commit()

    nodes = load_pending_nodes(conn, batch_id,
                               limit=args.limit, node_id=args.node_id)

    print(f"  Nodes to scan: {len(nodes)}")
    if not nodes:
        print("  Nothing to do!")
        _finalize_batch(conn, batch_id, {})
        return

    # Process in batches
    total_stats = {
        "completed": 0, "failed": 0, "skipped": 0,
        "api_calls": 0, "total_tokens": 0,
    }

    batch_size = args.batch_size
    for i in range(0, len(nodes), batch_size):
        chunk = nodes[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(nodes) + batch_size - 1) // batch_size
        print(f"\n  Batch {batch_num}/{total_batches} "
              f"({len(chunk)} nodes)...")

        stats = scan_batch(conn, chunk, batch_id, model_names)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

        # Progress
        print(f"  Progress: {total_stats['completed']} completed, "
              f"{total_stats['failed']} failed")

    _finalize_batch(conn, batch_id, total_stats)

    print(f"\n{'='*50}")
    print("Scan Complete")
    print(f"{'='*50}")
    print(f"  Completed: {total_stats['completed']}")
    print(f"  Failed:    {total_stats['failed']}")
    print(f"  API calls: {total_stats['api_calls']}")
    print(f"  Tokens:    {total_stats['total_tokens']}")
    print()


def _finalize_batch(conn, batch_id: str, stats: dict) -> None:
    """Update batch summary with full statistics from scan results."""
    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        agg = _aggregate_batch_stats(conn, batch_id)

        # Compute duration from start time
        start_row = conn.execute(
            "SELECT execution_start FROM ai_scan_batch_summary "
            "WHERE batch_id = ?", (batch_id,),
        ).fetchone()
        duration_min = None
        if start_row and start_row["execution_start"]:
            start_dt = datetime.fromisoformat(
                start_row["execution_start"].replace("Z", "+00:00"),
            )
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            duration_min = round((end_dt - start_dt).total_seconds() / 60, 2)

        # Estimate cost: Gemini Flash ~$0.15/1M input + $0.60/1M output
        total_tokens = stats.get("total_tokens", 0)
        estimated_cost = round(total_tokens * 0.0000004, 4)

        conn.execute(
            "UPDATE ai_scan_batch_summary SET "
            "execution_end = ?, batch_status = 'completed', "
            "total_duration_minutes = ?, "
            "nodes_total = ?, nodes_completed = ?, nodes_failed = ?, "
            "nodes_skipped = ?, "
            "total_api_calls = ?, total_tokens = ?, "
            "estimated_cost_usd = ?, "
            "full_agreement_count = ?, partial_agreement_count = ?, "
            "divergent_count = ?, divergent_node_ids = ?, "
            "high_confidence_count = ?, medium_confidence_count = ?, "
            "low_confidence_count = ?, "
            "already_changed_count = ?, will_change_count = ?, "
            "stable_count = ?, "
            "failed_node_ids = ?, parse_failure_count = ?, "
            "retry_count = ? "
            "WHERE batch_id = ?",
            (end_time, duration_min,
             agg["nodes_total"],
             stats.get("completed", 0), stats.get("failed", 0),
             agg["nodes_skipped"],
             stats.get("api_calls", 0), total_tokens,
             estimated_cost,
             agg["full_agreement"], agg["partial_agreement"],
             agg["divergent"], agg["divergent_node_ids"],
             agg["high_confidence"], agg["medium_confidence"],
             agg["low_confidence"],
             agg["already_changed"], agg["will_change"],
             agg["stable"],
             agg["failed_node_ids"], agg["parse_failure_count"],
             agg["retry_count"],
             batch_id),
        )
        conn.commit()
    except Exception as exc:
        logger.error("Failed to finalize batch: %s", exc)


def _aggregate_batch_stats(conn, batch_id: str) -> dict:
    """Aggregate statistics from scan results and audit log."""
    agg: dict = {}

    # Node counts from audit log
    agg["nodes_total"] = _count_audit(conn, batch_id, "NODE_COMPLETE") + \
        _count_audit(conn, batch_id, "NODE_FAIL")
    agg["nodes_skipped"] = _count_audit(conn, batch_id, "NODE_SKIP")

    # Agreement from scan results
    agreement_rows = conn.execute(
        "SELECT model_agreement_status, COUNT(*) as cnt "
        "FROM ai_impact_scan_results WHERE batch_id = ? "
        "GROUP BY model_agreement_status", (batch_id,),
    ).fetchall()
    agreement_map = {r["model_agreement_status"]: r["cnt"] for r in agreement_rows}
    agg["full_agreement"] = agreement_map.get("agreement", 0)
    agg["partial_agreement"] = agreement_map.get("single_model", 0)
    agg["divergent"] = agreement_map.get("divergent", 0)

    # Divergent node IDs
    div_rows = conn.execute(
        "SELECT node_id FROM ai_impact_scan_results "
        "WHERE batch_id = ? AND model_agreement_status = 'divergent'",
        (batch_id,),
    ).fetchall()
    agg["divergent_node_ids"] = json.dumps(
        [r["node_id"] for r in div_rows], ensure_ascii=False,
    ) if div_rows else None

    # Confidence distribution
    conf_rows = conn.execute(
        "SELECT uncertainty_confidence, COUNT(*) as cnt "
        "FROM ai_impact_scan_results WHERE batch_id = ? "
        "GROUP BY uncertainty_confidence", (batch_id,),
    ).fetchall()
    conf_map = {r["uncertainty_confidence"]: r["cnt"] for r in conf_rows}
    agg["high_confidence"] = conf_map.get("高", 0)
    agg["medium_confidence"] = conf_map.get("中", 0)
    agg["low_confidence"] = conf_map.get("低", 0)

    # Change status distribution
    cs_rows = conn.execute(
        "SELECT change_status, COUNT(*) as cnt "
        "FROM ai_impact_scan_results WHERE batch_id = ? "
        "GROUP BY change_status", (batch_id,),
    ).fetchall()
    cs_map = {r["change_status"]: r["cnt"] for r in cs_rows}
    agg["already_changed"] = cs_map.get("已变", 0)
    agg["will_change"] = cs_map.get("将变", 0)
    agg["stable"] = cs_map.get("稳定", 0)

    # Failed node IDs from audit log
    fail_rows = conn.execute(
        "SELECT DISTINCT node_id FROM ai_scan_audit_log "
        "WHERE batch_id = ? AND event_type = 'NODE_FAIL' AND node_id IS NOT NULL",
        (batch_id,),
    ).fetchall()
    agg["failed_node_ids"] = json.dumps(
        [r["node_id"] for r in fail_rows], ensure_ascii=False,
    ) if fail_rows else None

    # Parse failure count from audit log
    agg["parse_failure_count"] = conn.execute(
        "SELECT COUNT(*) FROM ai_scan_audit_log "
        "WHERE batch_id = ? AND event_type = 'MODEL_CALL' AND status = 'parse_fail'",
        (batch_id,),
    ).fetchone()[0]

    # Retry count
    agg["retry_count"] = conn.execute(
        "SELECT COUNT(*) FROM ai_scan_audit_log "
        "WHERE batch_id = ? AND event_type = 'MODEL_CALL' AND status = 'api_error'",
        (batch_id,),
    ).fetchone()[0]

    return agg


def _count_audit(conn, batch_id: str, event_type: str) -> int:
    """Count audit log entries by event type."""
    return conn.execute(
        "SELECT COUNT(*) FROM ai_scan_audit_log "
        "WHERE batch_id = ? AND event_type = ?",
        (batch_id, event_type),
    ).fetchone()[0]


def _parse_models(models_str: str) -> list[str]:
    """Parse model names from CLI argument."""
    if models_str.lower() == "all":
        return ["gemini", "deepseek"]
    return [m.strip().lower() for m in models_str.split(",") if m.strip()]


def _framework_label(source: list) -> str:
    """Human-readable framework label from source JSON."""
    if not source:
        return "APQC"
    first = source[0] if isinstance(source[0], str) else str(source[0])
    for fw in ("ITIL", "SCOR", "AI-era"):
        if fw.lower() in first.lower():
            return fw
    return "APQC"


if __name__ == "__main__":
    main()
