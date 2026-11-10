FROM apache/airflow:2.8.1-python3.10

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install dbt and other dependencies
RUN pip install --no-cache-dir \
    dbt-postgres==1.7.10 \
    dbt-core==1.7.10 \
    psycopg2-binary \
    python-dotenv
