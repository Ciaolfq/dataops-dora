#!/usr/bin/env python3
"""
Baseline 2: Chain-of-Thought (CoT)
纯 LLM 零样本 + 思维链推理诊断。
让模型逐步分析错误，然后给出诊断结果。

用法:
    python run_cot.py --dataset ../data/fault_dataset_100.json --output ../results/

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
    OPENAI_API_KEY: OpenAI API Key (备选)
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

# 添加 dora 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "dora"))

from core.llm.openai_compatible import OpenAICompatibleLLM
from config.config_loader import global_cfg


COT_SYSTEM_PROMPT = """You are a DataOps and dbt fault diagnosis expert.
Analyze the following error log step by step, then provide your diagnosis.

Follow this reasoning process:
1. **Error Analysis**: What is the error saying? What are the key symptoms?
2. **Potential Causes**: List all possible root causes based on the error message
3. **Evidence Evaluation**: For each potential cause, evaluate how well it matches the evidence
4. **Root Cause**: Identify the most likely root cause
5. **Fix Plan**: Provide concrete steps to fix the issue

After your reasoning, output a JSON block with your final diagnosis:

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

Be thorough in your reasoning. Show your work before the final JSON answer.
"""

COT_USER_PROMPT_TEMPLATE = """## Error Log

{error_log}

Please analyze this error step by step and provide your diagnosis.
Show your reasoning process clearly, then output the JSON with the final answer.
"""


import re


def parse_structured_output(answer: str) -> Dict[str, Any]:
    """从 LLM 回答中解析结构化输出"""
    result = {
        "root_cause": "",
        "category": "",
        "confidence": 0.0,
        "fix_steps": [],
    }

    # 尝试从 JSON 代码块中解析
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


def diagnose(error_log: str, llm: OpenAICompatibleLLM) -> Dict[str, Any]:
    """使用 CoT 进行诊断"""
    user_prompt = COT_USER_PROMPT_TEMPLATE.format(error_log=error_log)

    raw_answer = llm.chat(
        prompt=user_prompt,
        system_prompt=COT_SYSTEM_PROMPT,
    )

    structured = parse_structured_output(raw_answer)

    return {
        "root_cause": structured["root_cause"],
        "category": structured["category"],
        "confidence": structured["confidence"],
        "fix_steps": structured["fix_steps"],
        "raw_answer": raw_answer,
        "method": "cot",
    }


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str) -> Dict[str, Any]:
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

        print(f"  [{idx}/{len(dataset)}] {fault_id}...", end=" ", flush=True)

        start_time = time.time()
        try:
            prediction = diagnose(error_log, llm)
        except Exception as e:
            print(f"ERROR: {str(e)[:80]}")
            prediction = {
                "root_cause": f"Error: {str(e)}",
                "category": "error",
                "confidence": 0.0,
                "fix_steps": [],
                "method": "cot",
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
        })

    accuracy = correct / len(dataset) if dataset else 0.0

    result = {
        "baseline": "cot",
        "total_cases": len(dataset),
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    output_path = os.path.join(output_dir, "cot_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nCoT 评估完成:")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Chain-of-Thought Baseline 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: Chain-of-Thought (CoT)")
    print(f"数据集: {args.dataset}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(dataset, args.output)


if __name__ == "__main__":
    main()
