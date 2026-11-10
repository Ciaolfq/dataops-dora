#!/usr/bin/env python3
"""
Baseline 5: ReAct RAG
ReAct (Reasoning + Acting) 风格的 RAG 系统。
模型循环进行：思考 -> 行动（检索） -> 观察 -> 思考... -> 最终回答。

用法:
    python run_react_rag.py --dataset ../data/fault_dataset_100.json --output ../results/

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
"""

import argparse
import json
import os
import sys
import time
import re
from typing import Any, Dict, List, Optional

# 添加 dora 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "dora"))

from core.retrieval.chroma_retrieval import ChromaRetrieval
from core.llm.openai_compatible import OpenAICompatibleLLM
from config.config_loader import global_cfg


REACT_SYSTEM_PROMPT = """You are a DataOps fault diagnosis expert using the ReAct framework.
You will reason about the problem and take actions (search the knowledge base) to gather
information before providing a final diagnosis.

Available actions:
- Search[query]: Search the knowledge base for relevant fault cases

Rules:
1. Start by analyzing the error and determining what information you need
2. Use Search[query] to look up relevant fault cases
3. After each search, review the results and decide if you need more information
4. You can make up to 3 searches
5. When you have enough information, provide your final diagnosis
6. Always output a JSON block with your final answer

Use the following format for each step:
Thought: [your reasoning about what to do next]
Action: Search[search query]
Observation: [search results will be provided here]

... (repeat as needed)

Thought: I have enough information to provide the diagnosis.
Final Answer:
```json
{
  "root_cause": "Brief description of the root cause",
  "category": "Fault category (e.g., configuration_error, dependency_issue, permission_error, syntax_error, network_issue, resource_exhaustion)",
  "confidence": 0.85,
  "fix_steps": [
    "Step 1 description",
    "Step 2 description"
  ]
}
```
"""

REACT_USER_PROMPT_TEMPLATE = """## Error Log

{error_log}

Please diagnose this error using the ReAct framework. Start with your first thought and action.
"""


def extract_search_query(text: str) -> Optional[str]:
    """从模型输出中提取 Search 查询"""
    match = re.search(r'Search\s*\[(.+?)\]', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_final_answer(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出中提取最终答案 JSON"""
    json_match = re.search(
        r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict) and "root_cause" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def build_observation(docs: List, max_docs: int = 3) -> str:
    """构建观察结果（检索结果摘要）"""
    if not docs:
        return "No relevant documents found."

    observations = []
    for i, doc in enumerate(docs[:max_docs], 1):
        category = doc.metadata.get("category", "Unknown")
        content_preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
        observations.append(f"[{i}] ({category}) {content_preview}")

    return "\n".join(observations)


def diagnose(error_log: str, retriever: ChromaRetrieval, llm: OpenAICompatibleLLM,
             max_steps: int = 3) -> Dict[str, Any]:
    """使用 ReAct RAG 进行诊断"""

    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": REACT_USER_PROMPT_TEMPLATE.format(error_log=error_log)},
    ]

    search_history = []
    final_result = {
        "root_cause": "",
        "category": "",
        "confidence": 0.0,
        "fix_steps": [],
        "method": "react_rag",
        "steps_taken": 0,
        "searches_done": 0,
    }

    for step in range(max_steps):
        # 调用 LLM
        response = llm.chat_with_messages(messages)

        # 检查是否有最终答案
        final_answer = extract_final_answer(response)
        if final_answer:
            final_result["root_cause"] = final_answer.get("root_cause", "")
            final_result["category"] = final_answer.get("category", "")
            final_result["confidence"] = float(final_answer.get("confidence", 0))
            final_result["fix_steps"] = final_answer.get("fix_steps", [])
            final_result["steps_taken"] = step + 1
            final_result["raw_answer"] = response
            return final_result

        # 检查是否有 Search 动作
        search_query = extract_search_query(response)
        if search_query and search_query not in search_history:
            # 执行检索
            docs = retriever.search(query=search_query, top_n=5)
            search_history.append(search_query)
            final_result["searches_done"] += 1

            # 构建观察
            observation = build_observation(docs)

            # 将模型回复和观察结果加入消息历史
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"Observation:\n{observation}\n\nContinue with your next thought and action, or provide the final answer.",
            })
        else:
            # 没有搜索也没有最终答案，催促模型
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "Please either search for more information or provide your final diagnosis with the JSON block.",
            })

    # 达到最大步数，要求最终答案
    final_prompt = "You have used all your search steps. Please provide your final diagnosis with the JSON block now."
    messages.append({"role": "user", "content": final_prompt})
    response = llm.chat_with_messages(messages)

    final_answer = extract_final_answer(response)
    if final_answer:
        final_result["root_cause"] = final_answer.get("root_cause", "")
        final_result["category"] = final_answer.get("category", "")
        final_result["confidence"] = float(final_answer.get("confidence", 0))
        final_result["fix_steps"] = final_answer.get("fix_steps", [])

    final_result["steps_taken"] = max_steps
    final_result["raw_answer"] = response
    return final_result


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str, max_steps: int = 3) -> Dict[str, Any]:
    """运行评估"""
    os.makedirs(output_dir, exist_ok=True)

    retriever = ChromaRetrieval()
    llm_cfg = global_cfg.get("llm", {})
    llm = OpenAICompatibleLLM(llm_cfg)

    per_case_results = []
    correct = 0
    total_time = 0.0

    for idx, case in enumerate(dataset, 1):
        fault_id = case["fault_id"]
        error_log = case["error_log"]

        print(f"  [{idx}/{len(dataset)}] {fault_id} (max_steps={max_steps})...", end=" ", flush=True)

        start_time = time.time()
        try:
            prediction = diagnose(error_log, retriever, llm, max_steps)
        except Exception as e:
            print(f"ERROR: {str(e)[:80]}")
            prediction = {
                "root_cause": f"Error: {str(e)}",
                "category": "error",
                "confidence": 0.0,
                "fix_steps": [],
                "method": "react_rag",
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
            "steps_taken": prediction.get("steps_taken", 0),
            "searches_done": prediction.get("searches_done", 0),
        })

    accuracy = correct / len(dataset) if dataset else 0.0

    result = {
        "baseline": "react_rag",
        "total_cases": len(dataset),
        "max_steps": max_steps,
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    output_path = os.path.join(output_dir, "react_rag_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nReAct RAG 评估完成:")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="ReAct RAG Baseline 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    parser.add_argument("--max_steps", type=int, default=3,
                        help="最大推理步数 (默认: 3)")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: ReAct RAG")
    print(f"数据集: {args.dataset}")
    print(f"max_steps={args.max_steps}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(dataset, args.output, args.max_steps)


if __name__ == "__main__":
    main()
