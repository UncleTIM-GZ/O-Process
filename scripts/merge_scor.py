"""Merge SCOR 12.0 processes into O'Process framework.

SCOR L1: Plan, Source, Make, Deliver, Return, Enable.
Primary: Category 4 (Supply Chain). Secondary: Category 5 (Services).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import (
    IdRegistry, load_framework, rebuild_registry, recount_nodes, write_json,
)
from shared.types import LocalizedText, ProcessNode

FRAMEWORK_PATH = Path("docs/oprocess-framework/framework.json")

# (scor_id, name, target_parent, activities)
# fmt: off
SCOR_PROCESSES = [
    ("sP1", "Plan Supply Chain", "4.1", ["Identify and prioritize SC requirements", "Balance SC resources with requirements", "Establish and communicate SC plans"]),
    ("sP2", "Plan Source", "4.1", ["Identify and assess source requirements", "Balance source resources", "Establish sourcing plans"]),
    ("sP3", "Plan Make", "4.1", ["Identify production requirements", "Balance production resources", "Establish production plans"]),
    ("sP4", "Plan Deliver", "4.1", ["Identify delivery requirements", "Balance delivery resources", "Establish delivery plans"]),
    ("sP5", "Plan Return", "4.1", ["Assess return requirements", "Balance return resources", "Establish return plans"]),
    ("sS1", "Source Stocked Product", "4.2", ["Schedule product deliveries", "Receive product", "Verify product", "Transfer product"]),
    ("sS2", "Source Make-to-Order Product", "4.2", ["Schedule deliveries", "Receive product", "Verify product", "Transfer product"]),
    ("sS3", "Source Engineer-to-Order Product", "4.2", ["Identify sources of supply", "Select final supplier", "Schedule deliveries", "Receive product"]),
    ("sM1", "Make-to-Stock", "4.3", ["Schedule production", "Issue material", "Produce and test", "Package", "Stage finished product", "Release to deliver"]),
    ("sM2", "Make-to-Order", "4.3", ["Schedule production", "Issue sourced product", "Produce and test", "Package", "Release to deliver"]),
    ("sM3", "Engineer-to-Order", "4.3", ["Finalize production engineering", "Schedule production", "Issue sourced product", "Produce and test", "Release to deliver"]),
    ("sD1", "Deliver Stocked Product", "4.4", ["Process inquiry and quote", "Receive and validate order", "Reserve inventory", "Consolidate orders", "Build loads", "Route shipments", "Pick product", "Pack product", "Ship product"]),
    ("sD2", "Deliver Make-to-Order Product", "4.4", ["Process inquiry and quote", "Receive and validate order", "Reserve resources", "Consolidate orders", "Pick product", "Pack product", "Ship product"]),
    ("sD3", "Deliver Engineer-to-Order Product", "4.4", ["Obtain and respond to RFP/RFQ", "Negotiate and receive contract", "Schedule installation", "Install product"]),
    ("sD4", "Deliver Retail Product", "4.4", ["Generate stocking schedule", "Receive product at store", "Pick from backroom", "Stock shelf", "Checkout"]),
    ("sSR1", "Source Return Defective Product", "4.0", ["Identify defective condition", "Request return authorization", "Schedule shipment", "Return product"]),
    ("sSR2", "Source Return MRO Product", "4.0", ["Identify MRO condition", "Request return authorization", "Schedule shipment", "Return product"]),
    ("sSR3", "Source Return Excess Product", "4.0", ["Identify excess product", "Request return authorization", "Schedule shipment", "Return product"]),
    ("sDR1", "Deliver Return Defective Product", "4.0", ["Authorize return", "Schedule return receipt", "Receive product", "Transfer product"]),
    ("sDR2", "Deliver Return MRO Product", "4.0", ["Authorize return", "Schedule receipt", "Receive product", "Transfer product"]),
    ("sDR3", "Deliver Return Excess Product", "4.0", ["Authorize return", "Schedule receipt", "Receive product", "Transfer product"]),
    ("sE1", "Manage SC Business Rules", "4.0", ["Gather business rule info", "Interpret rules", "Document rules"]),
    ("sE2", "Manage SC Performance", "4.0", ["Initiate reporting", "Analyze reports", "Develop corrective actions"]),
    ("sE3", "Manage SC Data and Information", "4.0", ["Receive and compile data", "Maintain data integrity"]),
    ("sE4", "Manage SC Human Resources", "4.0", ["Identify skill requirements", "Identify available resources", "Match skills"]),
    ("sE5", "Manage SC Assets", "4.0", ["Schedule asset management", "Maintain assets", "Configure assets"]),
    ("sE6", "Manage SC Contracts", "4.0", ["Negotiate contracts", "Establish contracts", "Manage contracts"]),
    ("sE7", "Manage SC Network", "4.0", ["Select network model", "Evaluate alternatives", "Finalize network"]),
    ("sE8", "Manage SC Regulatory Compliance", "4.0", ["Monitor requirements", "Assess compliance", "Adapt to changes"]),
    ("sE9", "Manage SC Risk", "4.0", ["Identify SC risks", "Assess probability and impact", "Mitigate risks"]),
    ("sE10", "Manage SC Technology", "4.0", ["Define tech requirements", "Select solutions", "Implement technology"]),
    ("sE11", "Manage SC Sustainability", "4.0", ["Define objectives", "Measure performance", "Improve practices"]),
    ("sP-SVC", "Plan Service Operations", "5.1", ["Forecast service demand", "Plan resource allocation", "Balance capacity"]),
    ("sD-SVC", "Deliver Service Operations", "5.3", ["Schedule delivery", "Execute delivery", "Confirm completion"]),
]
# fmt: on


def _add_scor_nodes(
    lookup: dict[str, dict], registry: IdRegistry,
) -> int:
    added = 0
    for scor_id, name, target_id, activities in SCOR_PROCESSES:
        target = lookup.get(target_id)
        if target is None:
            print(f"  WARNING: target {target_id} not found for {name}")
            continue

        node_id = registry.allocate_child_id(target_id)
        node = ProcessNode(
            id=node_id, level=target["level"] + 1, parent_id=target_id,
            domain=target["domain"], source=[f"SCOR:{scor_id}"],
            name=LocalizedText(en=name, zh=""),
            description=LocalizedText(en=f"SCOR 12.0: {name} ({scor_id}).", zh=""),
            tags=target.get("tags", [])[:] + ["scor"],
            ai_context=f"SCOR process: {name}",
        ).to_dict()
        target["children"].append(node)
        lookup[node_id] = node
        added += 1

        for act_name in activities:
            act_id = registry.allocate_child_id(node_id)
            act = ProcessNode(
                id=act_id, level=node["level"] + 1, parent_id=node_id,
                domain=target["domain"], source=[f"SCOR:{scor_id}"],
                name=LocalizedText(en=act_name, zh=""),
                description=LocalizedText(en=f"SCOR activity in '{name}'.", zh=""),
                tags=node.get("tags", [])[:],
                ai_context=f"SCOR activity: {act_name}",
            ).to_dict()
            node["children"].append(act)
            lookup[act_id] = act
            added += 1

    return added


def main() -> None:
    print("Loading framework...")
    framework, lookup = load_framework(FRAMEWORK_PATH)
    registry = rebuild_registry(lookup)
    print(f"  Existing nodes: {registry.count}")

    print("Merging SCOR 12.0 processes...")
    added = _add_scor_nodes(lookup, registry)
    print(f"  Added {added} SCOR nodes")

    framework["total_nodes"] = recount_nodes(framework)
    print(f"  Total nodes: {framework['total_nodes']}")
    write_json(framework, FRAMEWORK_PATH)
    print(f"  Written: {FRAMEWORK_PATH}")


if __name__ == "__main__":
    main()
