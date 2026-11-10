"""
简单重排器（Baseline）
不改变文档顺序，直接返回原结果。
用作对比基线，衡量重排模块的效果。
"""

from typing import List, Optional

from core.rerank.base import BaseRerank
from core.retrieval.base import RetrievedDocument


class SimpleRerank(BaseRerank):
    """
    简单重排器（直通模式）

    不进行任何重排序操作，直接返回原始检索结果。
    作为 Baseline 使用，用于对比 Cross-Encoder 重排的增益效果。
    """

    def __init__(self) -> None:
        """初始化简单重排器"""
        pass

    def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_n: Optional[int] = None,
    ) -> List[RetrievedDocument]:
        """
        直通重排：直接返回原始结果（可选截断）

        Args:
            query: 查询文本（未使用，保留接口一致性）
            documents: 待重排的文档列表
            top_n: 保留的文档数量，None 则保留全部

        Returns:
            原始文档列表（按原顺序）
        """
        if top_n is not None:
            return documents[:top_n]
        return list(documents)
