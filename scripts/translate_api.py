"""High-quality Chinese translation using Google Gemini API.

Standalone script (not part of the regular pipeline).
Run manually before pipeline:
  GOOGLE_API_KEY=... python scripts/translate_api.py

Translates:
- framework.json: name.zh + description.zh for all nodes
- kpis.json: name.zh for all KPIs
- Caches results in .dev/translation-cache.json for incremental runs
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import read_json, write_json

FRAMEWORK_PATH = Path("docs/oprocess-framework/framework.json")
KPIS_PATH = Path("docs/oprocess-framework/kpis.json")
CACHE_PATH = Path(".dev/translation-cache.json")

BATCH_SIZE = 80  # large batches to minimize API calls
MODEL = "gemini-2.5-pro"
RATE_LIMIT_DELAY = 12  # seconds between requests (conservative for Pro tier)

SYSTEM_INSTRUCTION = """你是企业流程管理领域的专业翻译。将英文流程名称和描述翻译为简洁准确的中文。

核心术语表（必须严格遵循）:
- supply chain = 供应链, customer service = 客户服务
- human capital = 人力资本, information technology = 信息技术
- financial resources = 财务资源, business capabilities = 业务能力
- enterprise risk = 企业风险, compliance = 合规, resiliency = 弹性
- products and services = 产品和服务, vision and strategy = 愿景与战略
- knowledge management = 知识管理, project management = 项目管理
- machine learning = 机器学习, artificial intelligence = 人工智能
- deep learning = 深度学习, natural language = 自然语言
- governance = 治理, ethics = 伦理, transparency = 透明度
- infrastructure = 基础设施, automation = 自动化, deployment = 部署
- incident = 事件, problem = 问题, change = 变更, release = 发布
- service desk = 服务台, configuration management = 配置管理

规则:
1. 名称翻译要简短精炼，以动词或名词开头
2. 描述翻译要通顺自然，保持专业性
3. IT/AI 缩写保留英文: IT, AI, ML, API, SLA, KPI, ITIL, SCOR, RPA, LLM
4. 只返回 JSON 数组，格式与输入一致，key 不变，en 替换为 zh"""


def _collect_items(framework: dict, kpis: list[dict]) -> list[tuple[str, str]]:
    """Collect all (key, english_text) pairs needing translation."""
    items: list[tuple[str, str]] = []

    def _walk(node: dict) -> None:
        nid = node["id"]
        if node["name"]["en"]:
            items.append((f"{nid}:name", node["name"]["en"]))
        if node["description"]["en"]:
            items.append((f"{nid}:desc", node["description"]["en"]))
        for child in node.get("children", []):
            _walk(child)

    for cat in framework.get("categories", []):
        _walk(cat)

    for kpi in kpis:
        if kpi["name"]["en"]:
            items.append((f"kpi:{kpi['id']}:name", kpi["name"]["en"]))

    return items


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return read_json(CACHE_PATH)
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(cache, CACHE_PATH)


def _translate_batch(
    model: object, batch: list[tuple[str, str]]
) -> dict[str, str]:
    """Translate a batch via Gemini API. Returns key->zh mapping."""
    request_items = [{"key": k, "en": t} for k, t in batch]
    user_msg = json.dumps(request_items, ensure_ascii=False)

    response = model.generate_content(user_msg)  # type: ignore[union-attr]
    result_text = response.text

    # Strip markdown code fences if present
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        result_text = "\n".join(lines)

    results = json.loads(result_text)
    return {item["key"]: item["zh"] for item in results}


def _apply_to_framework(framework: dict, cache: dict[str, str]) -> int:
    """Apply cached translations to framework nodes. Returns count."""
    count = 0

    def _walk(node: dict) -> None:
        nonlocal count
        nid = node["id"]
        name_key = f"{nid}:name"
        desc_key = f"{nid}:desc"
        if name_key in cache:
            node["name"]["zh"] = cache[name_key]
            count += 1
        if desc_key in cache:
            node["description"]["zh"] = cache[desc_key]
            count += 1
        for child in node.get("children", []):
            _walk(child)

    for cat in framework.get("categories", []):
        _walk(cat)
    return count


def _apply_to_kpis(kpis: list[dict], cache: dict[str, str]) -> int:
    """Apply cached translations to KPIs. Returns count."""
    count = 0
    for kpi in kpis:
        key = f"kpi:{kpi['id']}:name"
        if key in cache:
            kpi["name"]["zh"] = cache[key]
            count += 1
    return count


def _load_env() -> None:
    """Load .env file if it exists."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    _load_env()
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY (or GEMINI_API_KEY) not set.")
        print("Set in .env file or: export GOOGLE_API_KEY=...")
        print("  Get a free key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    print("Loading data...")
    framework = read_json(FRAMEWORK_PATH)
    kpis = read_json(KPIS_PATH)
    cache = _load_cache()

    items = _collect_items(framework, kpis)
    uncached = [(k, t) for k, t in items if k not in cache]

    print(f"  Total items: {len(items)}")
    print(f"  Cached: {len(items) - len(uncached)}")
    print(f"  To translate: {len(uncached)}")

    if not uncached:
        print("All items already translated. Applying cache...")
    else:
        total_batches = (len(uncached) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} items)...",
                  end="", flush=True)
            try:
                translations = _translate_batch(model, batch)
                cache.update(translations)
                _save_cache(cache)
                print(f" OK ({len(translations)} translated)")
            except Exception as e:
                print(f"\n    ERROR: {e}")
                print(f"    Saved {len(cache)} cached translations so far.")
                print("    Re-run to continue from where you left off.")
                break
            if batch_num < total_batches:
                time.sleep(RATE_LIMIT_DELAY)

    # Apply all cached translations
    fw_count = _apply_to_framework(framework, cache)
    kpi_count = _apply_to_kpis(kpis, cache)

    write_json(framework, FRAMEWORK_PATH)
    write_json(kpis, KPIS_PATH)

    print(f"\nDone:")
    print(f"  Framework fields updated: {fw_count}")
    print(f"  KPI names updated: {kpi_count}")
    print(f"  Cache size: {len(cache)}")


if __name__ == "__main__":
    main()
