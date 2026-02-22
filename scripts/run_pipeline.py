"""Pipeline orchestrator: run all framework construction scripts in order.

Usage: python scripts/run_pipeline.py [--skip-translate]
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path("scripts")

PIPELINE_STEPS = [
    ("Parse PCF baseline", "parse_pcf.py"),
    ("Parse KPI metrics", "parse_metrics.py"),
    ("Merge ITIL practices", "merge_itil.py"),
    ("Merge SCOR processes", "merge_scor.py"),
    ("Add AI-era processes", "add_ai_processes.py"),
    ("Translate to bilingual", "translate.py"),
    ("Export languages + placeholders", "export_languages.py"),
    ("Validate quality gates", "validate.py"),
]


def main() -> None:
    skip_translate = "--skip-translate" in sys.argv
    total_start = time.time()

    print("=" * 60)
    print("O'Process Framework Construction Pipeline")
    print("=" * 60)

    for i, (label, script) in enumerate(PIPELINE_STEPS, 1):
        if skip_translate and script == "translate.py":
            print(f"\n[{i}/{len(PIPELINE_STEPS)}] {label} — SKIPPED")
            continue

        print(f"\n[{i}/{len(PIPELINE_STEPS)}] {label}")
        print("-" * 40)

        step_start = time.time()
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script)],
            capture_output=False,
        )
        elapsed = time.time() - step_start

        if result.returncode != 0:
            print(f"\nFAILED at step {i}: {label} ({elapsed:.1f}s)")
            sys.exit(1)

        print(f"  Completed in {elapsed:.1f}s")

    total = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"Pipeline completed in {total:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
