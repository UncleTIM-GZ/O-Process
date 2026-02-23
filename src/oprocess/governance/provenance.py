"""ProvenanceChain — track derivation path for tool responses.

Each tool response carries a provenance chain showing which
process nodes were used to produce the result, with confidence
scores and derivation rules (PRD v2.0 Section 5.1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProvenanceNode:
    """A single node in a provenance chain (PRD spec)."""

    node_id: str
    name: str
    confidence: float  # 0.0-1.0
    path: str  # e.g. '1.0 > 1.1 > 1.1.2'
    derivation_rule: str  # 'semantic_match' | 'rule_based' | 'direct_lookup'

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "confidence": self.confidence,
            "path": self.path,
            "derivation_rule": self.derivation_rule,
        }


class ProvenanceChain:
    """Builds and manages a provenance chain for a tool invocation."""

    def __init__(self) -> None:
        self._nodes: list[ProvenanceNode] = []

    def add(
        self,
        node_id: str,
        name: str,
        confidence: float,
        path: str,
        derivation_rule: str,
    ) -> None:
        """Add a node to the provenance chain."""
        self._nodes.append(
            ProvenanceNode(
                node_id=node_id,
                name=name,
                confidence=confidence,
                path=path,
                derivation_rule=derivation_rule,
            )
        )

    def to_list(self) -> list[dict]:
        """Export chain as list of dicts."""
        return [n.to_dict() for n in self._nodes]

    def node_ids(self) -> list[str]:
        """Get list of node IDs in the chain."""
        return [n.node_id for n in self._nodes]

    def __len__(self) -> int:
        return len(self._nodes)
