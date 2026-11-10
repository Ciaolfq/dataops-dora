"""
通用工具函数
包含 Prompt 构建、文本处理等常用工具
"""

import json
import re
from typing import Any, Dict, List

from core.retrieval.base import RetrievedDocument


# ============================================================
# DORA 增强版 Prompt 模板
# ============================================================

DORA_SYSTEM_PROMPT_TEMPLATE = """You are an expert DataOps and dbt fault diagnosis assistant.
Your task is to analyze user-submitted error logs, failures, and questions, then provide
accurate root cause analysis and actionable repair solutions based on reference fault cases.

Key responsibilities:
1. Identify the root cause of the problem
2. Classify the fault category
3. Provide step-by-step fix instructions
4. Cite reference sources that support your diagnosis

Output requirements:
- Respond in ENGLISH
- Be precise and evidence-based; do not speculate without supporting references
- Include code blocks when providing configuration or command fixes
- Structure your answer clearly with sections

You MUST output a JSON block at the end of your answer with the following structure:
```json
{{
  "root_cause": "Brief description of the root cause",
  "category": "Fault category (e.g., configuration_error, dependency_issue, permission_error, syntax_error, network_issue, resource_exhaustion)",
  "confidence": 0.95,
  "fix_steps": [
    "Step 1 description",
    "Step 2 description",
    "Step 3 description"
  ]
}}
```
"""

DORA_USER_PROMPT_TEMPLATE = """## Reference Fault Cases

The following are relevant fault diagnosis cases from the knowledge base.
Use them as evidence to support your diagnosis. Each case is numbered for reference.

{reference_block}

---

## User Question / Error Report

{user_query}

---

## Instructions

1. Analyze the user's problem carefully
2. Use the reference cases as your primary evidence source
3. If the reference cases do not contain relevant information, say so clearly
4. Provide your diagnosis and solution in a structured format
5. Include the required JSON block at the end of your answer
"""


def build_dora_system_prompt() -> str:
    """
    构建 DORA 系统 Prompt（定义角色和输出格式）

    Returns:
        系统提示文本
    """
    return DORA_SYSTEM_PROMPT_TEMPLATE


def build_dora_prompt(
    user_query: str,
    reference_docs: List[RetrievedDocument],
) -> str:
    """
    构建 DORA 用户 Prompt（包含参考文档和用户问题）

    Args:
        user_query: 用户查询
        reference_docs: 参考文档列表

    Returns:
        用户提示文本
    """
    # 构建参考文档块
    doc_sections = []
    for i, doc in enumerate(reference_docs, 1):
        category = doc.metadata.get("category", "Unknown")
        subcategory = doc.metadata.get("subcategory", "")
        cat_label = f"{category} / {subcategory}" if subcategory else category

        doc_section = f"""### Reference [{i}] - {cat_label}

{doc.content}
"""
        doc_sections.append(doc_section)

    reference_block = "\n".join(doc_sections) if doc_sections else "No reference documents available."

    return DORA_USER_PROMPT_TEMPLATE.format(
        reference_block=reference_block,
        user_query=user_query,
    )


# ============================================================
# 标准 RAG Prompt 模板（Baseline）
# ============================================================

STANDARD_RAG_PROMPT_TEMPLATE = """You are a professional dbt / DataOps fault diagnosis expert.
You must answer all questions completely in ENGLISH only, do not use any Chinese characters.
Based on the real community fault Q&A cases below, locate the root cause of the user's problem,
and provide complete executable repair code.
Do not guess without evidence, keep the answer concise and clear with standard code blocks.

【Reference Cases】
{doc_block}

【User Question】
{user_query}
"""


def build_standard_rag_prompt(
    user_query: str,
    reference_docs: List[RetrievedDocument],
) -> str:
    """
    构建标准 RAG Prompt（Baseline 版本）

    Args:
        user_query: 用户查询
        reference_docs: 参考文档列表

    Returns:
        完整的 Prompt 文本
    """
    doc_contents = [doc.content for doc in reference_docs]
    doc_block = "\n==========Reference Fault Cases==========\n".join(doc_contents)

    return STANDARD_RAG_PROMPT_TEMPLATE.format(
        doc_block=doc_block,
        user_query=user_query,
    )


# ============================================================
# 通用工具函数
# ============================================================

def clean_text(text: str) -> str:
    """
    清理文本：去除多余空白、统一换行符等

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 去除多余空行（最多保留一个空行）
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行尾空格
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def safe_json_parse(text: str, default: Any = None) -> Any:
    """
    安全解析 JSON，解析失败返回默认值

    Args:
        text: JSON 字符串
        default: 解析失败时的默认值

    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    从文本中提取 JSON 对象（支持代码块包裹）

    Args:
        text: 包含 JSON 的文本

    Returns:
        解析后的 JSON 字典，失败返回空字典
    """
    # 尝试匹配 ```json ... ```
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if match:
        result = safe_json_parse(match.group(1), None)
        if result is not None:
            return result

    # 尝试匹配第一个完整的 JSON 对象
    brace_count = 0
    start = -1
    for i, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start >= 0:
                result = safe_json_parse(text[start : i + 1], None)
                if result is not None:
                    return result

    return {}
