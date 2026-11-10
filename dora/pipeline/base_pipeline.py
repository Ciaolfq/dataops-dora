"""
基础流水线抽象类
定义 RAG 流水线的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional

from core.retrieval.base import RetrievedDocument


class PipelineResult:
    """
    流水线执行结果封装

    结构化输出格式：
    - root_cause: 根因分析
    - category: 故障分类
    - confidence: 置信度
    - fix_steps: 修复步骤列表
    - references: 引用来源列表
    - answer: 原始回答文本
    """

    def __init__(
        self,
        answer: str = "",
        root_cause: str = "",
        category: str = "",
        confidence: float = 0.0,
        fix_steps: Optional[List[str]] = None,
        references: Optional[List[Dict[str, Any]]] = None,
        raw_query: str = "",
        rewritten_queries: Optional[List[str]] = None,
        retrieved_docs: Optional[List[RetrievedDocument]] = None,
        reranked_docs: Optional[List[RetrievedDocument]] = None,
    ) -> None:
        self.answer = answer
        self.root_cause = root_cause
        self.category = category
        self.confidence = confidence
        self.fix_steps = fix_steps or []
        self.references = references or []
        self.raw_query = raw_query
        self.rewritten_queries = rewritten_queries or []
        self.retrieved_docs = retrieved_docs or []
        self.reranked_docs = reranked_docs or []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 API 返回）"""
        return {
            "answer": self.answer,
            "root_cause": self.root_cause,
            "category": self.category,
            "confidence": self.confidence,
            "fix_steps": self.fix_steps,
            "references": self.references,
            "raw_query": self.raw_query,
            "rewritten_queries": self.rewritten_queries,
            "retrieved_count": len(self.retrieved_docs),
            "reranked_count": len(self.reranked_docs),
        }


class BasePipeline(ABC):
    """RAG 流水线抽象基类"""

    @abstractmethod
    def run(self, query: str, **kwargs: Any) -> PipelineResult:
        """
        非流式执行完整流水线

        Args:
            query: 用户查询
            **kwargs: 额外参数

        Returns:
            流水线执行结果
        """
        pass

    @abstractmethod
    def run_stream(self, query: str, **kwargs: Any) -> Iterator[str]:
        """
        流式执行流水线（仅返回生成的文本流）

        Args:
            query: 用户查询
            **kwargs: 额外参数

        Yields:
            逐块生成的文本片段
        """
        pass
