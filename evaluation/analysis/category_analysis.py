#!/usr/bin/env python3
"""
按故障大类分析各系统的表现
将故障案例按 category 分组，计算每个类别的准确率。

用法:
    python category_analysis.py --results ../results/ --output ../results/category_analysis.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
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
            baseline_name = filename.replace("_results.json", "")
            filepath = os.path.join(results_dir, filename)
            try:
                results[baseline_name] = load_result(filepath)
            except Exception as e:
                print(f"Warning: 无法加载 {filename}: {e}")
    return results


def analyze_by_category(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    按类别分析单个系统的表现

    Returns:
        {category: {"count": int, "correct": int, "accuracy": float}}
    """
    per_case = result.get("per_case_results", [])
    category_stats = defaultdict(lambda: {"count": 0, "correct": 0})

    for case in per_case:
        category = case.get("true_category", "unknown").lower()
        category_stats[category]["count"] += 1
        if case.get("is_correct"):
            category_stats[category]["correct"] += 1

    result = {}
    for cat, stats in sorted(category_stats.items()):
        stats["accuracy"] = stats["correct"] / stats["count"] if stats["count"] > 0 else 0.0
        result[cat] = stats

    return result


def print_category_analysis(all_results: Dict[str, Dict[str, Any]]) -> None:
    """打印类别分析表格"""
    # 收集所有类别
    all_categories = set()
    category_data = {}

    for name, result in all_results.items():
        cat_stats = analyze_by_category(result)
        category_data[name] = cat_stats
        all_categories.update(cat_stats.keys())

    all_categories = sorted(all_categories)

    print("=" * 90)
    print("按故障类别分析 - Top-1 准确率")
    print("=" * 90)

    # 表头
    header = f"{'系统':<25}"
    for cat in all_categories:
        header += f" {cat:>12}"
    header += f" {'总体':>10}"
    print(header)
    print("-" * len(header))

    # 每一行是一个系统
    sorted_systems = sorted(
        all_results.keys(),
        key=lambda n: all_results[n].get("top1_accuracy", 0),
        reverse=True,
    )

    for name in sorted_systems:
        line = f"{name:<25}"
        cat_stats = category_data[name]

        for cat in all_categories:
            if cat in cat_stats:
                acc = cat_stats[cat]["accuracy"]
                count = cat_stats[cat]["count"]
                line += f" {acc:>11.0%}({count})"
            else:
                line += f" {'N/A':>12}"

        overall = all_results[name].get("top1_accuracy", 0)
        line += f" {overall:>9.2%}"
        print(line)

    # 样本数行
    count_line = f"{'样本数':<25}"
    total = 0
    for cat in all_categories:
        # 取第一个系统的该类别样本数（假设所有系统用相同数据集）
        for name in all_results:
            if cat in category_data[name]:
                cnt = category_data[name][cat]["count"]
                count_line += f" {cnt:>12}"
                total += cnt
                break
        else:
            count_line += f" {'0':>12}"
    count_line += f" {total:>10}"
    print("-" * len(header))
    print(count_line)

    print("=" * 90)
    print(f"共 {len(all_categories)} 个故障类别")
    print("=" * 90)


def save_category_analysis(all_results: Dict[str, Dict[str, Any]], output_path: str) -> None:
    """保存类别分析结果"""
    category_data = {}
    all_categories = set()

    for name, result in all_results.items():
        cat_stats = analyze_by_category(result)
        category_data[name] = {k: dict(v) for k, v in cat_stats.items()}
        all_categories.update(cat_stats.keys())

    output_data = {
        "categories": sorted(all_categories),
        "systems": category_data,
        "overall": {
            name: {"top1_accuracy": result.get("top1_accuracy", 0)}
            for name, result in all_results.items()
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n类别分析结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="按故障类别分析")
    parser.add_argument("--results", "-r", type=str, default="../results/",
                        help="评估结果目录")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="分析结果输出路径")
    args = parser.parse_args()

    if not os.path.isdir(args.results):
        print(f"错误: 结果目录不存在: {args.results}", file=sys.stderr)
        sys.exit(1)

    all_results = load_all_results(args.results)

    if not all_results:
        print(f"错误: 在 {args.results} 中未找到任何结果文件", file=sys.stderr)
        sys.exit(1)

    print(f"加载了 {len(all_results)} 个系统的评估结果\n")

    print_category_analysis(all_results)

    output_path = args.output or os.path.join(args.results, "category_analysis.json")
    save_category_analysis(all_results, output_path)


if __name__ == "__main__":
    main()
