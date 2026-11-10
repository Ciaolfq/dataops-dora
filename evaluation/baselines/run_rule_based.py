#!/usr/bin/env python3
"""
Baseline 1: Rule-based Matcher
基于正则表达式和关键字匹配的传统故障诊断方法。
预定义规则库，覆盖 dbt/Airflow/PostgreSQL 常见错误。

用法:
    python run_rule_based.py --dataset ../data/fault_dataset_100.json --output ../results/
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

# 添加 dora 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "dora"))


# ============================================================
# 预定义规则库（20+ 条）
# 覆盖 dbt / Airflow / PostgreSQL 常见错误
# ============================================================

RULES: List[Dict[str, Any]] = [
    # ---------- dbt 相关错误 ----------
    {
        "id": "DBT-001",
        "pattern": r"Compilation Error.*not found|relation.*does not exist|Table.*doesn't exist",
        "category": "schema_mismatch",
        "root_cause": "Model references a table or view that does not exist, possibly due to upstream models not being run or incorrect schema names.",
        "fix_steps": [
            "Check if upstream models have run successfully (dbt ls --select +model_name)",
            "Verify source/ref references and schema names",
            "Run dbt run --select +model_name to build upstream dependencies first",
            "Check schema configuration in profiles.yml",
        ],
        "confidence": 0.85,
    },
    {
        "id": "DBT-002",
        "pattern": r"Database Error.*permission denied|permission denied for (relation|schema|table)",
        "category": "permission_error",
        "root_cause": "Database user lacks necessary permissions on tables, schemas, or databases.",
        "fix_steps": [
            "Check if the dbt profile user has sufficient permissions",
            "Contact DBA to grant required permissions (SELECT, INSERT, CREATE, USAGE)",
            "Verify user has USAGE permission on target schema",
            "For materialized views, additional CREATE permissions are needed",
        ],
        "confidence": 0.9,
    },
    {
        "id": "DBT-003",
        "pattern": r"Syntax error|syntax error at or near|SQL compilation error",
        "category": "syntax_error",
        "root_cause": "SQL syntax error, possibly due to misspelled keywords, missing parentheses, or missing semicolons.",
        "fix_steps": [
            "Carefully inspect the SQL code near the line number indicated in the error",
            "Verify all SQL keywords are spelled correctly (SELECT, FROM, JOIN, WHERE)",
            "Check for matching parentheses and correct comma usage",
            "Use dbt parse command to quickly validate SQL syntax",
        ],
        "confidence": 0.8,
    },
    {
        "id": "DBT-004",
        "pattern": r"dbt.*version.*not found|requires dbt version|no matching distribution found",
        "category": "dependency_issue",
        "root_cause": "dbt version incompatibility or missing dbt adapter plugin.",
        "fix_steps": [
            "Check require-dbt-version config in dbt_project.yml",
            "Run dbt --version to check current version",
            "Use pip install --upgrade dbt-<adapter> to install the correct adapter",
            "Confirm project dbt version matches environment version",
        ],
        "confidence": 0.85,
    },
    {
        "id": "DBT-005",
        "pattern": r"Test.*failed|assertion.*failed|unique.*fail|not_null.*fail|relationships.*fail",
        "category": "data_quality",
        "root_cause": "dbt data test failure - uniqueness, non-null, referential integrity, or custom tests failed.",
        "fix_steps": [
            "Identify which specific test failed (unique/not_null/relationships/custom)",
            "Run dbt test --select test_name to get detailed failure data",
            "Check source data for quality issues (duplicates, nulls, orphan records)",
            "Fix source data or adjust test logic as appropriate",
        ],
        "confidence": 0.8,
    },
    {
        "id": "DBT-006",
        "pattern": r"YAML.*error|yaml\.scanner|yaml\.parser|mapping values are not allowed",
        "category": "configuration_error",
        "root_cause": "YAML configuration file format error, commonly due to incorrect indentation or unescaped special characters.",
        "fix_steps": [
            "Check the YAML file and line number indicated by the error",
            "Ensure spaces are used for indentation (2-space standard), not tabs",
            "Check for spaces after colons and wrap special characters in quotes",
            "Use online YAML validation tools to verify file format",
        ],
        "confidence": 0.88,
    },
    {
        "id": "DBT-007",
        "pattern": r"Connection refused|Could not connect to server|connection to server.*failed",
        "category": "network_issue",
        "root_cause": "Unable to connect to database server - possible network issue, database not running, or incorrect connection config.",
        "fix_steps": [
            "Check host, port, and database config in profiles.yml",
            "Verify the database service is running",
            "Test network connectivity (ping or telnet host port)",
            "Check firewall settings blocking the database port",
        ],
        "confidence": 0.85,
    },
    {
        "id": "DBT-008",
        "pattern": r"Out of memory|out of shared memory|memory exhausted|cannot allocate memory",
        "category": "resource_exhaustion",
        "root_cause": "Insufficient memory - query too complex, data volume too large, or system memory config insufficient.",
        "fix_steps": [
            "Check for full table scans on very large tables or complex multi-table JOINs",
            "Optimize SQL queries, add filters to reduce data volume",
            "Increase database work_mem or shared_buffers configuration",
            "Consider using incremental models instead of full builds",
        ],
        "confidence": 0.82,
    },
    # ---------- Airflow 相关错误 ----------
    {
        "id": "AIRFLOW-001",
        "pattern": r"DAG.*not found|dag_id.*does not exist|No such file",
        "category": "configuration_error",
        "root_cause": "Airflow cannot find the specified DAG file - possible path config error or syntax issue in DAG file.",
        "fix_steps": [
            "Confirm the DAG file exists in the dags_folder directory",
            "Check dags_folder config in airflow.cfg",
            "Run airflow dags list to see loaded DAGs",
            "Check DAG file for Python syntax errors (airflow dags reserialize)",
        ],
        "confidence": 0.82,
    },
    {
        "id": "AIRFLOW-002",
        "pattern": r"Connection.*not found|conn_id.*(?:isn't|is not) defined|connection id.*does not exist",
        "category": "configuration_error",
        "root_cause": "Airflow Connection not configured or misconfigured.",
        "fix_steps": [
            "Check connection config in Airflow UI Admin -> Connections",
            "Verify conn_id spelling matches references in DAG code",
            "Validate connection type, host, port, login, password settings",
            "Use airflow connections get <conn_id> to check config",
        ],
        "confidence": 0.88,
    },
    {
        "id": "AIRFLOW-003",
        "pattern": r"Scheduler.*heartbeat|scheduler.*not running|Scheduler seems to be down",
        "category": "runtime_error",
        "root_cause": "Airflow Scheduler not running or lost heartbeat.",
        "fix_steps": [
            "Check if Scheduler process is running (ps aux | grep scheduler)",
            "Review Scheduler logs for crash causes",
            "Restart Scheduler service",
            "Check database connectivity (Scheduler requires persistent metadata DB connection)",
        ],
        "confidence": 0.85,
    },
    {
        "id": "AIRFLOW-004",
        "pattern": r"ImportError|ModuleNotFoundError|No module named",
        "category": "dependency_issue",
        "root_cause": "Python module missing - package required by DAG or Operator not installed.",
        "fix_steps": [
            "Identify the missing module and install with pip install",
            "Check both Airflow worker and scheduler environments have dependencies installed",
            "If using Docker, update the image and redeploy",
            "Recommend using requirements.txt for unified dependency management",
        ],
        "confidence": 0.87,
    },
    {
        "id": "AIRFLOW-005",
        "pattern": r"deadlock detected|deadlock found|Lock wait timeout",
        "category": "concurrency_issue",
        "root_cause": "Database deadlock - multiple tasks modifying same data simultaneously causing lock contention.",
        "fix_steps": [
            "Check if multiple tasks are writing to the same table concurrently",
            "Adjust DAG scheduling to avoid concurrent execution",
            "Add row-level locking or use transaction isolation levels in tasks",
            "For Airflow metadata DB deadlocks, consider using pools to limit concurrency",
        ],
        "confidence": 0.8,
    },
    # ---------- PostgreSQL 相关错误 ----------
    {
        "id": "PG-001",
        "pattern": r"duplicate key value violates unique constraint|unique constraint.*violated",
        "category": "data_quality",
        "root_cause": "Violation of unique constraint during insert/update - duplicate key values exist.",
        "fix_steps": [
            "Review the constraint name in the error to identify which unique index conflicts",
            "Check source data for duplicate values",
            "Use ON CONFLICT clause to handle duplicates (UPSERT)",
            "For incremental loading, ensure deduplication logic is correct",
        ],
        "confidence": 0.9,
    },
    {
        "id": "PG-002",
        "pattern": r"foreign key constraint.*violated|violates foreign key constraint",
        "category": "data_quality",
        "root_cause": "Foreign key constraint violation - child table references a non-existent parent table record.",
        "fix_steps": [
            "Confirm parent record referenced by foreign key exists",
            "Check data loading order is correct (parent tables first, then child tables)",
            "For incremental data, ensure upstream data integrity",
            "Consider temporarily disabling foreign key constraints (evaluate data consistency risk)",
        ],
        "confidence": 0.88,
    },
    {
        "id": "PG-003",
        "pattern": r"too many connections|remaining connection slots are reserved|connection limit exceeded",
        "category": "resource_exhaustion",
        "root_cause": "PostgreSQL connection count has reached maximum limit.",
        "fix_steps": [
            "Check current connection count (SELECT count(*) FROM pg_stat_activity;)",
            "Check for connection leaks (application not closing connections properly)",
            "Increase max_connections configuration (requires database restart)",
            "Consider using connection pooling like PgBouncer",
        ],
        "confidence": 0.87,
    },
    {
        "id": "PG-004",
        "pattern": r"could not extend file|No space left on device|disk.*full",
        "category": "resource_exhaustion",
        "root_cause": "Insufficient disk space - database cannot write data.",
        "fix_steps": [
            "Check disk usage (df -h)",
            "Clean up temporary files and WAL logs (pg_archivecleanup)",
            "Run VACUUM or drop unused tables/indexes to free space",
            "Consider expanding disk or migrating to larger storage",
        ],
        "confidence": 0.9,
    },
    # ---------- 通用错误 ----------
    {
        "id": "GEN-001",
        "pattern": r"timeout.*expired|Request timed out|connection timeout",
        "category": "network_issue",
        "root_cause": "Network request timeout - possible high network latency or slow target service response.",
        "fix_steps": [
            "Check if network connection is stable",
            "Confirm target service is running normally",
            "Increase timeout configuration",
            "If cross-network access, consider using a closer service node",
        ],
        "confidence": 0.8,
    },
    {
        "id": "GEN-002",
        "pattern": r"Authentication failed|authentication.*failed|Invalid credentials|access denied",
        "category": "permission_error",
        "root_cause": "Authentication failure - incorrect username/password or expired token.",
        "fix_steps": [
            "Check username and password are correct",
            "Confirm API Key or Token hasn't expired",
            "Check if account is locked or disabled",
            "If using IAM roles, verify role permissions and trust relationship config",
        ],
        "confidence": 0.85,
    },
]

import re


def match_rules(error_log: str) -> List[Dict[str, Any]]:
    """匹配错误日志，返回所有匹配的规则"""
    matches = []
    for rule in RULES:
        try:
            pattern = re.compile(rule["pattern"], re.IGNORECASE | re.DOTALL)
            if pattern.search(error_log):
                matches.append(rule)
        except re.error:
            continue
    # 按置信度排序
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches


def diagnose(error_log: str) -> Dict[str, Any]:
    """对错误日志进行诊断，返回 top-1 匹配结果"""
    matched = match_rules(error_log)
    if matched:
        top = matched[0]
        return {
            "root_cause": top["root_cause"],
            "category": top["category"],
            "confidence": top["confidence"],
            "fix_steps": top["fix_steps"],
            "method": "rule_based",
            "matched_rules": [r["id"] for r in matched],
        }
    else:
        return {
            "root_cause": "Unrecognized error pattern, no predefined rules matched.",
            "category": "unknown",
            "confidence": 0.0,
            "fix_steps": [
                "Please provide more detailed error logs",
                "Check if this is a variant of a known error type",
                "Consider using LLM or RAG systems for diagnosis",
            ],
            "method": "rule_based",
            "matched_rules": [],
        }


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """加载故障数据集"""
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(dataset: List[Dict[str, Any]], output_dir: str) -> Dict[str, Any]:
    """运行评估"""
    os.makedirs(output_dir, exist_ok=True)

    per_case_results = []
    correct = 0
    total_time = 0.0

    for idx, case in enumerate(dataset, 1):
        fault_id = case["fault_id"]
        error_log = case["error_log"]

        print(f"  [{idx}/{len(dataset)}] {fault_id}...", end=" ", flush=True)

        start_time = time.time()
        prediction = diagnose(error_log)
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
        "baseline": "rule_based",
        "total_cases": len(dataset),
        "top1_accuracy": round(accuracy, 4),
        "correct_count": correct,
        "total_inference_time": round(total_time, 2),
        "avg_inference_time": round(total_time / len(dataset), 4) if dataset else 0,
        "per_case_results": per_case_results,
    }

    # 保存结果
    output_path = os.path.join(output_dir, "rule_based_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nRule-based 评估完成:")
    print(f"  Top-1 准确率: {accuracy:.2%} ({correct}/{len(dataset)})")
    print(f"  平均耗时: {result['avg_inference_time']:.4f}s")
    print(f"  结果已保存: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Rule-based Baseline 评估")
    parser.add_argument("--dataset", "-d", type=str, required=True,
                        help="故障数据集 JSON 文件路径")
    parser.add_argument("--output", "-o", type=str, default="../results/",
                        help="结果输出目录")
    args = parser.parse_args()

    print("=" * 60)
    print("Baseline: Rule-based Matcher")
    print(f"数据集: {args.dataset}")
    print(f"规则数: {len(RULES)}")
    print("=" * 60)

    dataset = load_dataset(args.dataset)
    print(f"加载了 {len(dataset)} 条故障案例\n")

    evaluate(dataset, args.output)


if __name__ == "__main__":
    main()
