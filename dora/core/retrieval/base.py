"""
基础检索抽象类
定义检索模块的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class RetrievedDocument:
    """检索结果文档封装"""

    def __init__(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        score: Optional[float] = None,
        doc_id: Optional[str] = None,
    ) -> None:
        """
        初始化检索文档

        Args:
            content: 文档内容
            metadata: 文档元数据（如 category, subcategory 等）
            score: 检索相似度得分
            doc_id: 文档唯一标识
        """
        self.content = content
        self.metadata = metadata or {}
        self.score = score
        self.doc_id = doc_id

    def __repr__(self) -> str:
        return (
            f"RetrievedDocument(id={self.doc_id}, score={self.score:.4f}, "
            f"content={self.content[:50]}...)"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata,
            "score": self.score,
        }


class BaseRetrieval(ABC):
    """检索器抽象基类"""

    @abstractmethod
    def search(
        self,
        query: str,
        top_n: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """
        根据查询检索相关文档

        Args:
            query: 查询文本
            top_n: 返回结果数量，为 None 时使用默认值
            filter: 元数据过滤条件，如 {"category": "dbt_run_error"}

        Returns:
            检索到的文档列表，按相似度排序
        """
        pass

    @abstractmethod
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
            top_n: 每个查询返回结果数量
            filter: 元数据过滤条件

        Returns:
            合并去重后的文档列表
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        返回向量库中文档总数

        Returns:
            文档总数
        """
        pass
