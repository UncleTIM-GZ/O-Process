"""Export framework into single-language flat arrays + create placeholder files.

Generates:
- framework-zh.json (flat array, Chinese only)
- framework-en.json (flat array, English only)
- roles.json, outcome_graph.json, interference_graph.json, genome_library.json
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import read_json, write_json

OUTPUT_DIR = Path("docs/oprocess-framework")
FRAMEWORK_PATH = OUTPUT_DIR / "framework.json"


def _flatten_tree(node: dict, lang: str, result: list[dict]) -> None:
    """Recursively flatten tree node into single-language entries."""
    result.append({
        "id": node["id"],
        "level": node["level"],
        "parent_id": node["parent_id"],
        "name": node["name"][lang],
        "description": node["description"][lang],
    })
    for child in node.get("children", []):
        _flatten_tree(child, lang, result)


def _export_language(framework: dict, lang: str, output_path: Path) -> int:
    """Export single-language flat array. Returns entry count."""
    entries: list[dict] = []
    for cat in framework["categories"]:
        _flatten_tree(cat, lang, entries)
    write_json(entries, output_path)
    return len(entries)


def _create_placeholders() -> list[str]:
    """Create empty placeholder files for v2+ features."""
    placeholders = {
        "roles.json": {"version": "v2", "roles": []},
        "outcome_graph.json": {"version": "v2", "nodes": [], "edges": []},
        "interference_graph.json": {"version": "v3", "nodes": [], "edges": []},
        "genome_library.json": {"version": "v2", "genes": []},
    }
    created = []
    for filename, content in placeholders.items():
        path = OUTPUT_DIR / filename
        write_json(content, path)
        created.append(filename)
    return created


def main() -> None:
    print(f"Loading framework: {FRAMEWORK_PATH}")
    framework = read_json(FRAMEWORK_PATH)

    zh_path = OUTPUT_DIR / "framework-zh.json"
    zh_count = _export_language(framework, "zh", zh_path)
    print(f"  Written: {zh_path} ({zh_count} entries)")

    en_path = OUTPUT_DIR / "framework-en.json"
    en_count = _export_language(framework, "en", en_path)
    print(f"  Written: {en_path} ({en_count} entries)")

    print("Creating placeholder files...")
    created = _create_placeholders()
    for name in created:
        print(f"  Written: {OUTPUT_DIR / name}")


if __name__ == "__main__":
    main()
