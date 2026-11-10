#!/usr/bin/env python3
"""
DORA (DataOps Retrieval Assistant) - 主入口

DORA 是一个面向 DataOps 场景的智能故障诊断系统，
结合错误感知查询重写、多路召回和 Cross-Encoder 精排技术，
实现高效、准确的 dbt / Airflow / PostgreSQL 故障诊断。

用法：
    # 交互式诊断
    python main.py

    # 单次查询
    python main.py --query "dbt run 报错：relation does not exist"

    # 构建向量库
    python main.py --build --data_path ./data/knowledge_base.json
"""

import sys
import argparse
from pathlib import Path

# 将项目根目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.logger import logger
from config.config_loader import global_cfg


def run_interactive() -> None:
    """交互式诊断模式"""
    from pipeline.dora_pipeline import DORAPipeline

    print("=" * 60)
    print("DORA - DataOps Retrieval Assistant")
    print("输入故障描述或错误日志进行诊断")
    print("输入 'quit' 或 'exit' 退出")
    print("=" * 60)

    pipeline = DORAPipeline()

    while True:
        try:
            query = input("\n请输入故障描述: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        try:
            result = pipeline.run(query)

            print(f"\n{'='*60}")
            print(f"诊断结果")
            print(f"{'='*60}")
            print(f"\n根因: {result.root_cause}")
            print(f"分类: {result.category}")
            print(f"置信度: {result.confidence:.1%}")
            print(f"\n修复步骤:")
            for i, step in enumerate(result.fix_steps, 1):
                print(f"  {i}. {step}")
            print(f"\n引用来源 ({len(result.references)} 篇):")
            for ref in result.references:
                print(f"  [{ref['index']}] {ref['category']} - {ref['snippet'][:60]}...")

        except Exception as e:
            logger.error(f"诊断失败: {str(e)}")
            print(f"诊断失败: {str(e)}")


def run_single_query(query: str) -> None:
    """单次查询模式"""
    from pipeline.dora_pipeline import DORAPipeline

    pipeline = DORAPipeline()
    result = pipeline.run(query)

    print(f"根因: {result.root_cause}")
    print(f"分类: {result.category}")
    print(f"置信度: {result.confidence:.1%}")
    print(f"修复步骤:")
    for i, step in enumerate(result.fix_steps, 1):
        print(f"  {i}. {step}")


def build_vector_db(data_path: str) -> None:
    """构建向量数据库"""
    from data.vector_builder import build_vector_database

    build_vector_database(data_file_path=data_path, reset=True)


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="DORA - DataOps Retrieval Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="单次查询模式：指定故障描述文本",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="构建向量数据库",
    )
    parser.add_argument(
        "--data_path",
        type=str,
        default="./data/knowledge_base.json",
        help="知识库数据文件路径（用于构建向量库）",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径（默认使用 config/settings.yaml）",
    )

    args = parser.parse_args()

    # 设置配置文件路径
    if args.config:
        import os
        os.environ["DORA_CONFIG_PATH"] = args.config

    logger.info("DORA 系统启动")

    if args.build:
        build_vector_db(args.data_path)
        return 0

    if args.query:
        run_single_query(args.query)
        return 0

    # 默认进入交互式模式
    run_interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
