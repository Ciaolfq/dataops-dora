#!/usr/bin/env python3
"""
消融实验分析
分析各模块（查询重写、重排）对 DORA 系统性能的贡献。

用法:
    # 完整 DORA
    python run_dora.py --dataset ../data/fault_dataset_100.json --output ../results/ablation_full/

    # 移除查询重写
    python run_dora.py --dataset ../data/fault_dataset_100.json --output ../results/ablation_no_rewrite/ --no-rewrite

    # 移除重排
    python run_dora.py --dataset ../data/fault_dataset_100.json --output ../results/ablation_no_rerank/ --no-rerank

    # 分析
    python ablation_analysis.py --full ../results/ablation_full/ --no-rewrite ../results/ablation_no_rewrite/ --no-rerank ../results/ablation_no_rerank/
"""

import argparse
import json
import os
import sys
from typing import Any, Dict


def load_dora_result(results_dir: str) -> Dict[str, Any]:
    """从目录加载 DORA 结果"""
    dora_path = os.path.join(results_dir, "dora_results.json")
    if not os.path.exists(dora_path):
        # 尝试查找任何结果文件
        for f in os.listdir(results_dir):
            if f.endswith("_results.json"):
                dora_path = os.path.join(results_dir, f)
                break

    if not os.path.exists(dora_path):
        raise FileNotFoundError(f"在 {results_dir} 中未找到结果文件")

    with open(dora_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_improvement(base_acc: float, ablation_acc: float) -> Dict[str, float]:
    """计算消融模块带来的性能下降"""
    drop_abs = base_acc - ablation_acc
    drop_rel = (drop_abs / base_acc * 100) if base_acc > 0 else 0.0
    return {
        "base_accuracy": base_acc,
        "ablation_accuracy": ablation_acc,
        "absolute_drop": drop_abs,
        "relative_drop_percent": drop_rel,
    }


def print_ablation_analysis(full_result: Dict[str, Any],
                            no_rewrite_result: Dict[str, Any],
                            no_rerank_result: Dict[str, Any]) -> None:
    """打印消融实验分析表格"""
    full_acc = full_result.get("top1_accuracy", 0)
    no_rewrite_acc = no_rewrite_result.get("top1_accuracy", 0)
    no_rerank_acc = no_rerank_result.get("top1_accuracy", 0)

    print("=" * 70)
    print("消融实验分析")
    print("=" * 70)

    # 方法列表
    variants = [
        ("DORA (Full)", full_acc, "完整系统"),
        ("w/o Query Rewrite", no_rewrite_acc, "移除错误感知查询重写"),
        ("w/o Cross-Encoder Rerank", no_rerank_acc, "移除 Cross-Encoder 重排"),
    ]

    header = f"{'系统变体':<25} {'Top-1 准确率':>14} {'下降':>10} {'说明':<25}"
    print(header)
    print("-" * len(header))

    for name, acc, desc in variants:
        if name == "DORA (Full)":
            drop_str = "-"
        else:
            drop = full_acc - acc
            drop_rel = (drop / full_acc * 100) if full_acc > 0 else 0
            drop_str = f"-{drop_rel:.1f}%"

        line = f"{name:<25} {acc:>13.2%} {drop_str:>10} {desc:<25}"
        print(line)

    print("-" * len(header))

    # 各模块贡献
    rewrite_contribution = full_acc - no_rewrite_acc
    rerank_contribution = full_acc - no_rerank_acc
    total_contribution = rewrite_contribution + rerank_contribution

    if total_contribution > 0:
        rewrite_ratio = rewrite_contribution / total_contribution * 100
        rerank_ratio = rerank_contribution / total_contribution * 100
    else:
        rewrite_ratio = 0
        rerank_ratio = 0

    print()
    print("模块贡献分析：")
    print(f"  查询重写模块贡献: {rewrite_contribution:+.2%} (占增益 {rewrite_ratio:.1f}%)")
    print(f"  Cross-Encoder 重排贡献: {rerank_contribution:+.2%} (占增益 {rerank_ratio:.1f}%)")

    print("=" * 70)


def save_ablation_analysis(full_result: Dict[str, Any],
                           no_rewrite_result: Dict[str, Any],
                           no_rerank_result: Dict[str, Any],
                           output_path: str) -> None:
    """保存消融实验分析结果"""
    full_acc = full_result.get("top1_accuracy", 0)
    no_rewrite_acc = no_rewrite_result.get("top1_accuracy", 0)
    no_rerank_acc = no_rerank_result.get("top1_accuracy", 0)

    rewrite_contribution = full_acc - no_rewrite_acc
    rerank_contribution = full_acc - no_rerank_acc

    analysis = {
        "full_dora": {
            "top1_accuracy": full_acc,
            "avg_inference_time": full_result.get("avg_inference_time", 0),
        },
        "without_rewrite": {
            "top1_accuracy": no_rewrite_acc,
            "avg_inference_time": no_rewrite_result.get("avg_inference_time", 0),
            "accuracy_drop_abs": rewrite_contribution,
            "accuracy_drop_rel": rewrite_contribution / full_acc if full_acc > 0 else 0,
        },
        "without_rerank": {
            "top1_accuracy": no_rerank_acc,
            "avg_inference_time": no_rerank_result.get("avg_inference_time", 0),
            "accuracy_drop_abs": rerank_contribution,
            "accuracy_drop_rel": rerank_contribution / full_acc if full_acc > 0 else 0,
        },
        "module_contribution": {
            "query_rewrite": rewrite_contribution,
            "cross_encoder_rerank": rerank_contribution,
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"\n消融实验分析结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="消融实验分析")
    parser.add_argument("--full", type=str, required=True,
                        help="完整 DORA 结果目录")
    parser.add_argument("--no-rewrite", type=str, required=True,
                        help="移除查询重写的结果目录")
    parser.add_argument("--no-rerank", type=str, required=True,
                        help="移除重排的结果目录")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="分析结果输出路径")
    args = parser.parse_args()

    try:
        full_result = load_dora_result(args.full)
        no_rewrite_result = load_dora_result(args.no_rewrite)
        no_rerank_result = load_dora_result(args.no_rerank)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    print_ablation_analysis(full_result, no_rewrite_result, no_rerank_result)

    output_path = args.output or os.path.join(os.path.dirname(args.full.rstrip("/")), "ablation_analysis.json")
    save_ablation_analysis(full_result, no_rewrite_result, no_rerank_result, output_path)


if __name__ == "__main__":
    main()
