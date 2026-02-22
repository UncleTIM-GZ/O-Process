"""Add AI-era process nodes to O'Process framework.

New Process Groups:
- 8.8  AI and Intelligent Operations (under Cat 8 IT)
- 11.5 AI Governance and Ethics (under Cat 11 Risk)
- 13.10 AI Capabilities Development (under Cat 13 Capabilities)
Plus scattered AI activities across other categories.
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

# (group_name, target_parent, processes_with_activities)
# fmt: off
AI_PROCESS_GROUPS = [
    # === 8.8 AI and Intelligent Operations ===
    ("AI and Intelligent Operations", "8.0", [
        ("Manage MLOps Lifecycle", [
            "Define ML model requirements", "Prepare and validate training data",
            "Train and evaluate models", "Deploy models to production",
            "Monitor model performance and drift", "Retrain and update models"]),
        ("Manage LLMOps", [
            "Design prompt engineering workflows", "Manage LLM fine-tuning",
            "Implement RAG pipelines", "Monitor LLM output quality",
            "Manage LLM cost optimization"]),
        ("Manage AIOps", [
            "Implement AI-driven monitoring", "Automate incident detection",
            "Enable predictive capacity management",
            "Automate root cause analysis"]),
        ("Manage Robotic Process Automation", [
            "Identify RPA opportunities", "Design automation workflows",
            "Deploy and monitor bots", "Optimize bot performance"]),
        ("Manage Data Science Workflows", [
            "Establish data science standards", "Manage experiment tracking",
            "Govern feature stores", "Manage model registry"]),
        ("Manage AI Infrastructure", [
            "Provision GPU/TPU compute resources", "Manage ML platforms",
            "Optimize AI workload scheduling", "Manage vector databases"]),
    ]),
    # === 11.5 AI Governance and Ethics ===
    ("AI Governance and Ethics", "11.0", [
        ("Manage AI Ethics Framework", [
            "Define AI ethics principles", "Establish ethics review board",
            "Conduct AI impact assessments", "Monitor ethical compliance"]),
        ("Manage AI Regulatory Compliance", [
            "Monitor AI regulations (EU AI Act, etc.)",
            "Classify AI systems by risk level",
            "Maintain AI compliance documentation",
            "Conduct regulatory audits"]),
        ("Manage AI Safety and Alignment", [
            "Define AI safety requirements", "Implement guardrails and filters",
            "Test adversarial robustness", "Monitor alignment metrics"]),
        ("Manage AI Bias and Fairness", [
            "Assess training data bias", "Implement fairness metrics",
            "Audit model decisions for bias", "Remediate identified biases"]),
        ("Manage AI Transparency and Explainability", [
            "Implement model explainability", "Document AI decision processes",
            "Provide stakeholder AI literacy", "Publish AI transparency reports"]),
    ]),
    # === 13.10 AI Capabilities Development ===
    ("AI Capabilities Development", "13.0", [
        ("Assess AI Capability Maturity", [
            "Define AI maturity framework", "Benchmark current AI capabilities",
            "Develop AI maturity roadmap", "Track maturity progression"]),
        ("Develop AI Knowledge and Skills", [
            "Identify AI skill gaps", "Design AI training programs",
            "Certify AI practitioners", "Build AI communities of practice"]),
        ("Manage AI-Assisted Decision Making", [
            "Define decision automation criteria", "Implement decision support systems",
            "Monitor decision quality", "Balance human-AI decision authority"]),
        ("Manage AI Innovation Pipeline", [
            "Scout AI technology trends", "Evaluate AI use cases",
            "Prototype AI solutions", "Scale successful AI pilots"]),
    ]),
]

# Scattered AI activities across other categories: (name, target_parent)
AI_SCATTERED = [
    ("AI-Powered Market Analysis", "1.1"),
    ("AI-Driven Scenario Planning", "1.2"),
    ("AI-Powered Product Design", "2.1"),
    ("Generative AI for Content Creation", "2.2"),
    ("AI-Driven Customer Segmentation", "3.1"),
    ("AI-Powered Pricing Optimization", "3.3"),
    ("AI-Powered Demand Forecasting", "4.1"),
    ("AI-Enabled Quality Inspection", "4.3"),
    ("AI-Powered Service Personalization", "5.3"),
    ("Intelligent Chatbot Management", "6.1"),
    ("AI-Powered Sentiment Analysis", "6.2"),
    ("AI-Driven Talent Acquisition", "7.1"),
    ("AI-Powered Employee Experience", "7.3"),
    ("AI-Powered Fraud Detection", "9.2"),
    ("AI-Driven Financial Forecasting", "9.3"),
    ("AI-Powered Predictive Maintenance", "10.1"),
    ("AI-Enhanced Compliance Monitoring", "11.2"),
    ("AI-Powered Partner Assessment", "12.1"),
]
# fmt: on


def _add_ai_groups(lookup: dict[str, dict], registry: IdRegistry) -> int:
    added = 0
    for group_name, target_id, processes in AI_PROCESS_GROUPS:
        target = lookup.get(target_id)
        if target is None:
            continue

        # Create Process Group node
        gid = registry.allocate_child_id(target_id)
        group = ProcessNode(
            id=gid, level=target["level"] + 1, parent_id=target_id,
            domain=target["domain"], source=["oprocess:ai-era"],
            name=LocalizedText(en=group_name, zh=""),
            description=LocalizedText(en=f"AI-era process group: {group_name}.", zh=""),
            tags=target.get("tags", [])[:] + ["ai_era"],
            ai_context=f"AI-era: {group_name}",
        ).to_dict()
        target["children"].append(group)
        lookup[gid] = group
        added += 1

        for proc_name, activities in processes:
            pid = registry.allocate_child_id(gid)
            proc = ProcessNode(
                id=pid, level=group["level"] + 1, parent_id=gid,
                domain=target["domain"], source=["oprocess:ai-era"],
                name=LocalizedText(en=proc_name, zh=""),
                description=LocalizedText(en=f"AI process: {proc_name}.", zh=""),
                tags=group.get("tags", [])[:],
                ai_context=f"AI process: {proc_name}",
            ).to_dict()
            group["children"].append(proc)
            lookup[pid] = proc
            added += 1

            for act_name in activities:
                aid = registry.allocate_child_id(pid)
                act = ProcessNode(
                    id=aid, level=proc["level"] + 1, parent_id=pid,
                    domain=target["domain"], source=["oprocess:ai-era"],
                    name=LocalizedText(en=act_name, zh=""),
                    description=LocalizedText(en=f"AI activity: {act_name}.", zh=""),
                    tags=proc.get("tags", [])[:],
                    ai_context=f"AI activity: {act_name}",
                ).to_dict()
                proc["children"].append(act)
                lookup[aid] = act
                added += 1

    return added


def _add_scattered(lookup: dict[str, dict], registry: IdRegistry) -> int:
    added = 0
    for name, target_id in AI_SCATTERED:
        target = lookup.get(target_id)
        if target is None:
            print(f"  WARNING: target {target_id} not found for {name}")
            continue
        nid = registry.allocate_child_id(target_id)
        node = ProcessNode(
            id=nid, level=target["level"] + 1, parent_id=target_id,
            domain=target["domain"], source=["oprocess:ai-era"],
            name=LocalizedText(en=name, zh=""),
            description=LocalizedText(en=f"AI-era activity: {name}.", zh=""),
            tags=target.get("tags", [])[:] + ["ai_era"],
            ai_context=f"AI activity: {name}",
        ).to_dict()
        target["children"].append(node)
        lookup[nid] = node
        added += 1
    return added


def main() -> None:
    print("Loading framework...")
    framework, lookup = load_framework(FRAMEWORK_PATH)
    registry = rebuild_registry(lookup)
    print(f"  Existing nodes: {registry.count}")

    print("Adding AI-era process groups...")
    added_groups = _add_ai_groups(lookup, registry)
    print(f"  Added {added_groups} AI group nodes")

    print("Adding scattered AI activities...")
    added_scattered = _add_scattered(lookup, registry)
    print(f"  Added {added_scattered} scattered AI nodes")

    framework["total_nodes"] = recount_nodes(framework)
    print(f"  Total nodes: {framework['total_nodes']}")
    write_json(framework, FRAMEWORK_PATH)
    print(f"  Written: {FRAMEWORK_PATH}")


if __name__ == "__main__":
    main()
