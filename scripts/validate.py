"""Full quality gate validation for O'Process framework output files.

Checks:
1. Total entries >= 1921 (PCF baseline)
2. No duplicate IDs
3. All bilingual fields non-empty
4. Five pillar fields present on every node
5. JSON Schema validation (fastjsonschema if available, else jsonschema)
6. sources_mapping.json covers all 1921 PCF entries
7. kpis.json >= 3910 entries (with process_id referential integrity)
8. Script line counts <= 300
9. parent_id referential integrity
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import read_json

OUTPUT_DIR = Path("docs/oprocess-framework")
SCRIPTS_DIR = Path("scripts")
MAX_SCRIPT_LINES = 300
MIN_PCF_ENTRIES = 1921
MIN_KPI_ENTRIES = 3910

REQUIRED_PILLAR_FIELDS = [
    "contract", "genome", "temporal", "interference_refs",
    "contributes_to_outcomes",
]


def _collect_all_nodes(framework: dict) -> list[dict]:
    """Flatten all nodes from tree structure."""
    nodes: list[dict] = []

    def _walk(node: dict) -> None:
        nodes.append(node)
        for child in node.get("children", []):
            _walk(child)

    for cat in framework.get("categories", []):
        _walk(cat)
    return nodes


def _check_total_entries(nodes: list[dict]) -> list[str]:
    errors = []
    if len(nodes) < MIN_PCF_ENTRIES:
        errors.append(f"FAIL: Total entries {len(nodes)} < {MIN_PCF_ENTRIES}")
    else:
        print(f"  PASS: Total entries = {len(nodes)} (>= {MIN_PCF_ENTRIES})")
    return errors


def _check_duplicate_ids(nodes: list[dict]) -> list[str]:
    errors = []
    seen: set[str] = set()
    for node in nodes:
        nid = node["id"]
        if nid in seen:
            errors.append(f"FAIL: Duplicate ID: {nid}")
        seen.add(nid)
    if not errors:
        print(f"  PASS: No duplicate IDs ({len(seen)} unique)")
    return errors


def _check_bilingual(nodes: list[dict]) -> list[str]:
    errors = []
    empty_name = 0
    empty_desc = 0
    for node in nodes:
        if not node.get("name", {}).get("zh"):
            empty_name += 1
        if not node.get("name", {}).get("en"):
            empty_name += 1
        if not node.get("description", {}).get("zh"):
            empty_desc += 1
        if not node.get("description", {}).get("en"):
            empty_desc += 1

    if empty_name > 0:
        errors.append(f"FAIL: {empty_name} empty name fields (zh or en)")
    else:
        print("  PASS: All name.zh and name.en non-empty")

    if empty_desc > 0:
        msg = (
            f"FAIL: {empty_desc} empty description fields "
            "(violates schema minLength:1)"
        )
        errors.append(msg)
    else:
        print("  PASS: All description.zh and description.en non-empty")
    return errors


def _check_pillar_fields(nodes: list[dict]) -> list[str]:
    errors = []
    missing_count = 0
    for node in nodes:
        for field in REQUIRED_PILLAR_FIELDS:
            if field not in node:
                missing_count += 1
                if missing_count <= 5:
                    errors.append(f"FAIL: Node {node['id']} missing '{field}'")
    if missing_count == 0:
        print("  PASS: All five pillar fields present on every node")
    elif missing_count > 5:
        errors.append(f"  ... and {missing_count - 5} more missing fields")
    return errors


def _check_parent_id_integrity(nodes: list[dict]) -> list[str]:
    """Verify every node's parent_id references an existing node."""
    errors = []
    all_ids = {node["id"] for node in nodes}
    orphans = 0
    for node in nodes:
        pid = node.get("parent_id")
        if pid is not None and pid not in all_ids:
            orphans += 1
            if orphans <= 5:
                errors.append(f"FAIL: Node {node['id']} parent_id '{pid}' not found")
    if orphans > 5:
        errors.append(f"  ... and {orphans - 5} more orphaned parent_id refs")
    if orphans == 0:
        print("  PASS: All parent_id references valid")
    return errors


def _check_schema_validation(framework: dict) -> list[str]:
    errors = []
    schema_path = OUTPUT_DIR / "schema.json"
    if not schema_path.exists():
        errors.append("FAIL: schema.json not found")
        return errors

    schema = read_json(schema_path)

    try:
        import fastjsonschema
        validate = fastjsonschema.compile(schema)
        validate(framework)
        print("  PASS: JSON Schema validation (fastjsonschema)")
    except ImportError:
        try:
            import jsonschema
            jsonschema.validate(framework, schema)
            print("  PASS: JSON Schema validation (jsonschema)")
        except ImportError:
            msg = (
                "WARN: No schema validator available "
                "(install fastjsonschema)"
            )
            errors.append(msg)
        except jsonschema.ValidationError as e:
            errors.append(f"FAIL: Schema validation: {e.message[:200]}")
    except fastjsonschema.JsonSchemaValueException as e:
        errors.append(f"FAIL: Schema validation: {str(e)[:200]}")

    return errors


