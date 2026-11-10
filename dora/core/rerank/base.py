"""
基础重排抽象类
定义重排模块的统一接口
"""

from abc import ABC, abstractmethod
from typing import List

from core.retrieval.base import RetrievedDocument


class BaseRerank(ABC):
    """重排器抽象基类"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_n: int = None,
    ) -> List[RetrievedDocument]:
        """
        对检索结果进行重排序

        Args:
            query: 查询文本
            documents: 待重排的文档列表
            top_n: 重排后保留的文档数量，None 则保留全部

        Returns:
            重排后的文档列表，按相关性降序排列
        """
        pass
