"""AI Impact Scanner — LLM calls and JSON parsing.

Supports Gemini (google-genai) and DeepSeek (OpenAI-compatible).
Each call returns a unified LLMResponse dataclass.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

logger = logging.getLogger("scanner")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一个企业流程知识分析专家，专门评估AI技术对企业运营流程的影响。

你的任务是对企业流程节点进行AI冲击扫描，判断每个流程节点在AI时代的变化状态和变化性质。

## 你的知识边界声明

你的判断基于训练数据中包含的以下类型信息：
- 学术论文和研究报告
- 行业媒体的案例报道
- 企业公开披露的转型信息
- 咨询机构发布的行业分析
- 监管和政策文件

你必须区分以下两类信息并在输出中明确标注：
- 类型A：有具体案例、数据或研究支撑的判断（较可靠）
- 类型B：基于行业趋势讨论和预测的判断（存在舆论高估风险）

## 你必须严格遵守的规则

规则1：禁止基于技术可能性做判断。AI技术上能做到不等于企业实际在这样做。你的判断必须基于有证据的实际发生，而非技术潜力。

规则2：禁止混淆标杆企业和普遍企业。少数领先企业的实践不代表行业普遍状态。如果你的证据主要来自标杆企业，必须在输出中明确标注。

规则3：禁止将企业宣称的意图等同于已发生的行为。企业发布的转型计划、战略声明不构成变化已发生的证据。

规则4：当你对某个判断不确定时，必须在不确定性说明中如实表达，不得为了输出完整而虚构判断。

规则5：每个判断必须附带判断依据类型标注，不得输出无依据来源的结论。

## 输出要求

你必须且只能输出一个合法的JSON对象，不要输出任何JSON之外的内容，不要使用markdown代码块包裹，不要添加任何解释性文字。

## 你的角色定位

你是假说生成器，不是权威来源。你的输出将进入人工验证流程，最终由人工判断是否采纳。你的任务是提供尽可能有用且诚实的初始判断，而不是提供看起来完整但实际上缺乏依据的判断。\
"""

USER_PROMPT_TEMPLATE = """\
## 待扫描流程节点信息

节点ID：{node_id}
节点名称（中文）：{node_name_zh}
节点名称（英文）：{node_name_en}
所属框架：{source_framework}
框架原始分类路径：{taxonomy_path}
节点层级：{node_level}
节点原始描述：
{node_description}
所属行业领域标签：{domain_tags}

---

## 你的扫描任务

请对上述流程节点进行AI冲击扫描，严格按照以下六个维度逐一输出判断。

### 维度1：AI渗透率评估

请评估以下三个子项，每个子项给出高/中/低的判断，并用1-2句话说明依据：

1a. 核心决策替代性
1b. 信息处理加速性
1c. 隐性知识依赖度

综合AI渗透率：高/中/低

### 维度2：变化状态判断

选项A：已变  选项B：将变  选项C：稳定

### 维度3：变化性质分类

性质A：增强型  性质B：压缩型  性质C：消亡型  性质D：涌现型

### 维度4：人机边界当前判断

类型1-4中选择

### 维度5：不确定性说明

### 维度6：信号质量自评

## 输出格式

请严格按照以下JSON格式输出：

{{
  "node_id": "{node_id}",
  "scan_timestamp": "ISO8601格式时间",
  "model_id": "你的模型标识",
  "dimension_1_ai_penetration": {{
    "decision_replaceability": {{"rating": "高/中/低", "basis": "判断依据"}},
    "processing_acceleration": {{"rating": "高/中/低", "basis": "判断依据"}},
    "tacit_knowledge_dependency": {{"rating": "高/中/低", "basis": "判断依据"}},
    "overall_penetration": "高/中/低"
  }},
  "dimension_2_change_status": {{
    "status": "已变/将变/稳定",
    "evidence_type": "类型A/类型B/混合",
    "evidence_source": "来源描述",
    "basis_description": "核心依据描述"
  }},
  "dimension_3_change_nature": {{
    "applicable": true,
    "types_selected": ["A"],
    "type_descriptions": {{
      "A": "描述或null", "B": "描述或null",
      "C": "描述或null", "D": "描述或null"
    }}
  }},
  "dimension_4_boundary": {{
    "current_type": "类型1/类型2/类型3/类型4",
    "boundary_description": "说明",
    "stability": "稳定/过渡中/高度不确定",
    "stability_note": "说明"
  }},
  "dimension_5_uncertainty": {{
    "overall_confidence": "高/中/低",
    "uncertainty_sources": ["选项列表"],
    "special_note": "说明或null"
  }},
  "dimension_6_signal_quality": {{
    "information_period": "时间范围",
    "source_distribution": {{
      "academic": "高/中/低/无",
      "industry_media": "高/中/低/无",
      "corporate_disclosure": "高/中/低/无",
      "consulting_reports": "高/中/低/无",
      "regulatory": "高/中/低/无"
    }},
    "potential_bias": "偏差提示"
  }},
  "scan_summary": {{
    "one_line_judgment": "一句话概括",
    "priority_flag": "高优先级验证/常规验证/低优先级验证",
    "priority_reason": "理由"
  }}
}}\
"""

