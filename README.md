# DORA: Error-Aware Retrieval-Augmented Generation for Automated Fault Diagnosis in Data Engineering Pipelines

**Accepted at ICDE 2027**

---

## Abstract

Modern data engineering pipelines built on dbt, Airflow, and similar stacks fail frequently due to a wide range of faults spanning configuration, data quality, schema, and runtime execution. While large language models (LLMs) show promise for automated diagnosis, vanilla retrieval-augmented generation (RAG) often **hurts** fix quality — a phenomenon we call the *RAG Paradox*: retrieved documents improve classification accuracy but introduce noise that degrades the validity of generated fixes.

We present **DORA** (DataOps Retrieval-Augmented diagnosis), a four-stage error-aware diagnostic pipeline that reverses this degradation. DORA combines (1) deterministic error pattern pre-classification, (2) type-aware adaptive multi-query retrieval, (3) LLM listwise reranking, and (4) quality-aware grounded diagnosis with a dynamic mode switch.

Evaluated on **100 injected faults** across three major categories (Definition, Data, Execution) in an Airflow + dbt + PostgreSQL environment, DORA achieves **69.0% RCHR@1** and **0.731 Action Validity**, outperforming the strongest RAG baseline by **+43.6% in Action Validity** while also being faster (4.1s vs. 6.3s).

---

## Architecture

<p align="center">
  <img src="figures/%E5%9B%BE%E7%89%870.pdf" alt="DORA Architecture" width="85%">
  <br>
  <em>Figure 1: The DORA four-stage diagnostic pipeline.</em>
</p>

DORA executes four sequential stages:

1. **Error Pattern Pre-classification** — A deterministic rule engine classifies the error into 1 of 16 fault subcategories to establish an initial hypothesis.
2. **Type-Aware Adaptive Multi-Query Retrieval** — Guided by the prior, the system synthesizes diverse queries (symptom, root cause, remediation) and retrieves from a curated DataOps knowledge base.
3. **LLM Listwise Reranking** — An LLM-based reranker scores each candidate on diagnostic relevance, filtering out tangential noise.
4. **Quality-Aware Diagnosis** — A quality gate routes to either *grounded* generation (high-confidence context) or *internal* reasoning (low-confidence context), preventing hallucination from noisy retrieval.

---

## Key Results

### Overall Performance (100 injected faults)

| Method | RCHR@1 ↑ | RCHR@3 ↑ | Action Validity ↑ | Latency ↓ |
|--------|:--------:|:--------:|:-----------------:|:---------:|
| B1: Rule-based Parser | 39.0% | 39.0% | 0.189 | <0.1s |
| B2: CoT LLM | 67.0% | 86.0% | 0.671 | 6.0s |
| B3: Self-Consistency | 36.0% | 40.0% | 0.493 | 6.0s |
| B4: Cross-Encoder RAG | 68.0% | 83.0% | 0.509 | 2.5s |
| B5: ReAct-style RAG | 64.0% | 82.0% | 0.506 | 6.3s |
| **B6: DORA (Ours)** | **69.0%** | **85.0%** | **0.729** | **4.1s** |

> **The RAG Paradox**: Vanilla RAG (B4) improves RCHR by +1.0pp over CoT but **reduces Action Validity by −24.1%**. DORA reverses this, converting RAG from a liability into an asset (+8.7% AV vs. CoT).

<p align="center">
  <img src="figures/%E5%9B%BE%E7%89%873.pdf" alt="Main Results" width="80%">
  <br>
  <em>Figure 2: Overall diagnostic performance comparison.</em>
</p>

### By Fault Category

| Category | DORA AV | Best Baseline | Improvement |
|----------|:-------:|:-------------:|:-----------:|
| Definition (35 cases) | 0.741 | 0.722 (CoT) | +2.6% |
| Data (35 cases) | 0.716 | 0.690 (CoT) | +3.8% |
| Execution (30 cases) | 0.729 | 0.590 (CoT) | **+23.6%** |

DORA's largest advantage is on **Execution faults** — the category where vanilla RAG does the most damage.

<p align="center">
  <img src="figures/%E5%9B%BE%E7%89%874.pdf" alt="Category Comparison" width="80%">
  <br>
  <em>Figure 3: Action Validity by fault category.</em>
</p>

### Ablation Study

| Configuration | RCHR@1 | Action Validity |
|---------------|:------:|:---------------:|
| Vanilla RAG (Baseline) | 61.0% | 0.509 |
| + Error Pre-classification | 63.0% | 0.615 |
| + Adaptive Multi-Query | 66.0% | 0.678 |
| + LLM Reranking | 68.0% | 0.710 |
| **+ Quality Gating (Full DORA)** | **69.0%** | **0.731** |

<p align="center">
  <img src="figures/v2.pdf" alt="Ablation Study" width="70%">
  <br>
  <em>Figure 4: Component-wise ablation study of DORA.</em>
</p>

---

## Repository Structure

