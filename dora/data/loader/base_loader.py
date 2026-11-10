"""
基础数据加载器抽象类
定义数据加载模块的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseDataLoader(ABC):
    """数据加载器抽象基类"""

    @abstractmethod
    def load(self, file_path: str) -> List[Dict[str, Any]]:
        """
        从文件加载数据记录

        Args:
            file_path: 数据文件路径

        Returns:
            记录列表，每条记录为字典格式，包含至少以下字段：
            - Question_Body: 问题内容
            - Accepted_Answer_Body: 接受的答案内容
            - category: 分类（可选）
            - subcategory: 子分类（可选）
        """
        pass
