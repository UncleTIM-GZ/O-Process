"""Shared data types for O'Process framework construction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LocalizedText:
    """Bilingual text container (zh + en)."""

    zh: str = ""
    en: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"zh": self.zh, "en": self.en}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> LocalizedText:
        return cls(zh=d.get("zh", ""), en=d.get("en", ""))


@dataclass
class ProcessNode:
    """Single node in the process classification framework."""

    id: str
    level: int
    parent_id: Optional[str]
    domain: str  # "operating" | "management_support"
    source: list[str] = field(default_factory=list)
    name: LocalizedText = field(default_factory=LocalizedText)
    description: LocalizedText = field(default_factory=LocalizedText)
    kpi_refs: list[str] = field(default_factory=list)
    contributes_to_outcomes: list[str] = field(default_factory=list)
    contract: dict[str, Any] = field(default_factory=lambda: {
        "preconditions": [],
        "invariants": [],
        "postconditions": [],
        "compensation": None,
    })
    genome: dict[str, Any] = field(default_factory=lambda: {
        "core_genes": [],
        "context_genes": [],
        "regulatory_genes": [],
        "mutations": {},
    })
    interference_refs: list[str] = field(default_factory=list)
    temporal: dict[str, Any] = field(default_factory=lambda: {
        "maturity_half_life": None,
        "automation_trajectory": None,
        "human_ai_boundary": None,
        "obsolescence_risk": None,
        "evolution_log": [],
    })
    provenance_eligible: bool = True
    ai_context: str = ""
    tags: list[str] = field(default_factory=list)
    children: list[ProcessNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Recursively serialize to dict for JSON output."""
        return {
            "id": self.id,
            "level": self.level,
            "parent_id": self.parent_id,
            "domain": self.domain,
            "source": self.source,
            "name": self.name.to_dict(),
            "description": self.description.to_dict(),
            "kpi_refs": self.kpi_refs,
            "contributes_to_outcomes": self.contributes_to_outcomes,
            "contract": self.contract,
            "genome": self.genome,
            "interference_refs": self.interference_refs,
            "temporal": self.temporal,
            "provenance_eligible": self.provenance_eligible,
            "ai_context": self.ai_context,
            "tags": self.tags,
            "children": [c.to_dict() for c in self.children],
        }

    def count_nodes(self) -> int:
        """Recursively count total nodes including self."""
        return 1 + sum(c.count_nodes() for c in self.children)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProcessNode:
        """Deserialize from dict (e.g., loaded from JSON)."""
        children_data = d.get("children", [])
        node = cls(
            id=d["id"],
            level=d["level"],
            parent_id=d.get("parent_id"),
            domain=d["domain"],
            source=d.get("source", []),
            name=LocalizedText.from_dict(d.get("name", {})),
            description=LocalizedText.from_dict(d.get("description", {})),
            kpi_refs=d.get("kpi_refs", []),
            contributes_to_outcomes=d.get("contributes_to_outcomes", []),
            contract=d.get("contract", cls.__dataclass_fields__["contract"].default_factory()),
            genome=d.get("genome", cls.__dataclass_fields__["genome"].default_factory()),
            interference_refs=d.get("interference_refs", []),
            temporal=d.get("temporal", cls.__dataclass_fields__["temporal"].default_factory()),
            provenance_eligible=d.get("provenance_eligible", True),
            ai_context=d.get("ai_context", ""),
            tags=d.get("tags", []),
            children=[cls.from_dict(c) for c in children_data],
        )
        return node


@dataclass
class KPIEntry:
    """Single KPI metric entry."""

    id: str
    process_id: str
    name: LocalizedText = field(default_factory=LocalizedText)
    unit: str = "unknown"
    formula: Optional[str] = None
    category: Optional[str] = None
    scor_attribute: Optional[str] = None
    direction: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "process_id": self.process_id,
            "name": self.name.to_dict(),
            "unit": self.unit,
            "formula": self.formula,
            "category": self.category,
            "scor_attribute": self.scor_attribute,
            "direction": self.direction,
        }
