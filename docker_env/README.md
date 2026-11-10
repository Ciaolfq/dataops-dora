# DORA Experiment Environment Setup

## Overview

Docker-based experimental environment for DORA (Error-Aware RAG for DataOps Fault Diagnosis).

## Stack

- **Apache Airflow 2.8.1** - Pipeline orchestration
- **dbt-core 1.7.10** - Data transformation
- **PostgreSQL 15** - Data warehouse + metadata database

## Quick Start

### 1. Start Environment

```bash
cd docker_env
docker-compose up -d
```

### 2. Initialize Airflow (First Run)

```bash
docker-compose up airflow-init
```

### 3. Access Airflow UI

- URL: http://localhost:8080
- Username: admin
- Password: admin

### 4. Run the Pipeline

1. Go to Airflow UI
2. Find `dora_demo_pipeline` DAG
3. Toggle it on and trigger a run
4. Verify all 6 tasks complete successfully

## Pipeline Structure (6 Tasks)

```
extract_raw_data -> dbt_staging -> dbt_test_staging -> dbt_marts -> dbt_test_marts -> notify_success
```

### Models

**Staging (views):**
- stg_customers
- stg_orders
- stg_products
- stg_order_items

**Marts (tables):**
- dim_customers
- fct_order_summary

## Fault Injection

### Inject a Fault

```bash
# List available faults
python fault_injection/inject_fault.py

# Inject specific fault
python fault_injection/inject_fault.py DEF-01

# Reset after experiment
python fault_injection/inject_fault.py DEF-01 --reset
```

## Fault Definitions

20 predefined fault definitions across 3 categories:

| Category | Subcategory | Count |
|----------|-------------|-------|
| Definition | Config | 3 |
| Definition | Syntax | 3 |
| Definition | Dependency | 2 |
| Data | Schema | 1 |
| Data | Type | 1 |
| Data | Quality | 3 |
| Execution | Permission | 1 |
| Execution | Performance | 1 |
| Execution | Concurrency | 1 |
| Execution | Resource | 1 |
| Execution | Dependency | 1 |

## Directory Structure

```
docker_env/
├── docker-compose.yml          # Docker Compose configuration
├── README.md                   # This file
├── airflow/                    # Airflow service
│   ├── Dockerfile
│   └── dags/
│       └── dora_demo_pipeline.py
├── dbt/                        # dbt project
│   └── dbt_project/
│       ├── dbt_project.yml
│       ├── profiles.yml
│       └── models/
│           ├── staging/
│           └── marts/
├── postgres/                   # PostgreSQL
│   └── init/
│       └── 01_init_dbt.sql
└── fault_injection/            # Fault injection tools
    ├── fault_definitions.json
    └── inject_fault.py
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Airflow Webserver | 8080 | Airflow UI |
| PostgreSQL | 5432 | Metadata + data warehouse |

## Cleanup

```bash
# Stop services
docker-compose down

# Stop and remove volumes (full reset)
docker-compose down -v
```
