#!/usr/bin/env python3
"""
Baseline 4: Cross-Encoder RAG
标准向量检索 + Cross-Encoder 重排 + LLM 生成。
无查询重写，只使用 Cross-Encoder 精排检索结果。

用法:
    python run_cross_encoder_rag.py --dataset ../data/fault_dataset_100.json --output ../results/

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

from core.retrieval.chroma_retrieval import ChromaRetrieval
from core.rerank.cross_encoder_rerank import CrossEncoderRerank
from core.llm.openai_compatible import OpenAICompatibleLLM
from config.config_loader import global_cfg


RAG_SYSTEM_PROMPT = """You are a professional dbt / DataOps fault diagnosis expert.
Based on the reference fault cases provided below, analyze the user's error log,
identify the root cause, and provide actionable fix steps.

Output requirements:
1. Analyze the error and explain your reasoning
2. Output a JSON block at the end with the following structure:
```json
{
  "root_cause": "Brief description of the root cause",
  "category": "Fault category (e.g., configuration_error, dependency_issue, permission_error, syntax_error, network_issue, resource_exhaustion, data_quality, schema_mismatch)",
  "confidence": 0.85,
  "fix_steps": [
    "Step 1 description",
    "Step 2 description",
    "Step 3 description"
  ]
}
```

Be precise and evidence-based. Use the reference cases as your primary evidence.
If the reference cases don't contain relevant information, say so clearly.
"""

RAG_USER_PROMPT_TEMPLATE = """## Reference Fault Cases

The following are relevant fault diagnosis cases retrieved from the knowledge base.
Use them as evidence to support your diagnosis.

{reference_block}

---

## Error Log to Diagnose

{error_log}

---

Please analyze the error log above and provide your diagnosis.
Reference the fault cases when applicable.
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


def build_reference_block(docs: List) -> str:
    """构建参考文档块"""
    doc_sections = []
    for i, doc in enumerate(docs, 1):
        category = doc.metadata.get("category", "Unknown")
        subcategory = doc.metadata.get("subcategory", "")
        cat_label = f"{category} / {subcategory}" if subcategory else category

        doc_section = f"""### Reference [{i}] - {cat_label}

{doc.content}
"""
        doc_sections.append(doc_section)

    return "\n".join(doc_sections) if doc_sections else "No reference documents found."


def diagnose(error_log: str, retriever: ChromaRetrieval, reranker: CrossEncoderRerank,
             llm: OpenAICompatibleLLM, top_k: int = 10, top_n: int = 5) -> Dict[str, Any]:
    """使用 Cross-Encoder RAG 进行诊断"""

    # Step 1: 向量检索
    retrieved_docs = retriever.search(query=error_log, top_n=top_k)

    # Step 2: Cross-Encoder 重排
    reranked_docs = reranker.rerank(query=error_log, documents=retrieved_docs, top_n=top_n)

    # Step 3: 构建 Prompt
    reference_block = build_reference_block(reranked_docs)
    user_prompt = RAG_USER_PROMPT_TEMPLATE.format(
        reference_block=reference_block,
        error_log=error_log,
    )

    # Step 4: LLM 生成
    raw_answer = llm.chat(
        prompt=user_prompt,
        system_prompt=RAG_SYSTEM_PROMPT,
    )

    # Step 5: 解析输出
    structured = parse_structured_output(raw_answer)

    return {
        "root_cause": structured["root_cause"],
        "category": structured["category"],
        "confidence": structured["confidence"],
        "fix_steps": structured["fix_steps"],
        "raw_answer": raw_answer,
        "method": "cross_encoder_rag",
        "retrieved_count": len(retrieved_docs),
        "reranked_count": len(reranked_docs),
    }


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str,
             top_k: int = 10, top_n: int = 5) -> Dict[str, Any]:
    """运行评估"""
    os.makedirs(output_dir, exist_ok=True)

    # 初始化组件
    retriever = ChromaRetrieval()
    reranker = CrossEncoderRerank()
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
            prediction = diagnose(error_log, retriever, reranker, llm, top_k, top_n)
        except Exception as e:
            print(f"ERROR: {str(e)[:80]}")
            prediction = {
                "root_cause": f"Error: {str(e)}",
                "category": "error",
                "confidence": 0.0,
                "fix_steps": [],
                "method": "cross_encoder_rag",
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
            "retrieved_count": prediction.get("retrieved_count", 0),
        })

    accuracy = correct / len(dataset) if dataset else 0.0

    result = {
        "baseline": "cross_encoder_rag",
        "total_cases": len(dataset),
        "top_k": top_k,
        "top_n": top_n,
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    output_path = os.path.join(output_dir, "cross_encoder_rag_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nCross-Encoder RAG 评估完成:")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Cross-Encoder RAG Baseline 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    parser.add_argument("--top_k", type=int, default=10,
                        help="初始检索数量 (默认: 10)")
    parser.add_argument("--top_n", type=int, default=5,
                        help="重排后保留数量 (默认: 5)")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: Cross-Encoder RAG")
    print(f"数据集: {args.dataset}")
    print(f"top_k={args.top_k}, top_n={args.top_n}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(dataset, args.output, args.top_k, args.top_n)


if __name__ == "__main__":
    main()
