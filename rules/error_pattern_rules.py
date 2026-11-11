"""
DORA Error Pattern Rules — Standalone Rule Engine
==================================================
Stage 1 of the DORA pipeline: deterministic pre-classification.

Usage:
    from error_pattern_rules import preclassify, rule_based_classify

    cat, subcat, rc_label, confidence, kws = preclassify(error_log)
    result = rule_based_classify(error_log)

This file is fully self-contained — no dependencies beyond Python stdlib.
"""
import re


# ============================================================
# Root Cause Taxonomy (20 labels across 3 categories)
# ============================================================

RC_TAXONOMY = {
    # Definition
    "DEF_CONFIG_MATERIALIZED": {"cat": "Definition", "sub": "Config"},
    "DEF_CONFIG_VAR":          {"cat": "Definition", "sub": "Config"},
    "DEF_CONFIG_YAML":         {"cat": "Definition", "sub": "Config"},
    "DEF_SYNTAX_FUNCTION":     {"cat": "Definition", "sub": "Syntax"},
    "DEF_SYNTAX_SQL":          {"cat": "Definition", "sub": "Syntax"},
    "DEF_DEP_REF":             {"cat": "Definition", "sub": "Dependency"},
    "DEF_DEP_CIRCULAR":        {"cat": "Definition", "sub": "Dependency"},
    # Data
    "DATA_SCHEMA_COLUMN":      {"cat": "Data", "sub": "Schema"},
    "DATA_SCHEMA_TABLE":       {"cat": "Data", "sub": "Schema"},
    "DATA_SCHEMA_DRIFT":       {"cat": "Data", "sub": "Schema"},
    "DATA_TYPE_CAST":          {"cat": "Data", "sub": "Type"},
    "DATA_QUALITY_UNIQUE":     {"cat": "Data", "sub": "Quality"},
    "DATA_QUALITY_FK":         {"cat": "Data", "sub": "Quality"},
    "DATA_QUALITY_NOTNULL":    {"cat": "Data", "sub": "Quality"},
    # Execution
    "EXE_DEP_CONNECTION":      {"cat": "Execution", "sub": "Dependency"},
    "EXE_PERF_TIMEOUT":        {"cat": "Execution", "sub": "Performance"},
    "EXE_CONC_DEADLOCK":       {"cat": "Execution", "sub": "Concurrency"},
    "EXE_PERM_DENIED":         {"cat": "Execution", "sub": "Permission"},
    "EXE_RES_DISK":            {"cat": "Execution", "sub": "Resource"},
    "EXE_RES_MEMORY":          {"cat": "Execution", "sub": "Resource"},
}


RC_LABEL_LIST = """
Definition Faults:
- DEF_CONFIG_MATERIALIZED: dbt materialized config error (typo/invalid value)
- DEF_CONFIG_VAR: undefined dbt variable/var
- DEF_CONFIG_YAML: YAML/schema.yml config syntax error
- DEF_SYNTAX_FUNCTION: undefined SQL function
- DEF_SYNTAX_SQL: SQL syntax/parse error
- DEF_DEP_REF: model ref() not found / missing model
- DEF_DEP_CIRCULAR: circular dependency / DAG cycle

Data Faults:
- DATA_SCHEMA_COLUMN: missing/non-existent column
- DATA_SCHEMA_TABLE: missing/non-existent table/relation
- DATA_SCHEMA_DRIFT: source schema drift / upstream schema change
- DATA_TYPE_CAST: data type mismatch / casting error
- DATA_QUALITY_UNIQUE: unique constraint violation / duplicate key
- DATA_QUALITY_FK: foreign key violation / referential integrity
- DATA_QUALITY_NOTNULL: not-null constraint violation

Execution Faults:
- EXE_DEP_CONNECTION: database connection failure
- EXE_PERF_TIMEOUT: query timeout / slow execution
- EXE_CONC_DEADLOCK: deadlock detected
- EXE_PERM_DENIED: permission denied / insufficient privilege
- EXE_RES_DISK: disk full / no space left
- EXE_RES_MEMORY: out of memory / OOM
"""


# ============================================================
# 19 Error Pattern Rules (ordered — first match wins)
# ============================================================
# Tuple format: (regex_pattern, category, subcategory, rc_label, query_hints)

