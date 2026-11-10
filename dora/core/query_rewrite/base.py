"""
基础查询重写抽象类
定义查询重写模块的统一接口
"""

from abc import ABC, abstractmethod
from typing import List


class BaseQueryRewrite(ABC):
    """查询重写抽象基类"""

    @abstractmethod
    def rewrite(self, raw_query: str) -> str:
        """
        重写单个查询（返回单个重写后的查询）

        Args:
            raw_query: 原始查询文本

        Returns:
            重写后的查询文本
        """
        pass

    @abstractmethod
    def rewrite_multi(self, raw_query: str, num_expansions: int = 3) -> List[str]:
        """
        生成多个扩展查询（用于多路召回）

        Args:
            raw_query: 原始查询文本
            num_expansions: 扩展查询数量

        Returns:
            扩展查询列表（包含原始查询）
        """
        pass
