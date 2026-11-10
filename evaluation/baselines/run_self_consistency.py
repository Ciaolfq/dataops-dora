#!/usr/bin/env python3
"""
Baseline 3: Self-Consistency
基于 CoT 的自一致性方法：多次采样，取多数投票结果。
通过多次生成并投票，提升诊断的稳定性和准确率。

用法:
    python run_self_consistency.py --dataset ../data/fault_dataset_100.json --output ../results/ --num_samples 5

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List

# 添加 dora 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "dora"))

from core.llm.openai_compatible import OpenAICompatibleLLM
from config.config_loader import global_cfg


# 复用 CoT 的 prompt
SC_SYSTEM_PROMPT = """You are a DataOps and dbt fault diagnosis expert.
Analyze the following error log and provide your diagnosis.

Output a JSON block with your diagnosis:

```json
{
  "root_cause": "Brief description of the root cause",
  "category": "Fault category (e.g., configuration_error, dependency_issue, permission_error, syntax_error, network_issue, resource_exhaustion)",
  "confidence": 0.85,
  "fix_steps": [
    "Step 1 description",
    "Step 2 description",
    "Step 3 description"
  ]
}
```
"""

SC_USER_PROMPT_TEMPLATE = """## Error Log

{error_log}

Please diagnose this error and output the JSON result.
"""

import re


def parse_structured_output(answer: str) -> Dict[str, Any]:
    """从回答中解析结构化输出"""
    result = {
        "root_cause": "",
        "category": "",
        "confidence": 0.0,
        "fix_steps": [],
    }

    json_match = re.search(
        r"```(?:json)?\s*\n(.*?)\n```", answer, re.DOTALL | re.IGNORECASE
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict):
                result["root_cause"] = data.get("root_cause", "")
                result["category"] = data.get("category", "")
                result["confidence"] = float(data.get("confidence", 0))
                steps = data.get("fix_steps", [])
                if isinstance(steps, list):
                    result["fix_steps"] = [str(s) for s in steps]
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return result


def diagnose_single(error_log: str, llm: OpenAICompatibleLLM, temperature: float = 0.7) -> Dict[str, Any]:
    """单次采样诊断"""
    user_prompt = SC_USER_PROMPT_TEMPLATE.format(error_log=error_log)

    raw_answer = llm.chat(
        prompt=user_prompt,
        system_prompt=SC_SYSTEM_PROMPT,
        temperature=temperature,
    )

    structured = parse_structured_output(raw_answer)
    return {
        "root_cause": structured["root_cause"],
        "category": structured["category"],
        "confidence": structured["confidence"],
        "fix_steps": structured["fix_steps"],
        "raw_answer": raw_answer,
    }


def diagnose_self_consistency(
    error_log: str,
    llm: OpenAICompatibleLLM,
    num_samples: int = 5,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """自一致性诊断：多次采样 + 多数投票"""
    samples = []

    for i in range(num_samples):
        sample = diagnose_single(error_log, llm, temperature)
        samples.append(sample)

    # 对 category 进行多数投票
    categories = [s["category"].lower() for s in samples if s["category"]]
    if categories:
        category_counter = Counter(categories)
        final_category = category_counter.most_common(1)[0][0]
        # 计算投票置信度
        vote_confidence = category_counter.most_common(1)[0][1] / len(samples)
    else:
        final_category = "unknown"
        vote_confidence = 0.0

    # 选择 category 与最终结果一致的第一个样本作为详细结果
    final_result = None
    for s in samples:
        if s["category"].lower() == final_category:
            final_result = s
            break

    if final_result is None:
        final_result = samples[0] if samples else {
            "root_cause": "",
            "category": final_category,
            "confidence": 0.0,
            "fix_steps": [],
        }

    return {
        "root_cause": final_result["root_cause"],
        "category": final_category,
        "confidence": vote_confidence,
        "fix_steps": final_result["fix_steps"],
        "method": "self_consistency",
        "num_samples": num_samples,
        "all_samples": [
            {"category": s["category"], "confidence": s["confidence"]}
            for s in samples
        ],
        "raw_answer": final_result.get("raw_answer", ""),
    }


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str, num_samples: int) -> Dict[str, Any]:
    """运行评估"""
    os.makedirs(output_dir, exist_ok=True)

    llm_cfg = global_cfg.get("llm", {})
    llm = OpenAICompatibleLLM(llm_cfg)

    per_case_results = []
    correct = 0
    total_time = 0.0

    for idx, case in enumerate(dataset, 1):
        fault_id = case["fault_id"]
        error_log = case["error_log"]

        print(f"  [{idx}/{len(dataset)}] {fault_id} ({num_samples} samples)...", end=" ", flush=True)

        start_time = time.time()
        try:
            prediction = diagnose_self_consistency(error_log, llm, num_samples)
        except Exception as e:
            print(f"ERROR: {str(e)[:80]}")
            prediction = {
                "root_cause": f"Error: {str(e)}",
                "category": "error",
                "confidence": 0.0,
                "fix_steps": [],
                "method": "self_consistency",
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
            "num_samples": num_samples,
        })

    accuracy = correct / len(dataset) if dataset else 0.0

    result = {
        "baseline": "self_consistency",
        "total_cases": len(dataset),
        "num_samples": num_samples,
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    output_path = os.path.join(output_dir, f"self_consistency_n{num_samples}_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nSelf-Consistency 评估完成 (n={num_samples}):")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Self-Consistency Baseline 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    parser.add_argument("--num_samples", "-n", type=int, default=5,
                        help="采样数量 (默认: 5)")
    parser.add_argument("--temperature", "-t", type=float, default=0.7,
                        help="采样温度 (默认: 0.7)")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: Self-Consistency")
    print(f"数据集: {args.dataset}")
    print(f"采样数: {args.num_samples}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(dataset, args.output, args.num_samples)


if __name__ == "__main__":
    main()
