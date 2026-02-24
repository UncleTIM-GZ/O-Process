"""Shared row-to-dict converters for database queries."""

from __future__ import annotations

import json
import sqlite3


def row_to_process(row: sqlite3.Row) -> dict:
    """Convert a database row to a process dict."""
    d = dict(row)
    d["source"] = json.loads(d["source"])
    d["tags"] = json.loads(d["tags"])
    d["kpi_refs"] = json.loads(d["kpi_refs"])
    d["provenance_eligible"] = bool(d["provenance_eligible"])
    return d
