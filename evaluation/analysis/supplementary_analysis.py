#!/usr/bin/env python3
"""
补充实验分析
- 不同模型（LLM provider）对比
- 不同 top_k 参数影响
- 不同查询扩展数量影响
- 推理时间分析
- 错误案例分析

用法:
    python supplementary_analysis.py --results ../results/
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List


def load_all_results(results_dir: str) -> Dict[str, Dict[str, Any]]:
    """加载目录下所有结果文件"""
    results = {}
    for filename in os.listdir(results_dir):
        if filename.endswith("_results.json"):
            baseline_name = filename.replace("_results.json", "")
            filepath = os.path.join(results_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    results[baseline_name] = json.load(f)
            except Exception as e:
                print(f"Warning: 无法加载 {filename}: {e}")
    return results


def analyze_inference_time(all_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """分析推理时间"""
    time_stats = {}
    for name, result in all_results.items():
        avg_time = result.get("avg_inference_time", 0)
        total_time = result.get("total_inference_time", 0)
        total_cases = result.get("total_cases", 0)

        per_case = result.get("per_case_results", [])
        if per_case:
            times = [c.get("inference_time", 0) for c in per_case]
            min_time = min(times) if times else 0
            max_time = max(times) if times else 0
        else:
            min_time = max_time = 0

        time_stats[name] = {
            "avg_seconds": avg_time,
            "total_seconds": total_time,
            "min_seconds": min_time,
            "max_seconds": max_time,
            "total_cases": total_cases,
        }

    return time_stats


def analyze_error_cases(all_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """分析错误案例（所有系统都答错的案例 / 只有 DORA 答对的案例）"""
    # 收集每个案例的正确/错误情况
    case_results = defaultdict(dict)

    for name, result in all_results.items():
        per_case = result.get("per_case_results", [])
        for case in per_case:
            fault_id = case.get("fault_id", "")
            case_results[fault_id][name] = case.get("is_correct", False)

    # 所有系统都答错的案例
    all_wrong = []
    # 只有 DORA 答对的案例
    only_dora_correct = []
    # 多数系统答对的案例
    majority_correct = []

    total_systems = len(all_results)

    for fault_id, results in case_results.items():
        correct_count = sum(1 for v in results.values() if v)

        if correct_count == 0:
            all_wrong.append(fault_id)
        elif correct_count == 1 and results.get("dora", False):
            only_dora_correct.append(fault_id)
        elif correct_count >= total_systems / 2:
            majority_correct.append(fault_id)

    return {
        "total_cases": len(case_results),
        "all_wrong_cases": all_wrong,
        "all_wrong_count": len(all_wrong),
        "only_dora_correct_cases": only_dora_correct,
        "only_dora_correct_count": len(only_dora_correct),
        "majority_correct_cases": majority_correct,
        "majority_correct_count": len(majority_correct),
    }


def print_supplementary_analysis(all_results: Dict[str, Dict[str, Any]]) -> None:
    """打印补充实验分析"""
    print("=" * 70)
    print("补充实验分析")
    print("=" * 70)

    # 推理时间分析
    print("\n--- 推理时间分析 ---")
    time_stats = analyze_inference_time(all_results)

    time_header = f"{'系统':<25} {'平均(s)':>10} {'最小(s)':>10} {'最大(s)':>10} {'总时间(s)':>12}"
    print(time_header)
    print("-" * len(time_header))

    sorted_by_time = sorted(time_stats.items(), key=lambda x: x[1]["avg_seconds"])
    for name, stats in sorted_by_time:
        line = (
            f"{name:<25} "
            f"{stats['avg_seconds']:>9.3f} "
            f"{stats['min_seconds']:>9.3f} "
            f"{stats['max_seconds']:>9.3f} "
            f"{stats['total_seconds']:>11.1f}"
        )
        print(line)

    # 错误案例分析
    print("\n--- 错误案例分析 ---")
    error_analysis = analyze_error_cases(all_results)

    print(f"总案例数: {error_analysis['total_cases']}")
    print(f"所有系统都答错的案例: {error_analysis['all_wrong_count']}")
    print(f"只有 DORA 答对的案例: {error_analysis['only_dora_correct_count']}")
    print(f"多数系统答对的案例: {error_analysis['majority_correct_count']}")

    if error_analysis["only_dora_correct_cases"]:
        print(f"\n只有 DORA 答对的案例列表:")
        for fid in error_analysis["only_dora_correct_cases"][:10]:
            print(f"  - {fid}")
        if len(error_analysis["only_dora_correct_cases"]) > 10:
            print(f"  ... 还有 {len(error_analysis['only_dora_correct_cases']) - 10} 个")

    if error_analysis["all_wrong_cases"]:
        print(f"\n所有系统都答错的案例（难题）:")
        for fid in error_analysis["all_wrong_cases"][:10]:
            print(f"  - {fid}")
        if len(error_analysis["all_wrong_cases"]) > 10:
            print(f"  ... 还有 {len(error_analysis['all_wrong_cases']) - 10} 个")

    print("\n" + "=" * 70)


def save_supplementary_analysis(all_results: Dict[str, Dict[str, Any]],
                                 output_path: str) -> None:
    """保存补充实验分析结果"""
    analysis = {
        "inference_time_analysis": analyze_inference_time(all_results),
        "error_case_analysis": analyze_error_cases(all_results),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"\n补充实验分析结果已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="补充实验分析")
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

    print_supplementary_analysis(all_results)

    output_path = args.output or os.path.join(args.results, "supplementary_analysis.json")
    save_supplementary_analysis(all_results, output_path)


if __name__ == "__main__":
    main()
