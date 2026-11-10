"""
Chroma 向量检索实现
支持元数据过滤、多路召回、混合检索预留接口
"""

from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from core.retrieval.base import BaseRetrieval, RetrievedDocument
from config.config_loader import global_cfg
from utils.logger import logger


class ChromaRetrieval(BaseRetrieval):
    """
    Chroma 向量数据库检索器

    特性：
    - 基于 SentenceTransformer 的向量嵌入
    - 元数据过滤（category, subcategory 等）
    - 多路召回（多查询检索 + 去重合并）
    - 混合检索预留接口（待扩展 BM25 等）
    """

    def __init__(self) -> None:
        """初始化 Chroma 检索器"""
        vec_cfg = global_cfg.get("vector_store", {})

        self.persist_path = vec_cfg.get("persist_path", "./chroma_db")
        self.collection_name = vec_cfg.get("collection_name", "dora_fault_docs")
        self.default_topn = vec_cfg.get("top_n", 10)
        self.embedding_model = vec_cfg.get("embedding_model", "all-MiniLM-L6-v2")

        # 初始化嵌入函数
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model
        )

        # 初始化 Chroma 客户端
        self._client = chromadb.PersistentClient(path=self.persist_path)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_fn,
        )

        doc_count = self._collection.count()
        logger.info(
            f"ChromaRetrieval 初始化完成 | "
            f"collection={self.collection_name} | "
            f"docs={doc_count} | "
            f"embedding_model={self.embedding_model}"
        )

    def search(
        self,
        query: str,
        top_n: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """
        单查询向量检索

        Args:
            query: 查询文本
            top_n: 返回结果数量
            filter: 元数据过滤条件，例如：
                - {"category": "dbt_run_error"}
                - {"category": {"$in": ["dbt_run_error", "dbt_test_error"]}}

        Returns:
            检索到的文档列表，按相似度降序排列
        """
        top = top_n if top_n else self.default_topn

        query_params = {
            "query_texts": [query],
            "n_results": top,
            "include": ["documents", "metadatas", "distances"],
        }

        if filter:
            query_params["where"] = filter

        try:
            res = self._collection.query(**query_params)
        except Exception as e:
            logger.error(f"Chroma 检索失败: {str(e)}")
            return []

        documents = res["documents"][0] if res["documents"] else []
        metadatas = res["metadatas"][0] if res["metadatas"] else []
        distances = res["distances"][0] if res["distances"] else []
        ids = res["ids"][0] if res.get("ids") else []

        results = []
        for i in range(len(documents)):
            # Chroma 返回的是距离，转换为相似度分数（距离越小越相似）
            distance = distances[i] if i < len(distances) else None
            score = 1.0 / (1.0 + distance) if distance is not None else None

            doc = RetrievedDocument(
                content=documents[i],
                metadata=metadatas[i] if i < len(metadatas) else {},
                score=score,
                doc_id=ids[i] if i < len(ids) else f"doc_{i}",
            )
            results.append(doc)

        logger.debug(
            f"Chroma 检索完成 | query='{query[:50]}...' | "
            f"results={len(results)} | filter={filter}"
        )

        return results

    def search_multi(
        self,
        queries: List[str],
        top_n: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """
        多查询检索（多路召回），自动去重合并

        策略：
        1. 对每个查询分别检索
        2. 基于 doc_id 去重
        3. 保留每个文档的最高得分
        4. 按最终得分排序

        Args:
            queries: 查询文本列表
            top_n: 每个查询返回的结果数量
            filter: 元数据过滤条件

        Returns:
            合并去重后的文档列表，按得分降序排列
        """
        if not queries:
            return []

        per_query_top = top_n if top_n else self.default_topn
        all_docs: Dict[str, RetrievedDocument] = {}

        for idx, query in enumerate(queries):
            docs = self.search(query, top_n=per_query_top, filter=filter)
            logger.debug(f"多路召回 - 查询 {idx + 1}/{len(queries)}: {len(docs)} 篇文档")

            for doc in docs:
                key = doc.doc_id or doc.content[:100]
                if key in all_docs:
                    # 保留更高的得分
                    if doc.score is not None and (
                        all_docs[key].score is None or doc.score > all_docs[key].score
                    ):
                        all_docs[key].score = doc.score
                else:
                    all_docs[key] = doc

        # 按得分排序
        results = sorted(
            all_docs.values(),
            key=lambda d: d.score if d.score is not None else -1,
            reverse=True,
        )

        logger.info(
            f"多路召回完成 | 查询数={len(queries)} | "
            f"去重后={len(results)}"
        )

        return results

    def count(self) -> int:
        """返回向量库中文档总数"""
        return self._collection.count()

    def add_documents(
        self,
        documents: List[str],
        ids: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        向向量库中添加文档

        Args:
            documents: 文档内容列表
            ids: 文档 ID 列表
            metadatas: 元数据列表
        """
        self._collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas or [{} for _ in documents],
        )
        logger.info(f"向向量库添加了 {len(documents)} 篇文档")

    def delete_collection(self) -> None:
        """删除当前集合（谨慎使用）"""
        self._client.delete_collection(self.collection_name)
        logger.warning(f"已删除集合: {self.collection_name}")
        # 重新创建空集合
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_fn,
        )
