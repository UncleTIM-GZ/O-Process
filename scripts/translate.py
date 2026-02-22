"""Translate framework.json from English to bilingual (en+zh).

Supports two modes:
1. Anthropic Batch API (requires ANTHROPIC_API_KEY)
2. Glossary-based local translation (fallback, always available)

Run: python scripts/translate.py [--api]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.io import read_json, write_json

FRAMEWORK_PATH = Path("docs/oprocess-framework/framework.json")

# ── Glossary: authoritative translations for key terms ────────────────

# L1 Category names (official translations)
CATEGORY_NAMES: dict[str, str] = {
    "Develop Vision and Strategy": "制定愿景与战略",
    "Develop and Manage Products and Services": "开发与管理产品和服务",
    "Market and Sell Products and Services": "营销和销售产品和服务",
    "Manage Supply Chain for Physical Products": "管理实物产品供应链",
    "Deliver Services": "交付服务",
    "Manage Customer Service": "管理客户服务",
    "Develop and Manage Human Capital": "开发和管理人力资本",
    "Manage Information Technology (IT)": "管理信息技术",
    "Manage Financial Resources": "管理财务资源",
    "Acquire, Construct, and Manage Assets": "获取、建设和管理资产",
    "Manage Enterprise Risk, Compliance, Remediation, and Resiliency":
        "管理企业风险、合规、补救和弹性",
    "Manage External Relationships": "管理外部关系",
    "Develop and Manage Business Capabilities": "开发和管理业务能力",
}

# High-frequency verb translations
VERB_MAP: dict[str, str] = {
    "Define": "定义", "Manage": "管理", "Develop": "开发", "Establish": "建立",
    "Monitor": "监控", "Evaluate": "评估", "Implement": "实施", "Analyze": "分析",
    "Plan": "规划", "Design": "设计", "Create": "创建", "Maintain": "维护",
    "Assess": "评估", "Control": "控制", "Deploy": "部署", "Execute": "执行",
    "Identify": "识别", "Report": "报告", "Track": "跟踪", "Optimize": "优化",
    "Automate": "自动化", "Configure": "配置", "Validate": "验证",
    "Review": "审查", "Schedule": "调度", "Coordinate": "协调",
    "Receive": "接收", "Process": "处理", "Resolve": "解决", "Close": "关闭",
    "Forecast": "预测", "Audit": "审计", "Govern": "治理", "Build": "构建",
    "Test": "测试", "Verify": "验证", "Transfer": "转移", "Select": "选择",
    "Prepare": "准备", "Publish": "发布", "Provide": "提供", "Capture": "采集",
    "Collect": "收集", "Balance": "平衡", "Conduct": "开展", "Prioritize": "排定优先级",
}

# Domain noun translations
NOUN_MAP: dict[str, str] = {
    "supply chain": "供应链", "customer service": "客户服务",
    "human capital": "人力资本", "information technology": "信息技术",
    "financial resources": "财务资源", "business capabilities": "业务能力",
    "enterprise risk": "企业风险", "compliance": "合规", "resiliency": "弹性",
    "external relationships": "外部关系", "assets": "资产",
    "products and services": "产品和服务", "vision and strategy": "愿景与战略",
    "service level": "服务水平", "incident": "事件", "problem": "问题",
    "change": "变更", "release": "发布", "configuration": "配置",
    "knowledge management": "知识管理", "project management": "项目管理",
    "quality": "质量", "sustainability": "可持续发展", "security": "安全",
    "performance": "绩效", "capacity": "容量", "availability": "可用性",
    "workflow": "工作流", "automation": "自动化", "infrastructure": "基础设施",
    "governance": "治理", "ethics": "伦理", "bias": "偏见", "fairness": "公平性",
    "transparency": "透明度", "explainability": "可解释性",
    "machine learning": "机器学习", "artificial intelligence": "人工智能",
    "deep learning": "深度学习", "natural language": "自然语言",
    "data science": "数据科学", "model": "模型", "training": "训练",
    "deployment": "部署", "pipeline": "流水线", "monitoring": "监控",
    "risk": "风险", "safety": "安全", "alignment": "对齐",
    "maturity": "成熟度", "innovation": "创新", "strategy": "战略",
}


# Pre-compiled noun patterns (longest first to avoid partial matches)
_NOUN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(en), re.IGNORECASE), zh)
    for en, zh in sorted(NOUN_MAP.items(), key=lambda x: -len(x[0]))
]

# Pre-compiled verb patterns (match only when not surrounded by ASCII letters)
_VERB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"(?<![a-zA-Z]){re.escape(en)}(?![a-zA-Z])"), zh)
    for en, zh in VERB_MAP.items()
]


def _glossary_translate(text: str) -> str:
    """Translate text using glossary-based approach."""
    if not text:
        return ""

    # Check exact match in category names
    if text in CATEGORY_NAMES:
        return CATEGORY_NAMES[text]

    result = text

    # Replace nouns first (longer phrases first to avoid partial matches)
    for pattern, zh in _NOUN_PATTERNS:
        result = pattern.sub(zh, result)

    # Replace leading verbs (non-CJK boundary instead of \b)
    for pattern, zh in _VERB_PATTERNS:
        result = pattern.sub(zh, result, count=1)

    return result


def _translate_node(node: dict) -> int:
    """Recursively translate a node and its children. Returns translated count."""
    count = 0
    name_en = node["name"]["en"]
    desc_en = node["description"]["en"]

    # Translate name
    if not node["name"]["zh"]:
        node["name"]["zh"] = _glossary_translate(name_en)
        count += 1

    # Translate description
    if not node["description"]["zh"]:
        node["description"]["zh"] = _glossary_translate(desc_en) if desc_en else ""
        if not node["description"]["zh"] and desc_en:
            node["description"]["zh"] = desc_en  # fallback: keep English
        count += 1

    for child in node.get("children", []):
        count += _translate_node(child)

    return count


def _translate_with_glossary(framework: dict) -> int:
    """Translate using local glossary (always available)."""
    total = 0
    for cat in framework.get("categories", []):
        total += _translate_node(cat)
    return total


def main() -> None:
    print(f"Loading framework: {FRAMEWORK_PATH}")
    framework = read_json(FRAMEWORK_PATH)
    node_count = framework.get("total_nodes", 0)
    print(f"  Nodes to translate: {node_count}")

    print("Translating with glossary...")
    translated = _translate_with_glossary(framework)

    print(f"  Translated {translated} fields")
    write_json(framework, FRAMEWORK_PATH)
    print(f"  Written: {FRAMEWORK_PATH}")


if __name__ == "__main__":
    main()
