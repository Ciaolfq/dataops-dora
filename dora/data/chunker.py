"""
文档分块器
支持多种分块策略：固定大小分块（带重叠）、分类元数据增强，预留语义分块接口
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import logger


class DocumentChunker:
    """
    文档分块器

    支持的分块策略：
    1. 固定大小分块（fixed）：按字符数分割，带重叠
    2. 语义分块（semantic）：基于语义边界分割（需额外模型，预留接口）
    3. 整文档（whole）：不分割，整篇作为一个 chunk

    所有策略均支持元数据增强（在 chunk 开头添加分类信息）
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        strategy: str = "fixed",
        add_metadata_prefix: bool = True,
    ) -> None:
        """
        初始化文档分块器

        Args:
            chunk_size: 每个 chunk 的目标字符数
            chunk_overlap: chunk 之间的重叠字符数
            strategy: 分块策略："fixed" | "semantic" | "whole"
            add_metadata_prefix: 是否在每个 chunk 前添加分类元数据前缀
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.add_metadata_prefix = add_metadata_prefix

        if strategy not in ("fixed", "semantic", "whole"):
            raise ValueError(f"不支持的分块策略: {strategy}")

        logger.info(
            f"DocumentChunker 初始化 | strategy={strategy} | "
            f"chunk_size={chunk_size} | overlap={chunk_overlap} | "
            f"metadata_prefix={add_metadata_prefix}"
        )

    def chunk_record(self, record: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        将单条记录分块为多个文档片段

        Args:
            record: 数据记录字典

        Returns:
            (chunk_text, metadata) 元组列表
        """
        # 构建完整文档文本
        full_text = self._build_full_text(record)

        # 提取元数据
        metadata = self._extract_metadata(record)

        # 选择分块策略
        if self.strategy == "whole":
            chunks = [(full_text, metadata)]
        elif self.strategy == "fixed":
            chunks = self._fixed_size_chunk(full_text, metadata)
        elif self.strategy == "semantic":
            chunks = self._semantic_chunk(full_text, metadata)
        else:
            chunks = [(full_text, metadata)]

        # 添加元数据前缀
        if self.add_metadata_prefix:
            chunks = [
                (self._add_metadata_prefix(text, meta), meta)
                for text, meta in chunks
            ]

        return chunks

    def chunk_records(self, records: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        批量分块多条记录

        Args:
            records: 记录列表

        Returns:
            所有 chunk 的 (text, metadata) 元组列表
        """
        all_chunks = []
        for idx, record in enumerate(records):
            chunks = self.chunk_record(record)
            # 为每个 chunk 添加记录索引
            for i, (text, meta) in enumerate(chunks):
                meta = dict(meta)
                meta["record_index"] = idx
                meta["chunk_index"] = i
                all_chunks.append((text, meta))

        logger.info(
            f"文档分块完成 | {len(records)} 条记录 -> {len(all_chunks)} 个 chunk"
        )
        return all_chunks

    def _build_full_text(self, record: Dict[str, Any]) -> str:
        """
        从记录构建完整文档文本

        Args:
            record: 数据记录

        Returns:
            拼接后的完整文本
        """
        q = record.get("Question_Body", record.get("question", ""))
        a = record.get("Accepted_Answer_Body", record.get("answer", ""))
        title = record.get("Title", record.get("title", ""))

        parts = []
        if title:
            parts.append(f"标题：{title}")
        parts.append(f"问题：{q}")
        parts.append(f"解决方案：{a}")

        return "\n".join(parts)

    def _extract_metadata(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        从记录中提取元数据

        Args:
            record: 数据记录

        Returns:
            元数据字典
        """
        metadata = {
            "category": record.get("category", ""),
            "subcategory": record.get("subcategory", ""),
            "title": record.get("Title", record.get("title", "")),
            "post_id": record.get("Id", record.get("post_id", "")),
        }
        # 移除空值
        return {k: v for k, v in metadata.items() if v}

    def _add_metadata_prefix(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        在文本前添加元数据前缀，增强检索效果

        Args:
            text: 原始文本
            metadata: 元数据

        Returns:
            带前缀的文本
        """
        prefix_parts = []

        if metadata.get("category"):
            prefix_parts.append(f"分类：{metadata['category']}")
        if metadata.get("subcategory"):
            prefix_parts.append(f"子分类：{metadata['subcategory']}")

        if prefix_parts:
            return " | ".join(prefix_parts) + "\n" + text

        return text

    def _fixed_size_chunk(
        self,
        text: str,
        metadata: Dict[str, Any],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        固定大小分块（带重叠）

        策略：
        - 尽量在句子边界处分割
        - 相邻 chunk 之间保留重叠部分以保证上下文连续

        Args:
            text: 待分块文本
            metadata: 元数据

        Returns:
            (chunk_text, metadata) 列表
        """
        if len(text) <= self.chunk_size:
            return [(text, metadata)]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # 计算当前 chunk 的结束位置
            end = min(start + self.chunk_size, text_len)

            # 尝试在句子边界处结束（句号、问号、换行等）
            if end < text_len:
                boundary_chars = ".!?。！？\n"
                # 在 end 前后各 100 字符范围内寻找边界
                search_start = max(start + self.chunk_size // 2, end - 100)
                search_end = min(text_len, end + 100)

                best_boundary = end  # 默认使用硬边界
                for i in range(min(end, search_end) - 1, search_start - 1, -1):
                    if text[i] in boundary_chars:
                        best_boundary = i + 1
                        break

                end = best_boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append((chunk_text, dict(metadata)))

            # 移动起始位置，考虑重叠
            if end >= text_len:
                break

            start = end - self.chunk_overlap
            if start < 0:
                start = 0

            # 防止死循环：如果没有前进
            if start == end - self.chunk_size and end < text_len:
                start = end  # 强制前进

        return chunks

    def _semantic_chunk(
        self,
        text: str,
        metadata: Dict[str, Any],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        语义分块（预留接口）

        基于语义相似度将文本分割为语义连贯的片段。
        当前回退到固定大小分块，后续可集成语义分块模型。

        Args:
            text: 待分块文本
            metadata: 元数据

        Returns:
            (chunk_text, metadata) 列表
        """
        logger.debug("语义分块尚未实现，回退到固定大小分块")
        return self._fixed_size_chunk(text, metadata)
