"""JSON I/O utilities and ID registry for O'Process framework construction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(data: Any, output_path: Path) -> None:
    """Write data as JSON with consistent formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(input_path: Path) -> Any:
    """Read JSON file with explicit UTF-8 encoding."""
    return json.loads(input_path.read_text(encoding="utf-8"))


class IdRegistry:
    """Global ID registry preventing collisions during merge operations."""

    def __init__(self) -> None:
        self._ids: set[str] = set()
        self._next_child: dict[str, int] = {}

    def register(self, node_id: str) -> None:
        """Register an ID. Raises ValueError on collision."""
        if node_id in self._ids:
            raise ValueError(f"ID collision: {node_id}")
        self._ids.add(node_id)
        parent_id = get_parent_id(node_id)
        if parent_id is not None:
            seq = int(node_id.rsplit(".", 1)[-1])
            self._next_child[parent_id] = max(
                self._next_child.get(parent_id, 0), seq + 1
            )

    def allocate_child_id(self, parent_id: str) -> str:
        """Allocate next available child ID under parent.

        L1 parents (e.g., "1.0") produce children like "1.3" (not "1.0.3").
        Other parents (e.g., "1.1") produce children like "1.1.3".
        """
        prefix = _child_prefix(parent_id)
        seq = self._next_child.get(parent_id, 1)
        new_id = f"{prefix}.{seq}"
        while new_id in self._ids:
            seq += 1
            new_id = f"{prefix}.{seq}"
        self._next_child[parent_id] = seq + 1
        self.register(new_id)
        return new_id

    def has(self, node_id: str) -> bool:
        return node_id in self._ids

    @property
    def count(self) -> int:
        return len(self._ids)


def _child_prefix(parent_id: str) -> str:
    """Get the prefix used when generating child IDs.

    L1 parents "X.0" → prefix "X" (children are "X.1", "X.2", ...).
    Other parents → prefix is the parent_id itself.
    """
    if parent_id.endswith(".0") and parent_id.count(".") == 1:
        return parent_id[:-2]  # "1.0" → "1"
    return parent_id


def compute_level(hierarchy_id: str) -> int:
    """Compute hierarchy level from ID. Handles PCF L1 '.0' suffix."""
    if hierarchy_id.endswith(".0") and hierarchy_id.count(".") == 1:
        return 1  # e.g., "1.0", "13.0"
    return hierarchy_id.count(".") + 1


def get_parent_id(node_id: str) -> str | None:
    """Derive parent ID from a dot-separated node ID.

    L1 nodes (e.g., "1.0", "13.0") are roots → return None.
    L2 nodes (e.g., "1.1") → parent is "1.0".
    L3+ nodes (e.g., "1.1.1") → parent is "1.1".
    """
    # L1 roots
    if node_id.endswith(".0") and node_id.count(".") == 1:
        return None
    parts = node_id.rsplit(".", 1)
    if len(parts) <= 1:
        return None
    parent = parts[0]
    # L2 nodes: parent is the L1 category (e.g., "1" → "1.0")
    if parent.isdigit():
        return f"{parent}.0"
    return parent
