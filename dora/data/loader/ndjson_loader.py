"""
NDJSON 格式数据加载器
支持从 NDJSON（Newline Delimited JSON）文件加载数据记录
每行一个 JSON 对象，适合大规模数据处理
"""

import json
from typing import Any, Dict, List

from data.loader.base_loader import BaseDataLoader
from utils.logger import logger


class NdjsonLoader(BaseDataLoader):
    """
    NDJSON 数据加载器

    NDJSON 格式：每行一个独立的 JSON 对象
    优点：支持流式读取、易于并行处理、适合大数据集

    支持的记录格式：
    - {"Question_Body": "...", "Accepted_Answer_Body": "...", "category": "...", ...}
    """

    def __init__(self) -> None:
        """初始化 NDJSON 加载器"""
        pass

    def load(self, file_path: str) -> List[Dict[str, Any]]:
        """
        从 NDJSON 文件加载数据

        Args:
            file_path: NDJSON 文件路径

        Returns:
            记录列表
        """
        logger.info(f"开始加载 NDJSON 文件: {file_path}")

        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"第 {line_num} 行 JSON 解析失败: {str(e)}")
                    continue

        # 基本验证
        if records:
            sample = records[0]
            required_fields = ["Question_Body", "Accepted_Answer_Body"]
            missing = [f for f in required_fields if f not in sample]
            if missing:
                logger.warning(
                    f"记录缺少必要字段: {missing}。"
                    f"可用字段: {list(sample.keys())}"
                )

        logger.info(f"NDJSON 加载完成，共 {len(records)} 条记录")
        return records