```
ICDE-2027/
├── README.md                          # This file
├── REPLICATION.md                     # Step-by-step replication guide
├── requirements.txt                   # Python dependencies
│
├── dora/                              # DORA system core
│   ├── config/                        # Configuration (API via env var)
│   ├── core/
│   │   ├── llm/                       # LLM providers (DeepSeek, Qwen, etc.)
│   │   ├── query_rewrite/             # Error-aware query rewriting
│   │   ├── rerank/                    # Cross-encoder & simple reranking
│   │   └── retrieval/                 # Chroma & memory retrieval
│   ├── data/
│   │   ├── loader/                    # Data loaders
│   │   ├── chunker.py                 # Document chunking
│   │   ├── vector_builder.py          # Vector DB construction
│   │   └── knowledge_base_sample.json # Sample KB (50 entries)
│   ├── pipeline/
│   │   ├── dora_pipeline.py           # Full DORA pipeline
│   │   └── standard_rag_pipeline.py   # Standard RAG baseline
│   ├── prompts/                       # All prompt templates (6 files)
│   ├── utils/
│   └── main.py                        # CLI entry point
│
├── evaluation/
│   ├── baselines/                     # 6 baseline systems
│   │   ├── run_rule_based.py          # B1: Regex/rule-based
│   │   ├── run_cot.py                 # B2: Chain-of-Thought LLM
│   │   ├── run_self_consistency.py    # B3: Self-consistency
│   │   ├── run_cross_encoder_rag.py   # B4: Cross-Encoder RAG
│   │   ├── run_react_rag.py           # B5: ReAct-style RAG
│   │   └── run_dora.py                # B6: DORA (our system)
│   ├── data/
│   │   ├── fault_dataset_100.json     # 100 fault test cases
│   │   └── testdata.json              # Additional test data
│   ├── analysis/                      # Data analysis scripts
│   │   ├── calculate_metrics.py       # RCHR, AV, latency
│   │   ├── category_analysis.py       # Per-category breakdown
│   │   ├── ablation_analysis.py       # Component ablation
│   │   └── supplementary_analysis.py  # Additional analyses
│   └── results/                       # Output directory
│
├── docker_env/                        # Docker experiment environment
│   ├── docker-compose.yml             # Airflow + dbt + PostgreSQL
│   ├── airflow/dags/                  # 6-task demo DAG
│   ├── dbt/dbt_project/               # dbt project (staging + marts)
│   ├── postgres/init/                 # PostgreSQL initialization
│   └── fault_injection/               # Fault injection framework
│
└── figures/                           # Paper figures (PDF)
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API Key

```bash
# Linux/macOS
export DEEPSEEK_API_KEY="your-api-key"

# Windows
set DEEPSEEK_API_KEY=your-api-key
```

### 3. Build the Knowledge Base

```bash
cd dora
python -m data.vector_builder \
  --input data/knowledge_base_sample.json \
  --output chroma_db/
```

### 4. Run DORA

```bash
# Single diagnosis
python dora/main.py --log "your error log text"

# Full evaluation on 100 faults
python evaluation/baselines/run_dora.py \
  --dataset evaluation/data/fault_dataset_100.json \
  --output evaluation/results/
```

### 5. Run All Baselines

```bash
cd evaluation/baselines
python run_rule_based.py --dataset ../data/fault_dataset_100.json --output ../results/
python run_cot.py          --dataset ../data/fault_dataset_100.json --output ../results/
python run_self_consistency.py --dataset ../data/fault_dataset_100.json --output ../results/
python run_cross_encoder_rag.py --dataset ../data/fault_dataset_100.json --output ../results/
python run_react_rag.py    --dataset ../data/fault_dataset_100.json --output ../results/
python run_dora.py         --dataset ../data/fault_dataset_100.json --output ../results/
```

### 6. Analyze Results

```bash
cd evaluation/analysis
python calculate_metrics.py   --results ../results/
python category_analysis.py   --results ../results/
python ablation_analysis.py   --results ../results/
```

> **Detailed step-by-step instructions**: See [REPLICATION.md](REPLICATION.md).

---

## Docker Environment

A complete end-to-end experiment environment with Airflow, dbt-core, and PostgreSQL is provided in `docker_env/`. This environment supports:

- Running a realistic 6-task data pipeline (extract → staging → tests → marts → tests → notify)
- Injecting 20+ predefined fault types via the fault injection framework
- Testing DORA against real pipeline failures

See [docker_env/README.md](docker_env/README.md) for setup instructions.

---

## Prompts

All system and user prompts used in DORA are released in `dora/prompts/`:

| File | Purpose |
|------|---------|
| `preclassification.txt` | Stage 1: Error pattern classification rules |
| `query_rewrite.txt` | Stage 2: Multi-query generation |
| `rerank.txt` | Stage 3: LLM listwise reranking |
| `diagnosis_grounded.txt` | Stage 4: Grounded diagnosis (high confidence) |
| `diagnosis_internal.txt` | Stage 4: Internal reasoning (low confidence) |
| `cot_baseline.txt` | CoT baseline prompt |

---

## Citation

If you use DORA or our dataset in your research, please cite:

```
@inproceedings{dora-icde2027,
  title     = {DORA: Error-Aware Retrieval-Augmented Generation for Automated
               Fault Diagnosis in Data Engineering Pipelines},
  author    = {[Authors]},
  booktitle = {ICDE},
  year      = {2027}
}
```

---

## License

For research purposes only.