def _check_sources_mapping() -> list[str]:
    errors = []
    path = OUTPUT_DIR / "sources_mapping.json"
    if not path.exists():
        errors.append("FAIL: sources_mapping.json not found")
        return errors
    mapping = read_json(path)
    if len(mapping) < MIN_PCF_ENTRIES:
        msg = (
            f"FAIL: sources_mapping has {len(mapping)} entries "
            f"< {MIN_PCF_ENTRIES}"
        )
        errors.append(msg)
    else:
        msg = (
            f"  PASS: sources_mapping = {len(mapping)} entries "
            f"(>= {MIN_PCF_ENTRIES})"
        )
        print(msg)
    return errors


def _check_kpis(all_node_ids: set[str]) -> list[str]:
    errors = []
    path = OUTPUT_DIR / "kpis.json"
    if not path.exists():
        errors.append("FAIL: kpis.json not found")
        return errors
    kpis = read_json(path)
    if len(kpis) < MIN_KPI_ENTRIES:
        errors.append(f"FAIL: kpis.json has {len(kpis)} entries < {MIN_KPI_ENTRIES}")
    else:
        print(f"  PASS: kpis.json = {len(kpis)} entries (>= {MIN_KPI_ENTRIES})")
    # Check process_id referential integrity
    orphan_kpis = 0
    for kpi in kpis:
        pid = kpi.get("process_id", "")
        if pid and pid not in all_node_ids:
            orphan_kpis += 1
            if orphan_kpis <= 3:
                msg = (
                    f"FAIL: KPI {kpi['id']} process_id '{pid}' "
                    "not in framework"
                )
                errors.append(msg)
    if orphan_kpis > 3:
        errors.append(f"  ... and {orphan_kpis - 3} more orphaned KPI process_ids")
    if orphan_kpis == 0:
        print(f"  PASS: All {len(kpis)} KPI process_ids reference valid nodes")
    return errors


def _check_script_lines() -> list[str]:
    errors = []
    for py_file in sorted(SCRIPTS_DIR.glob("**/*.py")):
        if py_file.name == "__init__.py":
            continue
        lines = len(py_file.read_text().splitlines())
        if lines > MAX_SCRIPT_LINES:
            errors.append(f"FAIL: {py_file} = {lines} lines (> {MAX_SCRIPT_LINES})")
        else:
            print(f"  PASS: {py_file} = {lines} lines")
    return errors


def main() -> None:
    print("=" * 60)
    print("O'Process Framework Quality Gate Validation")
    print("=" * 60)

    framework = read_json(OUTPUT_DIR / "framework.json")
    nodes = _collect_all_nodes(framework)
    all_errors: list[str] = []

    print("\n[1] Total entries")
    all_errors.extend(_check_total_entries(nodes))

    print("\n[2] Duplicate IDs")
    all_errors.extend(_check_duplicate_ids(nodes))

    print("\n[3] Bilingual completeness")
    all_errors.extend(_check_bilingual(nodes))

    print("\n[4] Five pillar fields")
    all_errors.extend(_check_pillar_fields(nodes))

    print("\n[5] Parent ID referential integrity")
    all_errors.extend(_check_parent_id_integrity(nodes))

    print("\n[6] JSON Schema validation")
    all_errors.extend(_check_schema_validation(framework))

    print("\n[7] Sources mapping")
    all_errors.extend(_check_sources_mapping())

    all_node_ids = {node["id"] for node in nodes}
    print("\n[8] KPIs (with process_id integrity)")
    all_errors.extend(_check_kpis(all_node_ids))

    print("\n[9] Script line counts")
    all_errors.extend(_check_script_lines())

    print("\n" + "=" * 60)
    fails = [e for e in all_errors if e.startswith("FAIL")]
    warns = [e for e in all_errors if e.startswith("WARN")]
    if fails:
        print(f"FAILED: {len(fails)} errors, {len(warns)} warnings")
        for e in all_errors:
            print(f"  {e}")
        sys.exit(1)
    elif warns:
        print(f"PASSED with {len(warns)} warnings")
        for w in warns:
            print(f"  {w}")
    else:
        print("ALL QUALITY GATES PASSED")


if __name__ == "__main__":
    main()
