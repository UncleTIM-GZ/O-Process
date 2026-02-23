"""ProvenanceChain — track derivation path for tool responses.

Each tool response can carry a provenance chain showing which
process nodes, KPIs, or data sources were used to produce the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ProvenanceEntry:
    """A single step in a provenance chain."""

    node_id: str
    action: str  # e.g., "queried", "matched", "derived", "aggregated"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "details": self.details,
        }


class ProvenanceChain:
    """Builds and manages a provenance chain for a tool invocation."""

    def __init__(self) -> None:
        self._entries: list[ProvenanceEntry] = []

    def add(
        self, node_id: str, action: str, details: str = ""
    ) -> None:
        """Add an entry to the provenance chain."""
        self._entries.append(
            ProvenanceEntry(node_id=node_id, action=action, details=details)
        )

    def to_list(self) -> list[dict]:
        """Export chain as list of dicts."""
        return [e.to_dict() for e in self._entries]

    def node_ids(self) -> list[str]:
        """Get list of node IDs in the chain."""
        return [e.node_id for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)
