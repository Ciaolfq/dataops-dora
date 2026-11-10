"""
内存检索实现（基于关键词匹配）
用于测试和轻量级场景，无需向量数据库依赖
"""

import re
from typing import Any, Dict, List, Optional

from core.retrieval.base import BaseRetrieval, RetrievedDocument
from utils.logger import logger


class MemoryRetrieval(BaseRetrieval):
    """
    内存检索器（基于关键词匹配）

    特性：
    - 纯内存存储，无需外部数据库
    - 基于关键词和 TF-IDF 简化版匹配
    - 支持元数据过滤
    - 适合小规模数据集和测试场景
    """

    def __init__(
        self,
        documents: Optional[List[Dict[str, Any]]] = None,
        default_topn: int = 10,
    ) -> None:
        """
        初始化内存检索器

        Args:
            documents: 初始文档列表，每个文档包含 content 和 metadata
            default_topn: 默认返回结果数量
        """
        self.default_topn = default_topn
        self._docs: List[RetrievedDocument] = []

        if documents:
            self.add_documents(documents)

        logger.info(
            f"MemoryRetrieval 初始化完成 | docs={len(self._docs)} | "
            f"default_topn={self.default_topn}"
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        添加文档到内存索引

        Args:
            documents: 文档列表，每个元素为 {"content": "...", "metadata": {...}}
        """
        for i, doc in enumerate(documents):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            doc_id = doc.get("doc_id", f"mem_doc_{len(self._docs) + i}")
            self._docs.append(
                RetrievedDocument(
                    content=content,
                    metadata=metadata,
                    doc_id=doc_id,
                )
            )
        logger.info(f"MemoryRetrieval 添加了 {len(documents)} 篇文档，总计 {len(self._docs)} 篇")

    def _tokenize(self, text: str) -> set:
        """简单分词：提取单词和重要术语"""
        # 提取单词（排除过短的词）
        words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]{2,}\b', text.lower())
        return set(words)

    def _compute_score(self, query: str, doc: RetrievedDocument) -> float:
        """
        计算查询与文档的匹配分数（基于关键词覆盖率）

        Args:
            query: 查询文本
            doc: 文档

        Returns:
            相似度分数（0-1）
        """
        query_tokens = self._tokenize(query)
        doc_tokens = self._tokenize(doc.content)

        if not query_tokens or not doc_tokens:
            return 0.0

        # 计算 Jaccard 相似度
        intersection = query_tokens & doc_tokens
        union = query_tokens | doc_tokens
        jaccard = len(intersection) / len(union) if union else 0.0

        # 计算查询词覆盖率（召回导向）
        recall = len(intersection) / len(query_tokens) if query_tokens else 0.0

        # 加权组合（更看重查询词命中）
        score = recall * 0.6 + jaccard * 0.4

        return score

    def search(
        self,
        query: str,
        top_n: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """
        关键词检索

        Args:
            query: 查询文本
            top_n: 返回结果数量
            filter: 元数据过滤条件

        Returns:
            检索到的文档列表，按匹配分数降序排列
        """
        top = top_n if top_n else self.default_topn

        # 过滤文档
        candidates = self._docs
        if filter:
            candidates = [
                doc for doc in candidates
                if all(
                    doc.metadata.get(k) == v
                    for k, v in filter.items()
                )
            ]

        # 计算分数并排序
        scored = []
        for doc in candidates:
            score = self._compute_score(query, doc)
            if score > 0:
                doc_copy = RetrievedDocument(
                    content=doc.content,
                    metadata=dict(doc.metadata),
                    score=score,
                    doc_id=doc.doc_id,
                )
                scored.append(doc_copy)

        scored.sort(key=lambda d: d.score, reverse=True)
        results = scored[:top]

        logger.debug(
            f"Memory 检索完成 | query='{query[:50]}...' | "
            f"results={len(results)} | filter={filter}"
        )

        return results

    def search_multi(
        self,
        queries: List[str],
        top_n: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """
        多查询检索（多路召回），自动去重合并

        Args:
            queries: 查询文本列表
            top_n: 每个查询返回的结果数量
            filter: 元数据过滤条件

        Returns:
            合并去重后的文档列表
        """
        if not queries:
            return []

        all_docs: Dict[str, RetrievedDocument] = {}

        for query in queries:
            docs = self.search(query, top_n=top_n, filter=filter)
            for doc in docs:
                key = doc.doc_id or doc.content[:100]
                if key in all_docs:
                    if doc.score is not None and (
                        all_docs[key].score is None or doc.score > all_docs[key].score
                    ):
                        all_docs[key].score = doc.score
                else:
                    all_docs[key] = doc

        results = sorted(
            all_docs.values(),
            key=lambda d: d.score if d.score is not None else -1,
            reverse=True,
        )

        logger.info(
            f"Memory 多路召回完成 | 查询数={len(queries)} | 去重后={len(results)}"
        )

        return results

    def count(self) -> int:
        """返回文档总数"""
        return len(self._docs)

    def clear(self) -> None:
        """清空所有文档"""
        self._docs = []
        logger.info("MemoryRetrieval 已清空所有文档")
