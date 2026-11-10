"""
DORA 增强版完整流水线

流程：
1. 查询重写（错误感知 + 多查询扩展，多路召回）
2. 多路召回（多查询检索 + 去重合并）
3. Cross-Encoder 精排
4. Prompt 构建（带引用来源）
5. LLM 生成（结构化输出：根因、分类、置信度、修复步骤、引用）
"""

import json
import re
from typing import Any, Dict, Iterator, List, Optional

from core.query_rewrite.error_aware import ErrorAwareRewrite
from core.retrieval.chroma_retrieval import ChromaRetrieval
from core.rerank.cross_encoder_rerank import CrossEncoderRerank
from core.llm.openai_compatible import OpenAICompatibleLLM
from pipeline.base_pipeline import BasePipeline, PipelineResult
from config.config_loader import global_cfg
from utils.common import build_dora_prompt, build_dora_system_prompt
from utils.logger import logger


class DORAPipeline(BasePipeline):
    """
    DORA 增强版完整流水线

    增强特性：
    - 错误感知多查询扩展（多路召回）
    - Cross-Encoder 精排
    - 元数据过滤检索（可选）
    - 结构化输出解析（root_cause, category, confidence, fix_steps, references）
    - 引用来源标注
    """

    def __init__(self) -> None:
        """初始化 DORA 流水线各组件"""
        rewrite_cfg = global_cfg.get("query_rewrite", {})
        rerank_cfg = global_cfg.get("rerank", {})
        vec_cfg = global_cfg.get("vector_store", {})
        llm_cfg = global_cfg.get("llm", {})

        self.rewrite_enabled = rewrite_cfg.get("enabled", True)
        self.rerank_enabled = rerank_cfg.get("enabled", True)
        self.retrieval_top_n = vec_cfg.get("top_n", 10)
        self.rerank_top_n = rerank_cfg.get("top_n_after_rerank", 5)

        # 初始化组件
        if self.rewrite_enabled:
            self.rewriter = ErrorAwareRewrite()
        else:
            self.rewriter = None

        self.retriever = ChromaRetrieval()

        if self.rerank_enabled:
            self.reranker = CrossEncoderRerank()
        else:
            self.reranker = None

        self.llm = OpenAICompatibleLLM(llm_cfg)

        logger.info(
            f"DORA Pipeline 初始化完成 | "
            f"rewrite={'ON' if self.rewrite_enabled else 'OFF'} | "
            f"rerank={'ON' if self.rerank_enabled else 'OFF'} | "
            f"retrieval_top_n={self.retrieval_top_n} | "
            f"rerank_top_n={self.rerank_top_n}"
        )

    def run(self, query: str, **kwargs: Any) -> PipelineResult:
        """
        执行完整 DORA 流水线（非流式）

        Args:
            query: 用户查询
            **kwargs: 额外参数
                - filter: 元数据过滤条件（dict）
                - use_rerank: 是否使用重排（覆盖配置）
                - use_rewrite: 是否使用查询重写（覆盖配置）

        Returns:
            PipelineResult 结构化结果
        """
        use_rewrite = kwargs.get("use_rewrite", self.rewrite_enabled)
        use_rerank = kwargs.get("use_rerank", self.rerank_enabled)
        filter_condition = kwargs.get("filter", None)

        result = PipelineResult(raw_query=query)

        logger.info(f"[DORA Pipeline] 开始处理 | query='{query[:100]}...'")

        # Step 1: 查询重写（多查询扩展）
        if use_rewrite and self.rewriter:
            logger.info("[Step 1] 查询重写 - 生成扩展查询")
            expanded_queries = self.rewriter.rewrite_multi(query)
            result.rewritten_queries = expanded_queries
            logger.info(f"  生成 {len(expanded_queries)} 个查询（含原始）")
        else:
            logger.info("[Step 1] 跳过查询重写")
            expanded_queries = [query]

        # Step 2: 多路召回
        logger.info("[Step 2] 多路召回 - 向量检索")
        if len(expanded_queries) > 1:
            # 多查询检索 + 去重
            retrieved_docs = self.retriever.search_multi(
                queries=expanded_queries,
                top_n=self.retrieval_top_n,
                filter=filter_condition,
            )
        else:
            # 单查询检索
            retrieved_docs = self.retriever.search(
                query=expanded_queries[0],
                top_n=self.retrieval_top_n,
                filter=filter_condition,
            )

        result.retrieved_docs = retrieved_docs
        logger.info(f"  检索到 {len(retrieved_docs)} 篇文档")

        if not retrieved_docs:
            logger.warning("  未检索到任何参考文档")
            result.answer = "未找到相关的故障诊断文档。请尝试换一种表述方式，或检查错误信息是否完整。"
            return result

        # Step 3: Cross-Encoder 重排
        if use_rerank and self.reranker:
            logger.info("[Step 3] Cross-Encoder 精排")
            reranked_docs = self.reranker.rerank(
                query=query,  # 使用原始查询进行重排
                documents=retrieved_docs,
                top_n=self.rerank_top_n,
            )
            result.reranked_docs = reranked_docs
            final_docs = reranked_docs
            logger.info(f"  重排后保留 {len(reranked_docs)} 篇文档")
        else:
            logger.info("[Step 3] 跳过重排")
            final_docs = retrieved_docs[: self.rerank_top_n]
            result.reranked_docs = final_docs

        # Step 4: 构建 Prompt
        logger.info("[Step 4] 构建 Prompt")
        system_prompt = build_dora_system_prompt()
        user_prompt = build_dora_prompt(query, final_docs)

        # Step 5: LLM 生成
        logger.info("[Step 5] LLM 生成回答")
        raw_answer = self.llm.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        result.answer = raw_answer
        logger.info(f"  生成完成，回答长度: {len(raw_answer)}")

        # Step 6: 解析结构化输出
        logger.info("[Step 6] 解析结构化输出")
        structured = self._parse_structured_output(raw_answer)
        result.root_cause = structured.get("root_cause", "")
        result.category = structured.get("category", "")
        result.confidence = structured.get("confidence", 0.0)
        result.fix_steps = structured.get("fix_steps", [])
        result.references = self._build_references(final_docs)

        logger.info("[DORA Pipeline] 处理完成")
        return result

    def run_stream(self, query: str, **kwargs: Any) -> Iterator[str]:
        """
        流式执行 DORA 流水线

        Args:
            query: 用户查询
            **kwargs: 额外参数

        Yields:
            逐块生成的文本片段
        """
        use_rewrite = kwargs.get("use_rewrite", self.rewrite_enabled)
        use_rerank = kwargs.get("use_rerank", self.rerank_enabled)
        filter_condition = kwargs.get("filter", None)

        # Step 1: 查询重写
        if use_rewrite and self.rewriter:
            expanded_queries = self.rewriter.rewrite_multi(query)
        else:
            expanded_queries = [query]

        # Step 2: 多路召回
        if len(expanded_queries) > 1:
            retrieved_docs = self.retriever.search_multi(
                queries=expanded_queries,
                top_n=self.retrieval_top_n,
                filter=filter_condition,
            )
        else:
            retrieved_docs = self.retriever.search(
                query=expanded_queries[0],
                top_n=self.retrieval_top_n,
                filter=filter_condition,
            )

        if not retrieved_docs:
            yield "未找到相关的故障诊断文档。请尝试换一种表述方式，或检查错误信息是否完整。"
            return

        # Step 3: 重排
        if use_rerank and self.reranker:
            final_docs = self.reranker.rerank(
                query=query,
                documents=retrieved_docs,
                top_n=self.rerank_top_n,
            )
        else:
            final_docs = retrieved_docs[: self.rerank_top_n]

        # Step 4-5: 构建 Prompt 并流式生成
        system_prompt = build_dora_system_prompt()
        user_prompt = build_dora_prompt(query, final_docs)

        yield from self.llm.stream_chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

    def _parse_structured_output(self, answer: str) -> Dict[str, Any]:
        """
        从 LLM 回答中解析结构化信息

        尝试从回答中提取：
        - root_cause: 根因分析
        - category: 故障分类
        - confidence: 置信度
        - fix_steps: 修复步骤列表

        Args:
            answer: LLM 原始回答

        Returns:
            结构化信息字典
        """
        result = {
            "root_cause": "",
            "category": "",
            "confidence": 0.0,
            "fix_steps": [],
        }

        # 尝试从 JSON 代码块中解析
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", answer, re.DOTALL | re.IGNORECASE)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    result["root_cause"] = data.get("root_cause", data.get("rootCause", ""))
                    result["category"] = data.get("category", "")
                    result["confidence"] = float(data.get("confidence", 0))
                    steps = data.get("fix_steps", data.get("fixSteps", []))
                    if isinstance(steps, list):
                        result["fix_steps"] = [str(s) for s in steps]
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        # 尝试基于正则的启发式提取
        # 根因
        root_cause_patterns = [
            r"(?:根因|root cause|Root Cause)[:：]\s*(.+?)(?:\n\n|\n[A-Z]|$)",
            r"(?:根本原因)[:：]\s*(.+?)(?:\n\n|\n[A-Z]|$)",
        ]
        for pattern in root_cause_patterns:
            match = re.search(pattern, answer, re.IGNORECASE | re.DOTALL)
            if match:
                result["root_cause"] = match.group(1).strip()
                break

        # 分类
        category_patterns = [
            r"(?:分类|category|Category)[:：]\s*(.+?)(?:\n|$)",
            r"(?:故障类型|错误类型)[:：]\s*(.+?)(?:\n|$)",
        ]
        for pattern in category_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                result["category"] = match.group(1).strip()
                break

        # 置信度
        conf_patterns = [
            r"(?:置信度|confidence|Confidence)[:：]\s*(\d+(?:\.\d+)?)\s*%?",
        ]
        for pattern in conf_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                try:
                    conf = float(match.group(1))
                    if conf > 1:
                        conf = conf / 100.0
                    result["confidence"] = round(conf, 4)
                except ValueError:
                    pass
                break

        # 修复步骤
        steps_match = re.search(
            r"(?:修复步骤|解决方案|fix steps|Fix Steps|Solution)[:：]\s*\n((?:\s*[\d\-\*•]+\s*.+?\n)+)",
            answer,
            re.IGNORECASE | re.DOTALL,
        )
        if steps_match:
            steps_text = steps_match.group(1)
            steps = re.findall(r"^\s*[\d\-\*•]+\s*(.+?)\s*$", steps_text, re.MULTILINE)
            result["fix_steps"] = [s.strip() for s in steps if s.strip()]

        return result

    def _build_references(self, docs: List) -> List[Dict[str, Any]]:
        """
        从检索文档构建引用来源列表

        Args:
            docs: 文档列表

        Returns:
            引用来源列表
        """
        references = []
        for i, doc in enumerate(docs, 1):
            ref = {
                "index": i,
                "doc_id": doc.doc_id,
                "score": round(doc.score, 4) if doc.score else None,
                "category": doc.metadata.get("category", ""),
                "subcategory": doc.metadata.get("subcategory", ""),
                "title": doc.metadata.get("title", ""),
                "snippet": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
            }
            references.append(ref)
        return references
