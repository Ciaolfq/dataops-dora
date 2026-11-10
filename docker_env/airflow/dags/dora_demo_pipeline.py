"""
DORA Demo Data Pipeline DAG
A complete data pipeline with 6 tasks demonstrating a typical dbt + Airflow workflow.

Tasks:
1. extract_raw_data    - Extract raw data (simulated)
2. dbt_staging         - Run dbt staging models
3. dbt_test_staging    - Run dbt tests on staging
4. dbt_marts           - Run dbt marts models
5. dbt_test_marts      - Run dbt tests on marts
6. notify_success      - Send success notification
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'dora_demo',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

DBT_PROJECT_DIR = '/opt/dbt/dbt_demo'
DBT_PROFILES_DIR = '/opt/dbt'


def extract_raw_data(**context):
    """Simulate extracting data from source systems"""
    print("Extracting raw data from source systems...")
    print("Tables extracted: customers, orders, products, order_items")
    print("Row counts: customers=1000, orders=5000, products=500, order_items=12000")
    return "Extraction completed successfully"


def notify_success(**context):
    """Simulate sending success notification"""
    print("Pipeline completed successfully!")
    print("All models built and tested.")
    return "Notification sent"


with DAG(
    dag_id='dora_demo_pipeline',
    default_args=default_args,
    description='DORA Demo Data Pipeline - dbt + Airflow + PostgreSQL',
    schedule_interval='@daily',
    start_date=days_ago(1),
    catchup=False,
    tags=['dora', 'dbt', 'demo'],
) as dag:

    task_extract = PythonOperator(
        task_id='extract_raw_data',
        python_callable=extract_raw_data,
    )

    task_dbt_staging = BashOperator(
        task_id='dbt_staging',
        bash_command=f'cd {DBT_PROJECT_DIR} && dbt run --models staging --profiles-dir {DBT_PROFILES_DIR}',
    )

    task_dbt_test_staging = BashOperator(
        task_id='dbt_test_staging',
        bash_command=f'cd {DBT_PROJECT_DIR} && dbt test --models staging --profiles-dir {DBT_PROFILES_DIR}',
    )

    task_dbt_marts = BashOperator(
        task_id='dbt_marts',
        bash_command=f'cd {DBT_PROJECT_DIR} && dbt run --models marts --profiles-dir {DBT_PROFILES_DIR}',
    )

    task_dbt_test_marts = BashOperator(
        task_id='dbt_test_marts',
        bash_command=f'cd {DBT_PROJECT_DIR} && dbt test --models marts --profiles-dir {DBT_PROFILES_DIR}',
    )

    task_notify = PythonOperator(
        task_id='notify_success',
        python_callable=notify_success,
    )

    # Task dependencies
    (task_extract
     >> task_dbt_staging
     >> task_dbt_test_staging
     >> task_dbt_marts
     >> task_dbt_test_marts
     >> task_notify)