# ---------------------------------------------------------------------------
# LLMResponse
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    """Unified response from any LLM call."""

    model_id: str = ""
    raw_response: str = ""
    parsed_json: dict | None = None
    parsed_success: bool = False
    parse_error: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time_ms: int = 0
    api_error: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    model_config: str = ""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_user_prompt(node: dict) -> str:
    """Fill the user prompt template with node data."""
    return USER_PROMPT_TEMPLATE.format(
        node_id=node.get("node_id", ""),
        node_name_zh=node.get("node_name_zh", ""),
        node_name_en=node.get("node_name_en", ""),
        source_framework=node.get("source_framework", ""),
        taxonomy_path=node.get("taxonomy_path", ""),
        node_level=node.get("node_level", ""),
        node_description=node.get("node_description", ""),
        domain_tags=node.get("domain_tags", ""),
    )


# ---------------------------------------------------------------------------
# JSON parsing (3-step fallback)
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_JSON_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_response(raw: str) -> tuple[dict | None, str]:
    """Parse LLM output to JSON with 3-step fallback.

    Returns (parsed_dict, error_string). error_string is empty on success.
    """
    if not raw or not raw.strip():
        return None, "empty response"

    # Step 1: direct parse
    try:
        return json.loads(raw), ""
    except json.JSONDecodeError:
        pass

    # Step 2: extract ```json ... ``` block
    m = _JSON_BLOCK_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(1)), ""
        except json.JSONDecodeError:
            pass

    # Step 3: first { to last }
    m = _JSON_BRACE_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(0)), ""
        except json.JSONDecodeError as exc:
            return None, f"brace extraction failed: {exc}"

    return None, "no JSON found in response"


# ---------------------------------------------------------------------------
# Model dispatch
# ---------------------------------------------------------------------------

# Rate-limit config from env
_RATE_LIMIT_WAIT = float(os.environ.get("SCAN_RATE_LIMIT_WAIT", "1"))
_MAX_RETRY = int(os.environ.get("SCAN_MAX_RETRY", "3"))
_RETRY_WAIT = float(os.environ.get("SCAN_RETRY_WAIT", "60"))


def _retry_on_rate_limit(func, *args, **kwargs):
    """Call func with exponential backoff on 429/503 errors."""
    for attempt in range(_MAX_RETRY):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            err = str(exc).lower()
            is_rate_limit = "429" in err or "503" in err or "rate" in err
            if is_rate_limit and attempt < _MAX_RETRY - 1:
                wait = _RETRY_WAIT * (2 ** attempt)
                logger.warning("Rate limited, retry %d/%d in %.0fs",
                               attempt + 1, _MAX_RETRY, wait)
                time.sleep(wait)
                continue
            raise


def call_gemini(node: dict) -> LLMResponse:
    """Call Gemini via google-genai SDK."""
    resp = LLMResponse(model_id="gemini-2.5-flash")
    start = time.monotonic()

    try:
        from google import genai

        client = genai.Client()
        prompt = build_user_prompt(node)

        resp.system_prompt = SYSTEM_PROMPT
        resp.user_prompt = prompt
        resp.model_config = json.dumps(
            {"model": "gemini-2.5-flash", "temperature": 0.3},
            ensure_ascii=False,
        )

        result = _retry_on_rate_limit(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )

        resp.raw_response = result.text or ""
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            resp.prompt_tokens = result.usage_metadata.prompt_token_count or 0
            resp.completion_tokens = (
                result.usage_metadata.candidates_token_count or 0
            )
            resp.total_tokens = result.usage_metadata.total_token_count or 0

    except Exception as exc:
        resp.api_error = str(exc)
        logger.error("Gemini API error: %s", exc)

    resp.response_time_ms = int((time.monotonic() - start) * 1000)

    if resp.raw_response and not resp.api_error:
        parsed, err = parse_json_response(resp.raw_response)
        resp.parsed_json = parsed
        resp.parsed_success = parsed is not None
        resp.parse_error = err

    time.sleep(_RATE_LIMIT_WAIT)
    return resp


def call_deepseek(node: dict) -> LLMResponse:
    """Call DeepSeek via OpenAI-compatible API."""
    resp = LLMResponse(model_id="deepseek-v3-cn")
    start = time.monotonic()

    try:
        from openai import OpenAI

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            resp.api_error = "DEEPSEEK_API_KEY not set"
            resp.response_time_ms = int((time.monotonic() - start) * 1000)
            return resp

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        prompt = build_user_prompt(node)

        resp.system_prompt = SYSTEM_PROMPT
        resp.user_prompt = prompt
        resp.model_config = json.dumps(
            {"model": "deepseek-chat", "temperature": 0.3},
            ensure_ascii=False,
        )

        result = _retry_on_rate_limit(
            client.chat.completions.create,
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        resp.raw_response = result.choices[0].message.content or ""
        if result.usage:
            resp.prompt_tokens = result.usage.prompt_tokens or 0
            resp.completion_tokens = result.usage.completion_tokens or 0
            resp.total_tokens = result.usage.total_tokens or 0

    except Exception as exc:
        resp.api_error = str(exc)
        logger.error("DeepSeek API error: %s", exc)

    resp.response_time_ms = int((time.monotonic() - start) * 1000)

    if resp.raw_response and not resp.api_error:
        parsed, err = parse_json_response(resp.raw_response)
        resp.parsed_json = parsed
        resp.parsed_success = parsed is not None
        resp.parse_error = err

    time.sleep(_RATE_LIMIT_WAIT)
    return resp


MODEL_DISPATCH: dict[str, callable] = {
    "gemini": call_gemini,
    "deepseek": call_deepseek,
}