ERROR_RULES = [
    # Execution (match most specific first)
    (r'permission denied|insufficient privilege|42501|access denied',
     'Execution', 'Permission', 'EXE_PERM_DENIED',
     ['permission denied postgres', 'grant privileges']),
    (r'deadlock|deadlock detected',
     'Execution', 'Concurrency', 'EXE_CONC_DEADLOCK',
     ['postgres deadlock fix', 'deadlock detected']),
    (r'no space left|disk full|insufficient disk|out of disk',
     'Execution', 'Resource', 'EXE_RES_DISK',
     ['disk full no space', 'insufficient disk space']),
    (r'out of memory|memory exhausted|oom|insufficient memory',
     'Execution', 'Resource', 'EXE_RES_MEMORY',
     ['out of memory error', 'insufficient memory postgres']),
    (r'connection refused|could not connect|connection failed|cannot connect',
     'Execution', 'Dependency', 'EXE_DEP_CONNECTION',
     ['connection refused database', 'postgres connection error']),
    (r'timeout|timed out|statement timeout|query timeout',
     'Execution', 'Performance', 'EXE_PERF_TIMEOUT',
     ['query timeout fix', 'optimize slow query']),
    # Definition
    (r'circular|cycle.*detect|cyclic.*dependency|circular reference',
     'Definition', 'Dependency', 'DEF_DEP_CIRCULAR',
     ['circular dependency dag', 'circular reference error']),
    (r'var.*not defined|undefined variable|variable.*not found|dbt.*var',
     'Definition', 'Config', 'DEF_CONFIG_VAR',
     ['dbt var undefined', 'dbt variable config']),
    (r'materialized|dbt_project.*yml|invalid.*config|misconfigured',
     'Definition', 'Config', 'DEF_CONFIG_MATERIALIZED',
     ['dbt materialized configuration', 'dbt_project.yml settings']),
    (r'function.*does not exist|undefined function|function.*not found',
     'Definition', 'Syntax', 'DEF_SYNTAX_FUNCTION',
     ['postgres undefined function', 'create function sql']),
    (r'model.*not found|ref.*not found|could not find model|undefined model',
     'Definition', 'Dependency', 'DEF_DEP_REF',
     ['dbt ref not found', 'dbt model dependency']),
    (r'syntax error|parse error|syntaxerror|sqlstate.*42601',
     'Definition', 'Syntax', 'DEF_SYNTAX_SQL',
     ['sql syntax error', 'postgres parse error']),
    # Data
    (r'foreign key.*violat|violates foreign key|fk.*constraint|referential integrity',
     'Data', 'Quality', 'DATA_QUALITY_FK',
     ['foreign key violation', 'referential integrity']),
    (r'duplicate key|unique constraint|violates unique|duplicate.*value',
     'Data', 'Quality', 'DATA_QUALITY_UNIQUE',
     ['duplicate key unique constraint', 'unique violation fix']),
    (r'null value.*not null|not null.*violat|violates not-null|notnull',
     'Data', 'Quality', 'DATA_QUALITY_NOTNULL',
     ['not null constraint violation', 'null value error']),
    (r'invalid input syntax|cannot cast|invalid.*type|type.*mismatch|datatype.*error',
     'Data', 'Type', 'DATA_TYPE_CAST',
     ['data type mismatch', 'postgres cast error']),
    (r'schema.*changed|schema drift|source schema|column.*added|column.*dropped',
     'Data', 'Schema', 'DATA_SCHEMA_DRIFT',
     ['schema drift pipeline', 'source schema change']),
    (r'relation.*does not exist|table.*does not exist|relation.*not found',
     'Data', 'Schema', 'DATA_SCHEMA_TABLE',
     ['table not exist postgres', 'relation not found error']),
    (r'column.*does not exist|unknown column|column.*not found|missing.*column',
     'Data', 'Schema', 'DATA_SCHEMA_COLUMN',
     ['column not exist error', 'missing column postgres']),
]


# ============================================================
# Public API
# ============================================================

def preclassify(error_log: str):
    """
    Stage 1: Lightweight pre-classification.
    Returns (category, subcategory, rc_label, confidence, query_hints).
    If no rule matches, returns ("Unknown", "Unknown", "UNKNOWN", 0.3, []).
    """
    log = error_log.lower()
    for pattern, cat, subcat, rc_label, kws in ERROR_RULES:
        if re.search(pattern, log):
            return cat, subcat, rc_label, 0.85, kws
    return "Unknown", "Unknown", "UNKNOWN", 0.3, []


def rule_based_classify(error_log: str) -> dict:
    """
    Full rule-based diagnosis (used as B1 baseline).
    Returns a dict with category, subcategory, rc_label, root_cause, fix_steps.
    """
    log = error_log.lower()
    for pattern, cat, subcat, rc_label, kws in ERROR_RULES:
        if re.search(pattern, log):
            return {
                "category": cat,
                "subcategory": subcat,
                "rc_label": rc_label,
                "confidence": 0.8,
                "root_cause": rc_label.replace('_', ' ').lower(),
                "fix_steps": _rule_based_fix(rc_label),
                "rc_candidates": [rc_label],
            }
    return {
        "category": "Unknown",
        "subcategory": "Unknown",
        "rc_label": "UNKNOWN",
        "confidence": 0.2,
        "root_cause": "Unknown error type",
        "fix_steps": ["Check logs for more details"],
        "rc_candidates": ["UNKNOWN"],
    }


