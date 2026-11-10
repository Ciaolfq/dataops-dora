"""
Cross-Encoder 重排器
使用 sentence-transformers 的 CrossEncoder 进行精确的语义相关性重排
"""

from typing import List, Optional

from core.rerank.base import BaseRerank
from core.retrieval.base import RetrievedDocument
from config.config_loader import global_cfg
from utils.logger import logger


class CrossEncoderRerank(BaseRerank):
    """
    Cross-Encoder 重排器

    Cross-Encoder 与 Bi-Encoder（向量检索使用）的区别：
    - Bi-Encoder: 分别对 query 和 document 编码，计算余弦相似度（快、精度一般）
    - Cross-Encoder: 将 query 和 document 拼接后一起输入模型，直接输出相关性分数（慢、精度高）

    使用场景：
    先用向量检索快速召回 top-k（如 50 篇），再用 Cross-Encoder 精排到 top-n（如 5 篇）
    """

    def __init__(self) -> None:
        """初始化 Cross-Encoder 重排器"""
        rerank_cfg = global_cfg.get("rerank", {})

        self.enabled = rerank_cfg.get("enabled", True)
        self.model_name = rerank_cfg.get(
            "model_name", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.default_top_n = rerank_cfg.get("top_n_after_rerank", 5)
        self.batch_size = rerank_cfg.get("batch_size", 32)

        self._model = None

        if self.enabled:
            self._load_model()
        else:
            logger.info("CrossEncoderRerank 已禁用")

    def _load_model(self) -> None:
        """延迟加载 CrossEncoder 模型"""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"正在加载 CrossEncoder 模型: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            logger.info("CrossEncoder 模型加载完成")
        except ImportError as e:
            logger.error(
                f"sentence-transformers 未安装，CrossEncoder 重排不可用: {str(e)}"
            )
            self.enabled = False
            self._model = None
        except Exception as e:
            logger.error(f"CrossEncoder 模型加载失败: {str(e)}")
            self.enabled = False
            self._model = None

    def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_n: Optional[int] = None,
    ) -> List[RetrievedDocument]:
        """
        使用 Cross-Encoder 对文档进行重排序

        Args:
            query: 查询文本
            documents: 待重排的文档列表
            top_n: 重排后保留的文档数量，None 则使用配置中的默认值

        Returns:
            重排后的文档列表，按 Cross-Encoder 相关性分数降序排列
        """
        if not documents:
            return []

        top = top_n if top_n is not None else self.default_top_n

        # 如果重排被禁用或模型未加载，直接返回原结果（截断到 top_n）
        if not self.enabled or self._model is None:
            logger.debug("CrossEncoder 重排未启用，返回原始排序结果")
            return documents[:top]

        # 构造 (query, document) 对
        pairs = [[query, doc.content] for doc in documents]

        logger.debug(
            f"开始 CrossEncoder 重排 | query='{query[:50]}...' | "
            f"docs={len(documents)} | top_n={top}"
        )

        try:
            # 批量预测相关性分数
            scores = self._model.predict(pairs, batch_size=self.batch_size)

            # 将分数赋给文档并排序
            for i, doc in enumerate(documents):
                doc.score = float(scores[i])

            # 按分数降序排序
            reranked = sorted(documents, key=lambda d: d.score, reverse=True)

            # 截取 top_n
            result = reranked[:top]

            logger.debug(
                f"CrossEncoder 重排完成 | 保留 {len(result)}/{len(documents)} 篇 | "
                f"最高得分: {result[0].score:.4f if result else 'N/A'}"
            )

            return result

        except Exception as e:
            logger.error(f"CrossEncoder 重排失败，返回原始排序: {str(e)}")
            return documents[:top]
