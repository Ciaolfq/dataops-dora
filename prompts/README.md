# DORA Prompts
==========

All LLM prompts used in the DORA pipeline and baselines.

## DORA Pipeline Prompts

| File | Stage | Purpose |
|------|-------|---------|
| `preclassification.txt` | (optional LLM pre-classify) | Initial fault category prediction before retrieval |
| `query_rewrite.txt` | Stage 2 — Adaptive Multi-Query Retrieval | Generate 3-4 diverse retrieval queries from multiple semantic angles |
| `rerank.txt` | Stage 3 — LLM Reranking | Score document relevance (0–1 scale) for reranking |
| `diagnosis_grounded.txt` | Stage 4 — Grounded Diagnosis | Generate diagnosis using retrieved context (high-confidence path) |
| `diagnosis_internal.txt` | Stage 4 — Internal Diagnosis | Generate diagnosis using LLM internal knowledge (low-confidence path) |

## Baseline Prompts

| File | Baseline | Purpose |
|------|----------|---------|
| `cot_baseline.txt` | B2: CoT LLM | Chain-of-thought reasoning without retrieval |

## Prompt Design Principles

1. **Structured JSON output** — All diagnostic prompts end with a JSON block containing root_cause, category, confidence, and fix_steps
2. **Taxonomy-aware** — All baselines receive the same 20-label root cause taxonomy in their system prompts
3. **Error-aware** — DORA's query rewrite prompt receives the pre-classification prior as context
4. **Quality-gated** — Stage 4 has two paths (grounded vs internal) selected based on retrieval confidence
