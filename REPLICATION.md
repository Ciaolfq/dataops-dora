# DORA Replication Guide

This document provides step-by-step instructions to reproduce the experiments reported in the DORA paper (ICDE 2027).

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Knowledge Base Preparation](#2-knowledge-base-preparation)
3. [Dataset Preparation](#3-dataset-preparation)
4. [Running Baselines](#4-running-baselines)
5. [Running DORA (Full System)](#5-running-dora-full-system)
6. [Ablation Study](#6-ablation-study)
7. [Result Analysis](#7-result-analysis)
8. [Reproducing Figures and Tables](#8-reproducing-figures-and-tables)
9. [Docker Environment (Optional)](#9-docker-environment-optional)

---

## 1. Environment Setup

### 1.1 Hardware Requirements

- **GPU**: NVIDIA GPU with 8GB+ VRAM (for Cross-Encoder reranking)
- **CPU**: 4+ cores
- **RAM**: 16GB+
- **Storage**: 10GB+ free space

### 1.2 Software Requirements

- Python 3.9+
- pip
- (Optional) Docker + Docker Compose (for fault injection experiments)

### 1.3 Install Dependencies

```bash
# Clone or download the ICDE-2027 package
cd ICDE-2027

# Install Python dependencies
pip install -r requirements.txt
```

### 1.4 Configure API Keys

DORA uses an LLM API for diagnosis. We recommend DeepSeek API, but any OpenAI-compatible API will work.

```bash
# Option 1: Environment variable (recommended)
export DEEPSEEK_API_KEY="your-api-key-here"

# Option 2: Edit the config file
# Open dora/config/settings.yaml and set api_key
```

**Supported LLM Providers:**
- DeepSeek (default)
- Qwen / Tongyi Qianwen
- AIHubMix Claude
- Any OpenAI-compatible API

---

## 2. Knowledge Base Preparation

### 2.1 Build Vector Database

```bash
cd dora

# Build from sample knowledge base (50 entries)
python -m data.vector_builder \
    --input data/knowledge_base_sample.json \
    --output chroma_db/ \
    --collection-name dora_knowledge_base
```

### 2.2 (Optional) Build Full Knowledge Base

If you have the full knowledge base:

```bash
python -m data.vector_builder \
    --input /path/to/full_knowledge_base.json \
    --output chroma_db/ \
    --collection-name dora_knowledge_base \
    --embedding-model all-MiniLM-L6-v2
```

### 2.3 Verify Knowledge Base

```bash
python -c "
from dora.core.retrieval.chroma_retrieval import ChromaRetriever
retriever = ChromaRetriever(persist_dir='chroma_db', collection_name='dora_knowledge_base')
print(f'Knowledge base size: {retriever.count()} entries')
"
```

Expected output: Knowledge base size should match the number of entries in your input file.

---

## 3. Dataset Preparation

The evaluation dataset is provided at `evaluation/data/fault_dataset_100.json`.

### 3.1 Dataset Format

Each fault case contains:
```json
{
  "fault_id": "FAULT-001",
  "category": "configuration_error",
  "subcategory": "Config/Settings",
  "title": "dbt_project.yml materialized typo",
  "error_log": "...full error log text...",
  "root_cause": "Root cause description...",
  "fix_steps": ["Step 1...", "Step 2..."],
  "severity": "high",
  "source": "dbt",
  "difficulty": 1
}
```

### 3.2 Dataset Statistics

| Category | Count |
|----------|-------|
| configuration_error | 10 |
| dependency_issue | 9 |
| permission_error | 9 |
| syntax_error | 9 |
| network_issue | 9 |
| resource_exhaustion | 9 |
| data_quality | 9 |
| schema_mismatch | 9 |
| runtime_error | 9 |
| concurrency_issue | 9 |
| operation_error | 9 |
| **Total** | **100** |

---

## 4. Running Baselines

### 4.1 B1: Rule-Based (Regex Matching)

```bash
cd evaluation/baselines

python run_rule_based.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/rule_based_results.json
```

This baseline uses 20+ predefined regex rules to match error patterns and classify faults.

### 4.2 B2: Chain-of-Thought (CoT)

```bash
python run_cot.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/cot_results.json \
    --model deepseek-chat \
    --temperature 0.7
```

This baseline uses standard CoT prompting to diagnose faults directly from error logs.

### 4.3 B3: Self-Consistency

```bash
python run_self_consistency.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/self_consistency_results.json \
    --model deepseek-chat \
    --num-samples 5 \
    --temperature 0.7
```

This baseline generates multiple CoT responses and uses majority voting to determine the final answer.

### 4.4 B4: Cross-Encoder RAG

```bash
python run_cross_encoder_rag.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/cross_encoder_rag_results.json \
    --model deepseek-chat \
    --top-k 10 \
    --reranker cross-encoder/ms-marco-MiniLM-L-6-v2
```

This baseline uses dense retrieval + Cross-Encoder reranking + LLM generation.

### 4.5 B5: ReAct RAG

```bash
python run_react_rag.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/react_rag_results.json \
    --model deepseek-chat \
    --max-rounds 3 \
    --top-k 5
```

This baseline implements ReAct-style reasoning with iterative retrieval (3 rounds).

### 4.6 B6: DORA (Our Method)

```bash
python run_dora.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/dora_results.json \
    --model deepseek-chat \
    --top-k 10
```

This is the full DORA system with error-aware pre-classification, query rewriting, multi-path retrieval, and Cross-Encoder reranking.

---

## 5. Running DORA (Full System)

### 5.1 Single Fault Diagnosis

```bash
cd dora

python main.py \
    --error-log "path/to/error.log" \
    --config config/settings.yaml \
    --output diagnosis_result.json
```

### 5.2 Batch Evaluation

```bash
cd evaluation/baselines

python run_dora.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/dora_results.json \
    --model deepseek-chat \
    --top-k 10 \
    --rewrite true \
    --rerank true
```

### 5.3 DORA Configuration

Key parameters in `dora/config/settings.yaml`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `llm.provider` | deepseek | LLM provider |
| `llm.model` | deepseek-chat | Model name |
| `llm.temperature` | 0.1 | Sampling temperature |
| `retrieval.top_k` | 10 | Number of retrieved documents |
| `rewrite.enabled` | true | Enable query rewriting |
| `rerank.enabled` | true | Enable Cross-Encoder reranking |
| `rerank.top_k` | 5 | Number of documents after reranking |

---

## 6. Ablation Study

To reproduce the ablation study results, run DORA with different components disabled:

### 6.1 Full DORA (Baseline)

```bash
python run_dora.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/ablation_full/ \
    --rewrite --rerank
```

### 6.2 w/o Query Rewrite

```bash
python run_dora.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/ablation_no_rewrite/ \
    --no-rewrite --rerank
```

### 6.3 w/o Cross-Encoder Rerank

```bash
python run_dora.py \
    --dataset ../data/fault_dataset_100.json \
    --output ../results/ablation_no_rerank/ \
    --rewrite --no-rerank
```

### 6.4 Analyze Ablation Results

```bash
cd evaluation/analysis

python ablation_analysis.py \
    --full ../results/ablation_full/ \
    --no-rewrite ../results/ablation_no_rewrite/ \
    --no-rerank ../results/ablation_no_rerank/ \
    --output ../results/ablation_analysis.json
```

---

## 7. Result Analysis

### 7.1 Calculate Core Metrics

```bash
cd evaluation/analysis

python calculate_metrics.py \
    --results ../results/ \
    --output ../results/metrics_summary.json
```

This computes:
- **RCHR (Root Cause Hit Rate)**: Top-1 accuracy
- **AV (Answer Validity)**: Fix step quality score
- **MTTR (Mean Time To Repair)**: Estimated repair time

### 7.2 Category Analysis

```bash
python category_analysis.py \
    --results ../results/ \
    --output ../results/category_analysis.json
```

This breaks down performance by fault category.

### 7.3 Supplementary Analysis

```bash
python supplementary_analysis.py \
    --results ../results/ \
    --output ../results/supplementary_analysis.json
```

This includes:
- Inference time analysis
- Error case analysis
- Difficulty correlation analysis

---

## 8. Reproducing Figures and Tables

### 8.1 Table 1: Main Results (RCHR / AV)

```bash
python evaluation/analysis/calculate_metrics.py --results evaluation/results/
```

Use the output to populate Table 1. Sort by RCHR descending.

### 8.2 Figure 2: Main Results Bar Chart

Use the `main_results.png` figure in the `figures/` directory, or regenerate:

```python
import json
import matplotlib.pyplot as plt

with open('evaluation/results/metrics_summary.json') as f:
    data = json.load(f)

systems = list(data.keys())
rchr = [data[s]['rchr'] * 100 for s in systems]

plt.figure(figsize=(10, 6))
bars = plt.bar(systems, rchr, color=['#888', '#888', '#888', '#888', '#888', '#e74c3c'])
plt.ylabel('RCHR (%)')
plt.title('Root Cause Hit Rate Comparison')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('figures/main_results.png', dpi=300)
```

### 8.3 Figure 3: Category Comparison

```bash
python evaluation/analysis/category_analysis.py --results evaluation/results/
```

Use the `category_analysis.json` output to create the grouped bar chart.

### 8.4 Figure 4: Ablation Study

```bash
python evaluation/analysis/ablation_analysis.py \
    --full evaluation/results/ablation_full/ \
    --no-rewrite evaluation/results/ablation_no_rewrite/ \
    --no-rerank evaluation/results/ablation_no_rerank/
```

### 8.5 Table 2: Per-Category Breakdown

Use the `category_analysis.json` output to create the per-category accuracy table.

---

## 9. Docker Environment (Optional)

For end-to-end fault injection experiments with real dbt + Airflow pipelines:

### 9.1 Start Environment

```bash
cd docker_env

# Initialize (first run only)
docker-compose up airflow-init

# Start all services
docker-compose up -d
```

### 9.2 Access Airflow UI

- URL: http://localhost:8080
- Username: admin
- Password: admin

### 9.3 Run Baseline Pipeline

1. Open Airflow UI
2. Find `dora_demo_pipeline` DAG
3. Toggle it on and trigger a run
4. Verify all 6 tasks complete successfully

### 9.4 Inject Faults

```bash
cd docker_env/fault_injection

# List available faults
python inject_fault.py

# Inject a specific fault
python inject_fault.py DEF-01

# Reset after experiment
python inject_fault.py DEF-01 --reset
```

### 9.5 Collect Error Logs

After injecting a fault and triggering the pipeline:
1. Check Airflow task logs for error messages
2. Copy error logs to a text file
3. Run DORA diagnosis on the error log

---

## Expected Results

When running with DeepSeek Chat model and the provided dataset, you should expect results approximately:

| System | RCHR (Top-1) | AV |
|--------|-------------|-----|
| Rule-based | ~35-40% | ~0.45 |
| CoT | ~50-55% | ~0.60 |
| Self-Consistency | ~55-60% | ~0.62 |
| Cross-Encoder RAG | ~65-70% | ~0.72 |
| ReAct RAG | ~68-73% | ~0.75 |
| **DORA (Ours)** | **~78-85%** | **~0.85** |

*Note: Exact results may vary slightly due to LLM stochasticity and API version differences.*

---

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure `DEEPSEEK_API_KEY` environment variable is set
2. **ChromaDB Import Error**: Run `pip install chromadb`
3. **Cross-Encoder Model Download**: First run may take time to download the model
4. **Out of Memory**: Reduce `--top-k` or use a smaller reranker model

### Support

For issues with replication, please refer to the paper or contact the authors.

---

## References

- DORA Paper: [ICDE 2027] "DORA: Error-Aware Retrieval-Augmented Generation for DataOps Fault Diagnosis"
- DeepSeek API: https://platform.deepseek.com/
- dbt: https://www.getdbt.com/
- Apache Airflow: https://airflow.apache.org/
