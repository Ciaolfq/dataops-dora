"""
向量库构建脚本
从数据文件加载文档，分块后构建 Chroma 向量数据库

用法：
    python -m data.vector_builder --data_path path/to/data.json
"""

import sys
import argparse
from pathlib import Path

# 将项目根目录加入模块搜索路径
root_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_path))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from data.loader.ndjson_loader import NdjsonLoader
from data.chunker import DocumentChunker
from config.config_loader import global_cfg
from utils.logger import logger


def build_vector_database(
    data_file_path: str = "data.json",
    chunk_strategy: str = "fixed",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    add_metadata_prefix: bool = True,
    reset: bool = False,
) -> None:
    """
    构建向量数据库

    Args:
        data_file_path: 数据文件路径（JSON/NDJSON 格式）
        chunk_strategy: 分块策略
        chunk_size: 分块大小（字符数）
        chunk_overlap: 分块重叠（字符数）
        add_metadata_prefix: 是否添加元数据前缀
        reset: 是否先清空已有向量库
    """
    vec_cfg = global_cfg.get("vector_store", {})

    persist_path = vec_cfg.get("persist_path", "./chroma_db")
    collection_name = vec_cfg.get("collection_name", "dora_fault_docs")
    embedding_model = vec_cfg.get("embedding_model", "all-MiniLM-L6-v2")

    logger.info(f"开始构建向量数据库 | collection={collection_name}")
    logger.info(f"数据文件: {data_file_path}")

    # 1. 初始化嵌入函数
    logger.info(f"加载嵌入模型: {embedding_model}")
    embed_fn = SentenceTransformerEmbeddingFunction(model_name=embedding_model)

    # 2. 初始化 Chroma 客户端
    client = chromadb.PersistentClient(path=persist_path)

    if reset:
        try:
            client.delete_collection(collection_name)
            logger.info(f"已删除现有集合: {collection_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
    )

    existing_count = collection.count()
    if existing_count > 0:
        logger.info(f"集合已存在，当前文档数: {existing_count}")

    # 3. 加载数据（支持 NDJSON 和 JSON）
    try:
        loader = NdjsonLoader()
        raw_records = loader.load(data_file_path)
    except Exception:
        # 回退到 JSON 格式
        import json
        logger.info("尝试以 JSON 格式加载...")
        with open(data_file_path, "r", encoding="utf-8") as f:
            raw_records = json.load(f)
        if isinstance(raw_records, dict) and "data" in raw_records:
            raw_records = raw_records["data"]

    if not raw_records:
        logger.error("未加载到任何数据记录，构建终止")
        return

    # 4. 文档分块
    chunker = DocumentChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=chunk_strategy,
        add_metadata_prefix=add_metadata_prefix,
    )

    all_chunks = chunker.chunk_records(raw_records)

    # 5. 准备写入数据
    docs = []
    ids = []
    metas = []

    for idx, (text, meta) in enumerate(all_chunks):
        doc_id = f"doc_{idx}"
        docs.append(text)
        ids.append(doc_id)
        metas.append(meta)

    logger.info(f"准备写入 {len(docs)} 个文档 chunk 到向量库")

    # 6. 批量写入
    batch_size = 100
    total_added = 0
    total_skipped = 0

    for i in range(0, len(docs), batch_size):
        batch_docs = docs[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        batch_metas = metas[i : i + batch_size]

        try:
            collection.add(
                documents=batch_docs,
                ids=batch_ids,
                metadatas=batch_metas,
            )
            total_added += len(batch_docs)
            logger.debug(f"已写入批次 {i // batch_size + 1} | {len(batch_docs)} 篇")
        except Exception as e:
            logger.error(f"批次写入失败 (起始索引 {i}): {str(e)}")
            # 尝试单条写入
            for j in range(len(batch_docs)):
                try:
                    collection.add(
                        documents=[batch_docs[j]],
                        ids=[batch_ids[j]],
                        metadatas=[batch_metas[j]],
                    )
                    total_added += 1
                except Exception as e2:
                    total_skipped += 1
                    logger.warning(f"跳过文档 {batch_ids[j]}: {str(e2)[:100]}")

    # 7. 总结
    final_count = collection.count()
    logger.info("=" * 50)
    logger.info(f"向量库构建完成")
    logger.info(f"  - 原始记录数: {len(raw_records)}")
    logger.info(f"  - 分块后 chunk 数: {len(all_chunks)}")
    logger.info(f"  - 成功写入: {total_added}")
    logger.info(f"  - 跳过失败: {total_skipped}")
    logger.info(f"  - 集合总文档数: {final_count}")
    logger.info(f"  - 存储路径: {persist_path}")
    logger.info("=" * 50)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="DORA 向量库构建工具")
    parser.add_argument(
        "--data_path",
        type=str,
        default="data/knowledge_base.json",
        help="数据文件路径（JSON/NDJSON 格式）",
    )
    parser.add_argument(
        "--chunk_strategy",
        type=str,
        default="fixed",
        choices=["fixed", "semantic", "whole"],
        help="分块策略",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=1000,
        help="分块大小（字符数）",
    )
    parser.add_argument(
        "--chunk_overlap",
        type=int,
        default=200,
        help="分块重叠（字符数）",
    )
    parser.add_argument(
        "--no_metadata_prefix",
        action="store_true",
        help="不添加分类元数据前缀",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先清空已有向量库再构建",
    )

    args = parser.parse_args()

    build_vector_database(
        data_file_path=args.data_path,
        chunk_strategy=args.chunk_strategy,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        add_metadata_prefix=not args.no_metadata_prefix,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()