def classify_rc_label(text: str) -> str:
    """Map arbitrary text to a root cause label via keyword matching."""
    t = text.lower()
    for label in RC_TAXONOMY.keys():
        if label.lower() in t:
            return label
    for pattern, _c, _s, label, _k in ERROR_RULES:
        if re.search(pattern, t):
            return label
    return "UNKNOWN"


# ============================================================
# Rule-based fix suggestions (for B1 baseline only)
# ============================================================

def _rule_based_fix(rc_label: str) -> list:
    fixes = {
        "DEF_CONFIG_MATERIALIZED": [
            "Fix materialized value in dbt_project.yml",
            "Run dbt compile to verify",
        ],
        "DEF_CONFIG_VAR": [
            "Add variable definition to dbt_project.yml vars section",
            "Verify variable name spelling",
        ],
        "DEF_CONFIG_YAML": [
            "Fix YAML syntax in schema.yml",
            "Validate with YAML linter",
        ],
        "DEF_SYNTAX_FUNCTION": [
            "Create the missing function",
            "Verify function name and argument types",
        ],
        "DEF_SYNTAX_SQL": [
            "Fix SQL syntax error",
            "Review query near error position",
        ],
        "DEF_DEP_REF": [
            "Correct model name in ref()",
            "Ensure model exists and is enabled",
        ],
        "DEF_DEP_CIRCULAR": [
            "Break circular dependency by refactoring",
            "Use ephemeral intermediate models",
        ],
        "DATA_SCHEMA_COLUMN": [
            "Update model to handle missing column",
            "Add COALESCE or remove reference",
        ],
        "DATA_SCHEMA_TABLE": [
            "Verify table exists",
            "Run upstream models first",
        ],
        "DATA_SCHEMA_DRIFT": [
            "Update model for new schema",
            "Add schema change detection tests",
        ],
        "DATA_TYPE_CAST": [
            "Add explicit type casting with :: or CAST()",
            "Align column types across tables",
        ],
        "DATA_QUALITY_UNIQUE": [
            "Add deduplication with row_number()",
            "Check source for duplicate records",
        ],
        "DATA_QUALITY_FK": [
            "Fix orphaned records",
            "Add referential integrity tests",
        ],
        "DATA_QUALITY_NOTNULL": [
            "Use COALESCE to handle NULL",
            "Add not_null dbt test",
        ],
        "EXE_DEP_CONNECTION": [
            "Verify database host/port config",
            "Check network connectivity",
        ],
        "EXE_PERF_TIMEOUT": [
            "Add indexes on filtered columns",
            "Use incremental models",
            "Optimize with EXPLAIN ANALYZE",
        ],
        "EXE_CONC_DEADLOCK": [
            "Ensure consistent table access order",
            "Add retry logic for deadlocks",
        ],
        "EXE_PERM_DENIED": [
            "GRANT SELECT, INSERT, UPDATE, DELETE on tables",
            "GRANT USAGE on schema",
        ],
        "EXE_RES_DISK": [
            "Run VACUUM to reclaim space",
            "Clean up temporary tables",
        ],
        "EXE_RES_MEMORY": [
            "Optimize query memory usage",
            "Increase work_mem if needed",
        ],
    }
    return fixes.get(rc_label, ["Check error logs for details"])


# ============================================================
# Quick test
# ============================================================

if __name__ == "__main__":
    test_cases = [
        ("psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint",
         "DATA_QUALITY_UNIQUE"),
        ("permission denied for relation orders", "EXE_PERM_DENIED"),
        ("deadlock detected", "EXE_CONC_DEADLOCK"),
        ("column 'email' does not exist", "DATA_SCHEMA_COLUMN"),
        ("function json_build_array(text) does not exist", "DEF_SYNTAX_FUNCTION"),
        ("model 'stg_unknown' not found", "DEF_DEP_REF"),
    ]
    print("DORA Pre-classification Rule Test")
    print("=" * 60)
    for log, expected in test_cases:
        cat, subcat, label, conf, kws = preclassify(log)
        status = "✓" if label == expected else f"✗ (expected {expected})"
        print(f"  {status}  {label:<25}  conf={conf}  ({cat}/{subcat})")
    print(f"\nTotal rules: {len(ERROR_RULES)}")
    print(f"Taxonomy labels: {len(RC_TAXONOMY)}")
