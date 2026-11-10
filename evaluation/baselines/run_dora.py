#!/usr/bin/env python3
"""
Baseline 6: DORA (Our Method)
完整 DORA 流水线：错误感知查询重写 + 多路召回 + Cross-Encoder 重排 + 结构化输出生成。

这是论文提出的目标系统，用于与其他 Baseline 对比验证各模块的有效性。

用法:
    python run_dora.py --dataset ../data/fault_dataset_100.json --output ../results/

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

# 添加 dora 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "dora"))

from pipeline.dora_pipeline import DORAPipeline
from pipeline.base_pipeline import PipelineResult


def diagnose(error_log: str, pipeline: DORAPipeline) -> Dict[str, Any]:
    """使用 DORA 完整流水线进行诊断"""

    result: PipelineResult = pipeline.run(error_log)

    return {
        "root_cause": result.root_cause,
        "category": result.category,
        "confidence": result.confidence,
        "fix_steps": result.fix_steps,
        "raw_answer": result.answer,
        "method": "dora",
        "rewritten_queries": result.rewritten_queries,
        "retrieved_count": len(result.retrieved_docs),
        "reranked_count": len(result.reranked_docs),
        "references": [
            {
                "doc_id": ref.get("doc_id", ""),
                "category": ref.get("category", ""),
                "score": ref.get("score", 0),
            }
            for ref in result.references
        ],
    }


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str,
             use_rewrite: bool = True, use_rerank: bool = True) -> Dict[str, Any]:
    """运行评估"""
    os.makedirs(output_dir, exist_ok=True)

    pipeline = DORAPipeline()

    per_case_results = []
    correct = 0
    total_time = 0.0

    for idx, case in enumerate(dataset, 1):
        fault_id = case["fault_id"]
        error_log = case["error_log"]

        print(f"  [{idx}/{len(dataset)}] {fault_id}...", end=" ", flush=True)

        start_time = time.time()
        try:
            prediction = diagnose(error_log, pipeline)
        except Exception as e:
            print(f"ERROR: {str(e)[:80]}")
            prediction = {
                "root_cause": f"Error: {str(e)}",
                "category": "error",
                "confidence": 0.0,
                "fix_steps": [],
                "method": "dora",
            }
        elapsed = time.time() - start_time
        total_time += elapsed

        is_correct = prediction["category"].lower() == case["category"].lower()
        if is_correct:
            correct += 1
            print("OK")
        else:
            print(f"WRONG (pred={prediction['category']}, true={case['category']})")

        per_case_results.append({
            "fault_id": fault_id,
            "predicted_category": prediction["category"],
            "true_category": case["category"],
            "predicted_root_cause": prediction["root_cause"],
            "true_root_cause": case["root_cause"],
            "is_correct": is_correct,
            "confidence": prediction["confidence"],
            "inference_time": round(elapsed, 4),
            "fix_steps": prediction["fix_steps"],
            "rewritten_queries": prediction.get("rewritten_queries", []),
            "retrieved_count": prediction.get("retrieved_count", 0),
            "reranked_count": prediction.get("reranked_count", 0),
        })

    accuracy = correct / len(dataset) if dataset else 0.0

    result = {
        "baseline": "dora",
        "total_cases": len(dataset),
        "rewrite_enabled": use_rewrite,
        "rerank_enabled": use_rerank,
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    output_path = os.path.join(output_dir, "dora_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDORA 评估完成:")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="DORA (Our Method) 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    parser.add_argument("--no-rewrite", action="store_true",
                        help="禁用查询重写模块")
    parser.add_argument("--no-rerank", action="store_true",
                        help="禁用重排模块")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: DORA (Our Method)")
    print(f"数据集: {args.dataset}")
    print(f"rewrite={'OFF' if args.no_rewrite else 'ON'}, rerank={'OFF' if args.no_rerank else 'ON'}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(
        dataset,
        args.output,
        use_rewrite=not args.no_rewrite,
        use_rerank=not args.no_rerank,
    )


if __name__ == "__main__":
    main()
