"""Merge ITIL 4 practices into O'Process framework.

ITIL 4 has 34 practices in 3 categories:
- General Management Practices (14)
- Service Management Practices (17)
- Technical Management Practices (3)

Primary target: Category 8 (IT Management).
Secondary: Categories 1, 5, 6, 7, 11, 12, 13.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import (
    IdRegistry,
    load_framework,
    rebuild_registry,
    recount_nodes,
    write_json,
)
from shared.types import LocalizedText, ProcessNode

FRAMEWORK_PATH = Path("docs/oprocess-framework/framework.json")

# ── ITIL 4 Practice Data ──────────────────────────────────────────────
# Each practice: (name, target_category_id, activities[])
# target_category_id = existing PCF process group to enrich

ITIL_PRACTICES: list[dict] = [
    # === General Management Practices (→ various categories) ===
    {"name": "Strategy Management", "target": "1.0",
     "activities": ["Define IT strategy alignment", "Assess strategic options",
                    "Execute strategic initiatives"]},
    {"name": "Portfolio Management", "target": "8.2",
     "activities": ["Evaluate portfolio investments", "Prioritize portfolio items",
                    "Balance portfolio risk and value"]},
    {"name": "Architecture Management", "target": "8.2",
     "activities": ["Define enterprise architecture vision",
                    "Maintain architecture repository",
                    "Govern architecture compliance"]},
    {"name": "Service Financial Management", "target": "8.2",
     "activities": ["Plan IT budgets and costs", "Account for IT services",
                    "Charge for IT services"]},
    {"name": "Workforce and Talent Management", "target": "7.0",
     "activities": ["Plan IT workforce capacity", "Develop IT talent pipeline",
                    "Manage IT skills and competencies"]},
    {"name": "Continual Improvement", "target": "13.0",
     "activities": ["Identify improvement opportunities",
                    "Define improvement initiatives", "Execute improvements",
                    "Evaluate improvement results"]},
    {"name": "Measurement and Reporting", "target": "13.6",
     "activities": ["Define KPI frameworks", "Collect and analyze metrics",
                    "Generate management reports"]},
    {"name": "Risk Management", "target": "11.1",
     "activities": ["Assess IT risks", "Treat IT risks",
                    "Monitor IT risk landscape"]},
    {"name": "Information Security Management", "target": "8.3",
     "activities": ["Define security policies", "Manage security incidents",
                    "Conduct security assessments", "Manage access controls"]},
    {"name": "Knowledge Management", "target": "13.5",
     "activities": ["Capture and share knowledge", "Maintain knowledge base",
                    "Improve knowledge practices"]},
    {"name": "Organizational Change Management", "target": "13.4",
     "activities": ["Assess change readiness", "Plan organizational changes",
                    "Manage stakeholder engagement"]},
    {"name": "Project Management", "target": "13.2",
     "activities": ["Initiate IT projects", "Plan and execute IT projects",
                    "Monitor and control IT projects"]},
    {"name": "Relationship Management", "target": "8.1",
     "activities": ["Manage business stakeholder relationships",
                    "Manage supplier relationships",
                    "Coordinate service level expectations"]},
    {"name": "Supplier Management", "target": "12.0",
     "activities": ["Evaluate and select suppliers",
                    "Manage supplier contracts",
                    "Monitor supplier performance"]},

    # === Service Management Practices (→ primarily Cat 8) ===
    {"name": "Service Design", "target": "8.5",
     "activities": ["Design service architecture", "Define service requirements",
                    "Plan service transitions"]},
    {"name": "Service Level Management", "target": "8.7",
     "activities": ["Define service level agreements",
                    "Monitor service levels", "Report on service performance",
                    "Review and improve SLAs"]},
    {"name": "Availability Management", "target": "8.7",
     "activities": ["Plan availability requirements",
                    "Monitor system availability",
                    "Optimize availability and resilience"]},
    {"name": "Capacity and Performance Management", "target": "8.7",
     "activities": ["Forecast capacity demands",
                    "Monitor performance baselines",
                    "Plan capacity optimization"]},
    {"name": "Service Continuity Management", "target": "8.3",
     "activities": ["Develop continuity plans", "Test continuity procedures",
                    "Maintain recovery capabilities"]},
    {"name": "Monitoring and Event Management", "target": "8.7",
     "activities": ["Define monitoring strategy",
                    "Detect and classify events",
                    "Correlate and respond to events",
                    "Automate event handling"]},
    {"name": "Incident Management", "target": "8.7",
     "activities": ["Detect and log incidents", "Classify and prioritize",
                    "Investigate and diagnose",
                    "Resolve and recover", "Close and review incidents"]},
    {"name": "Problem Management", "target": "8.7",
     "activities": ["Identify and log problems",
                    "Investigate root causes",
                    "Implement workarounds",
                    "Resolve known errors"]},
    {"name": "Service Request Management", "target": "8.7",
     "activities": ["Receive and categorize requests",
                    "Fulfill service requests",
                    "Track and close requests"]},
    {"name": "Change Enablement", "target": "8.6",
     "activities": ["Assess change requests", "Authorize changes",
                    "Coordinate change implementation",
                    "Review post-implementation"]},
    {"name": "Release Management", "target": "8.6",
     "activities": ["Plan releases", "Build and test release packages",
                    "Deploy releases", "Review release outcomes"]},
    {"name": "Service Validation and Testing", "target": "8.6",
     "activities": ["Plan test strategy", "Execute service tests",
                    "Validate service requirements"]},
    {"name": "Service Configuration Management", "target": "8.6",
     "activities": ["Maintain configuration items",
                    "Control configuration changes",
                    "Verify configuration accuracy"]},
    {"name": "IT Asset Management", "target": "8.0",
     "activities": ["Track IT asset lifecycle",
                    "Manage software licenses",
                    "Optimize asset utilization"]},
    {"name": "Service Catalog Management", "target": "8.1",
     "activities": ["Define service catalog structure",
                    "Maintain catalog entries",
                    "Publish catalog to stakeholders"]},
    {"name": "Service Desk", "target": "8.7",
     "activities": ["Manage user communications",
                    "Triage and route requests",
                    "Provide first-contact resolution"]},

    # === Technical Management Practices (→ Cat 8) ===
    {"name": "Deployment Management", "target": "8.6",
     "activities": ["Plan deployment approaches",
                    "Execute deployments to environments",
                    "Manage deployment automation"]},
    {"name": "Infrastructure and Platform Management", "target": "8.0",
     "activities": ["Manage cloud infrastructure",
                    "Manage on-premises platforms",
                    "Optimize infrastructure costs"]},
    {"name": "Software Development and Management", "target": "8.5",
     "activities": ["Manage development lifecycle",
                    "Implement coding standards",
                    "Manage technical debt"]},
]


def _add_itil_nodes(
    framework: dict, lookup: dict[str, dict], registry: IdRegistry,
) -> int:
    """Add ITIL practice nodes to framework. Returns count of new nodes."""
    added = 0

    for practice in ITIL_PRACTICES:
        target_id = practice["target"]
        practice_name = practice["name"]
        activities = practice["activities"]

        target_node = lookup.get(target_id)
        if target_node is None:
            print(f"  WARNING: target {target_id} not found for {practice_name}")
            continue

        # Create L3 node for the ITIL practice under target
        practice_id = registry.allocate_child_id(target_id)
        practice_node = ProcessNode(
            id=practice_id,
            level=target_node["level"] + 1,
            parent_id=target_id,
            domain=target_node["domain"],
            source=[f"ITIL:{practice_name}"],
            name=LocalizedText(en=practice_name, zh=""),
            description=LocalizedText(
                en=f"ITIL 4 practice: {practice_name}. "
                   f"Mapped to {target_node['name']['en']}.",
                zh="",
            ),
            tags=target_node.get("tags", [])[:] + ["itil"],
            ai_context=f"ITIL 4 practice for {practice_name}",
        ).to_dict()

        target_node["children"].append(practice_node)
        lookup[practice_id] = practice_node
        added += 1

        # Create L4 activity nodes under the practice
        for activity_name in activities:
            activity_id = registry.allocate_child_id(practice_id)
            activity_node = ProcessNode(
                id=activity_id,
                level=practice_node["level"] + 1,
                parent_id=practice_id,
                domain=target_node["domain"],
                source=[f"ITIL:{practice_name}"],
                name=LocalizedText(en=activity_name, zh=""),
                description=LocalizedText(
                    en=f"Activity within ITIL practice '{practice_name}'.",
                    zh="",
                ),
                tags=practice_node.get("tags", [])[:],
                ai_context=f"ITIL activity: {activity_name}",
            ).to_dict()

            practice_node["children"].append(activity_node)
            lookup[activity_id] = activity_node
            added += 1

    return added


def main() -> None:
    print("Loading framework...")
    framework, lookup = load_framework(FRAMEWORK_PATH)
    registry = rebuild_registry(lookup)
    print(f"  Existing nodes: {registry.count}")

    print("Merging ITIL 4 practices...")
    added = _add_itil_nodes(framework, lookup, registry)
    print(f"  Added {added} ITIL nodes")

    framework["total_nodes"] = recount_nodes(framework)
    print(f"  Total nodes: {framework['total_nodes']}")

    write_json(framework, FRAMEWORK_PATH)
    print(f"  Written: {FRAMEWORK_PATH}")


if __name__ == "__main__":
    main()
