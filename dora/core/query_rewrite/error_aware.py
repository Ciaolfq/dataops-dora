"""
增强版错误感知查询重写器

功能：
1. 从错误日志/查询中提取关键信息（错误类型、堆栈、错误码、关键字）
2. 生成多个重写查询（同义词扩展、术语标准化、场景补充）
3. 使用 LLM 进行智能查询扩展，支持多路召回
"""

import re
from typing import Dict, List, Optional

from core.query_rewrite.base import BaseQueryRewrite
from core.llm.openai_compatible import OpenAICompatibleLLM
from config.config_loader import global_cfg
from utils.logger import logger


class ErrorAwareRewrite(BaseQueryRewrite):
    """
    错误感知查询重写器

    增强特性：
    - 错误信息结构化提取（错误码、堆栈、异常类型）
    - 多查询扩展（同义词、术语标准化、场景补充）
    - 基于 LLM 的智能改写
    """

    # 常见错误码模式
    ERROR_CODE_PATTERNS = [
        r"ERROR[_-]?\d+",
        r"ERR[_-]?\d+",
        r"\b[A-Z]{2,}\d{3,}\b",  # 类似 DB101, SQL001 等
    ]

    # 常见异常类型关键词
    EXCEPTION_KEYWORDS = [
        "Exception", "Error", "Failure", "Failed", "Timeout",
        "Connection", "Permission", "Denied", "NotFound", "Invalid",
        "SyntaxError", "RuntimeError", "ValueError", "TypeError",
        "NullPointerException", "IndexError", "KeyError", "AttributeError",
    ]

    def __init__(self) -> None:
        """初始化错误感知查询重写器"""
        rewrite_cfg = global_cfg.get("query_rewrite", {})
        self.num_expansions = rewrite_cfg.get("num_expansions", 3)
        self.extract_error_info = rewrite_cfg.get("extract_error_info", True)

        # 初始化 LLM
        llm_cfg = global_cfg.get("llm", {})
        self.llm = OpenAICompatibleLLM(llm_cfg)

        logger.info(
            f"ErrorAwareRewrite 初始化完成 | "
            f"num_expansions={self.num_expansions} | "
            f"extract_error_info={self.extract_error_info}"
        )

    def extract_error_metadata(self, query: str) -> Dict[str, any]:
        """
        从查询中提取错误相关的元数据信息

        Args:
            query: 原始查询文本

        Returns:
            包含错误元数据的字典：
            - error_codes: 提取到的错误码列表
            - exception_types: 提取到的异常类型列表
            - has_stack_trace: 是否包含堆栈跟踪
            - key_terms: 关键术语列表
        """
        result = {
            "error_codes": [],
            "exception_types": [],
            "has_stack_trace": False,
            "key_terms": [],
        }

        # 提取错误码
        for pattern in self.ERROR_CODE_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            result["error_codes"].extend(matches)

        # 去重
        result["error_codes"] = list(set(result["error_codes"]))

        # 提取异常类型
        for kw in self.EXCEPTION_KEYWORDS:
            if re.search(re.escape(kw), query, re.IGNORECASE):
                result["exception_types"].append(kw)

        # 检测堆栈跟踪（包含 "at " 或 "File " 等典型堆栈模式）
        stack_indicators = [
            r"\bat\s+\w+\.\w+\(",  # Java/C# 风格: at Class.method(
            r'File ".*", line \d+',  # Python 风格: File "x.py", line 10
            r"^\s+at ",  # 缩进的 at 行
            r"stack\s*trace",
            r"traceback",
        ]
        for indicator in stack_indicators:
            if re.search(indicator, query, re.IGNORECASE | re.MULTILINE):
                result["has_stack_trace"] = True
                break

        # 提取关键术语（长度 > 3 的非停用词）
        key_terms = re.findall(r"\b[A-Z][a-zA-Z]{3,}\b", query)
        result["key_terms"] = list(set(key_terms))[:10]  # 最多保留 10 个

        return result

    def rewrite(self, raw_query: str) -> str:
        """
        重写单个查询（返回最佳重写结果）

        Args:
            raw_query: 原始查询文本

        Returns:
            重写后的查询文本
        """
        expanded_queries = self.rewrite_multi(raw_query, num_expansions=1)
        return expanded_queries[0] if expanded_queries else raw_query

    def rewrite_multi(self, raw_query: str, num_expansions: Optional[int] = None) -> List[str]:
        """
        生成多个扩展查询（用于多路召回）

        Args:
            raw_query: 原始查询文本
            num_expansions: 扩展查询数量（不包含原始查询）

        Returns:
            扩展查询列表，第一个为原始查询
        """
        if num_expansions is None:
            num_expansions = self.num_expansions

        logger.debug(f"开始查询重写 | 原始查询: {raw_query[:100]}...")

        # 提取错误元数据
        error_meta = {}
        if self.extract_error_info:
            error_meta = self.extract_error_metadata(raw_query)
            logger.debug(
                f"提取到错误元数据 | "
                f"error_codes={error_meta.get('error_codes', [])} | "
                f"exception_types={error_meta.get('exception_types', [])} | "
                f"has_stack_trace={error_meta.get('has_stack_trace', False)}"
            )

        # 使用 LLM 生成扩展查询
        try:
            expanded = self._llm_expand_query(raw_query, error_meta, num_expansions)
        except Exception as e:
            logger.warning(f"LLM 查询扩展失败，使用原始查询: {str(e)}")
            expanded = []

        # 确保原始查询在列表第一个位置
        result = [raw_query] + expanded

        # 去重（保持顺序）
        seen = set()
        unique_result = []
        for q in result:
            q_stripped = q.strip()
            if q_stripped and q_stripped not in seen:
                seen.add(q_stripped)
                unique_result.append(q_stripped)

        logger.info(
            f"查询重写完成 | 原始 1 个 -> 扩展后 {len(unique_result)} 个"
        )

        return unique_result

    def _llm_expand_query(
        self,
        raw_query: str,
        error_meta: Dict[str, any],
        num_expansions: int
    ) -> List[str]:
        """
        使用 LLM 生成扩展查询

        Args:
            raw_query: 原始查询
            error_meta: 错误元数据
            num_expansions: 扩展数量

        Returns:
            扩展查询列表
        """
        # 构建错误信息摘要
        error_summary = ""
        if error_meta.get("error_codes"):
            error_summary += f"- Error codes found: {', '.join(error_meta['error_codes'])}\n"
        if error_meta.get("exception_types"):
            error_summary += f"- Exception types: {', '.join(error_meta['exception_types'])}\n"
        if error_meta.get("has_stack_trace"):
            error_summary += "- Contains stack trace\n"
        if error_meta.get("key_terms"):
            error_summary += f"- Key technical terms: {', '.join(error_meta['key_terms'])}\n"

        system_prompt = (
            "You are an expert query expansion specialist for DataOps and dbt fault diagnosis. "
            "Your task is to generate diverse, semantically equivalent queries to improve "
            "retrieval recall from a technical knowledge base.\n\n"
            "Expansion strategies:\n"
            "1. Synonym expansion: Replace technical terms with common synonyms\n"
            "2. Terminology standardization: Convert informal terms to standard dbt/DataOps terminology\n"
            "3. Scenario enrichment: Add context about common DataOps failure scenarios\n"
            "4. Error code emphasis: Highlight error codes and exception names\n"
            "5. Abbreviation expansion: Expand common abbreviations to full terms\n\n"
            "Rules:\n"
            "- Each expanded query must be a complete, standalone question or search query\n"
            "- All queries must be in ENGLISH\n"
            "- Make each query different in wording and focus\n"
            "- Do not add explanations or numbering\n"
            f"- Generate exactly {num_expansions} expanded queries\n"
            "- Output each query on a separate line"
        )

        user_prompt = f"Original query:\n{raw_query}\n\n"

        if error_summary:
            user_prompt += f"Extracted error metadata from query:\n{error_summary}\n"

        user_prompt += (
            f"\nPlease generate {num_expansions} expanded queries for better retrieval. "
            "Output only the queries, one per line, no numbering, no explanation."
        )

        response = self.llm.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,  # 稍高温度以获得多样性
        )

        # 解析响应，每行一个查询
        queries = []
        for line in response.strip().split("\n"):
            line = line.strip()
            # 跳过空行和编号行
            if not line:
                continue
            # 移除可能的编号（如 "1. ", "1) ", "- " 等）
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            line = re.sub(r"^[-*•]\s*", "", line)
            if line and len(line) > 10:  # 过滤掉过短的行
                queries.append(line)
            if len(queries) >= num_expansions:
                break

        return queries
