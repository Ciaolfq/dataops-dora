"""
标准 RAG 流水线（Baseline）
无查询重写、无重排，作为对比基线
"""

from typing import Any, Iterator

from core.retrieval.chroma_retrieval import ChromaRetrieval
from core.llm.openai_compatible import OpenAICompatibleLLM
from pipeline.base_pipeline import BasePipeline, PipelineResult
from config.config_loader import global_cfg
from utils.common import build_standard_rag_prompt
from utils.logger import logger


class StandardRagPipeline(BasePipeline):
    """
    标准 RAG 流水线（Baseline）

    流程：
    1. 原始查询直接检索
    2. 拼接 Prompt
    3. LLM 生成回答

    用途：作为 DORA 增强版的对比基线，用于评估各增强模块的效果
    """

    def __init__(self) -> None:
        """初始化标准 RAG 流水线"""
        vec_cfg = global_cfg.get("vector_store", {})
        llm_cfg = global_cfg.get("llm", {})

        self.default_top_n = vec_cfg.get("top_n", 5)

        self.retriever = ChromaRetrieval()
        self.llm = OpenAICompatibleLLM(llm_cfg)

        logger.info(
            "Standard Vanilla RAG Pipeline 初始化完成 "
            "(No rewrite, no rerank - Baseline)"
        )

    def run(self, query: str, **kwargs: Any) -> PipelineResult:
        """
        执行标准 RAG 流水线（非流式）

        Args:
            query: 用户查询
            **kwargs: 额外参数
                - top_n: 检索返回数量
                - filter: 元数据过滤条件

        Returns:
            PipelineResult 结果
        """
        top_n = kwargs.get("top_n", self.default_top_n)
        filter_condition = kwargs.get("filter", None)

        result = PipelineResult(raw_query=query)

        logger.info(f"[Standard RAG] 开始处理 | query='{query[:100]}...'")

        # Step 1: 直接检索
        logger.info("[Step 1] 向量检索（原始查询）")
        retrieved_docs = self.retriever.search(
            query=query,
            top_n=top_n,
            filter=filter_condition,
        )
        result.retrieved_docs = retrieved_docs
        result.reranked_docs = retrieved_docs  # 无重排，检索结果即最终文档
        logger.info(f"  检索到 {len(retrieved_docs)} 篇文档")

        if not retrieved_docs:
            logger.warning("  未检索到任何参考文档")
            result.answer = "未找到相关的故障诊断文档。"
            return result

        # Step 2: 构建 Prompt
        logger.info("[Step 2] 构建 Prompt")
        prompt = build_standard_rag_prompt(query, retrieved_docs)

        # Step 3: LLM 生成
        logger.info("[Step 3] LLM 生成回答")
        answer = self.llm.chat(prompt)
        result.answer = answer
        logger.info(f"  生成完成，回答长度: {len(answer)}")

        logger.info("[Standard RAG] 处理完成")
        return result

    def run_stream(self, query: str, **kwargs: Any) -> Iterator[str]:
        """
        流式执行标准 RAG 流水线

        Args:
            query: 用户查询
            **kwargs: 额外参数

        Yields:
            逐块生成的文本片段
        """
        top_n = kwargs.get("top_n", self.default_top_n)
        filter_condition = kwargs.get("filter", None)

        # Step 1: 检索
        retrieved_docs = self.retriever.search(
            query=query,
            top_n=top_n,
            filter=filter_condition,
        )

        if not retrieved_docs:
            yield "未找到相关的故障诊断文档。"
            return

        # Step 2-3: 构建 Prompt 并流式生成
        prompt = build_standard_rag_prompt(query, retrieved_docs)
        yield from self.llm.stream_chat(prompt)
