#!/usr/bin/env python3
"""
计算核心评估指标（RCHR / AV / MTTR）
RCHR: Root Cause Hit Rate (根因命中率 = Top-1 准确率)
AV: Answer Validity (答案有效性 = 修复有效性平均分)
MTTR: Mean Time To Repair (平均修复时间估计)

用法:
    python calculate_metrics.py --results ../results/
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List


def load_result(result_path: str) -> Dict[str, Any]:
    """加载单个结果文件"""
    with open(result_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_results(results_dir: str) -> Dict[str, Dict[str, Any]]:
    """加载目录下所有结果文件"""
    results = {}
    for filename in os.listdir(results_dir):
        if filename.endswith("_results.json"):
            # 从文件名提取 baseline 名称
            baseline_name = filename.replace("_results.json", "")
            filepath = os.path.join(results_dir, filename)
            try:
                results[baseline_name] = load_result(filepath)
            except Exception as e:
                print(f"Warning: 无法加载 {filename}: {e}")
    return results


def compute_rchr(result: Dict[str, Any]) -> float:
    """
    计算 RCHR (Root Cause Hit Rate)
    即 Top-1 根因分类准确率
    """
    return result.get("top1_accuracy", 0.0)


def compute_av(result: Dict[str, Any]) -> float:
    """
    计算 AV (Answer Validity)
    即修复建议有效性的平均分
    基于 fix_steps 的质量评估
    """
    per_case = result.get("per_case_results", [])
    if not per_case:
        return 0.0

    # 如果有 fix_validity 字段直接使用
    total_validity = 0.0
    count = 0
    for case in per_case:
        if "fix_validity" in case:
            total_validity += case["fix_validity"]
            count += 1

    if count > 0:
        return total_validity / count

    # 否则基于 fix_steps 数量启发式估计
    total_score = 0.0
    for case in per_case:
        fix_steps = case.get("fix_steps", [])
        # 有 3-5 个步骤得分最高
        n = len(fix_steps)
        if 3 <= n <= 5:
            score = 0.8
        elif n >= 2:
            score = 0.6
        elif n >= 1:
            score = 0.4
        else:
            score = 0.0
        # 分类正确加分
        if case.get("is_correct"):
            score = min(score + 0.15, 1.0)
        total_score += score

    return total_score / len(per_case)


def compute_mttr(result: Dict[str, Any]) -> float:
    """
    计算 MTTR (Mean Time To Repair) 估计值（分钟）
    基于推理时间和修复步骤数估计
    """
    per_case = result.get("per_case_results", [])
    if not per_case:
        return 0.0

    total_mttr = 0.0
    for case in per_case:
        # 基础时间：推理时间（秒）转换为分钟，加上人工阅读时间
        inference_min = case.get("inference_time", 0) / 60.0
        num_steps = len(case.get("fix_steps", []))
        # 每步约 2 分钟执行时间
        step_time = num_steps * 2.0
        # 阅读和理解时间（约 3 分钟基础）
        read_time = 3.0

        mttr = inference_min + step_time + read_time
        total_mttr += mttr

    return total_mttr / len(per_case)


def print_summary(all_results: Dict[str, Dict[str, Any]]) -> None:
    """打印汇总表格"""
    print("=" * 80)
    print("核心指标汇总")
    print("=" * 80)

    header = f"{'系统':<25} {'RCHR':>10} {'AV':>10} {'MTTR(分)':>12} {'案例数':>10}"
    print(header)
    print("-" * len(header))

    # 按 RCHR 排序
    sorted_results = sorted(
        all_results.items(),
        key=lambda x: compute_rchr(x[1]),
        reverse=True,
    )

    for name, result in sorted_results:
        rchr = compute_rchr(result)
        av = compute_av(result)
        mttr = compute_mttr(result)
        total = result.get("total_cases", 0)

        line = (
            f"{name:<25} "
            f"{rchr:>9.2%} "
            f"{av:>9.2%} "
            f"{mttr:>11.2f} "
            f"{total:>10}"
        )
        print(line)

    print("=" * 80)
    print("RCHR: Root Cause Hit Rate (根因分类准确率)")
    print("AV: Answer Validity (修复建议有效性)")
    print("MTTR: Mean Time To Repair (估计平均修复时间)")
    print("=" * 80)


def save_summary(all_results: Dict[str, Dict[str, Any]], output_path: str) -> None:
    """保存汇总结果到 JSON"""
    summary = {}
    for name, result in all_results.items():
        summary[name] = {
            "rchr": compute_rchr(result),
            "av": compute_av(result),
            "mttr_minutes": compute_mttr(result),
            "total_cases": result.get("total_cases", 0),
            "top1_accuracy": result.get("top1_accuracy", 0),
            "avg_inference_time": result.get("avg_inference_time", 0),
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n汇总结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="计算核心评估指标 (RCHR/AV/MTTR)")
    parser.add_argument("--results", "-r", type=str, default="../results/",
                        help="评估结果目录")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="汇总结果输出路径（默认: results/metrics_summary.json）")
    args = parser.parse_args()

    if not os.path.isdir(args.results):
        print(f"错误: 结果目录不存在: {args.results}", file=sys.stderr)
        sys.exit(1)

    all_results = load_all_results(args.results)

    if not all_results:
        print(f"错误: 在 {args.results} 中未找到任何结果文件", file=sys.stderr)
        sys.exit(1)

    print(f"加载了 {len(all_results)} 个系统的评估结果\n")

    print_summary(all_results)

    output_path = args.output or os.path.join(args.results, "metrics_summary.json")
    save_summary(all_results, output_path)


if __name__ == "__main__":
    main()
