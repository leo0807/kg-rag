"""
Airflow DAG: pdf_ingest_pipeline

Runs daily at 02:00 UTC. Pulls new documents from PLM,
ingests them into the knowledge base with idempotency guarantees.

Requirements:
    pip install apache-airflow apache-airflow-providers-http
"""
from __future__ import annotations

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.providers.http.operators.http import SimpleHttpOperator
    from airflow.operators.bash import BashOperator
except ImportError:
    # Allow module import without Airflow installed
    pass

import json
import logging
import os

log = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://kg-rag-backend:8000")
API_KEY = os.getenv("BACKEND_API_KEY", "")
PLM_TYPE = os.getenv("PLM_TYPE", "teamcenter")
PLM_URL = os.getenv("PLM_URL", "")
PLM_TOKEN = os.getenv("PLM_TOKEN", "")

default_args = {
    "owner": "data-team",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": True,
    "email": ["dataops@aviation.corp"],
}

try:
    with DAG(
        dag_id="pdf_ingest_pipeline",
        description="Daily PLM document sync and knowledge base ingest",
        schedule="0 2 * * *",
        start_date=datetime(2026, 1, 1),
        catchup=False,
        default_args=default_args,
        tags=["ingest", "plm", "knowledge-base"],
        max_active_runs=1,
    ) as dag:

        scan_plm = BashOperator(
            task_id="scan_plm_documents",
            bash_command=(
                "python /opt/airflow/dags/../../scripts/plm_sync.py "
                f"--plm-type {PLM_TYPE} "
                f"--plm-url {PLM_URL} "
                f"--plm-token {PLM_TOKEN} "
                f"--backend-url {BACKEND_URL} "
                f"--api-key {API_KEY} "
                "--lookback-hours 25"
            ),
        )

        trigger_graph_update = SimpleHttpOperator(
            task_id="trigger_graph_analytics",
            http_conn_id="kg_rag_backend",
            endpoint="/api/admin/graph/analytics/refresh",
            method="POST",
            headers={"X-API-Key": API_KEY},
            response_check=lambda r: r.status_code == 200,
            dag=dag,
        )

        update_community_summaries = SimpleHttpOperator(
            task_id="update_community_summaries",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/communities/compute",
            method="POST",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        health_check = SimpleHttpOperator(
            task_id="graph_health_check",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/health",
            method="GET",
            headers={"X-API-Key": API_KEY},
            response_check=lambda r: r.json().get("health_score", 0) >= 50,
            dag=dag,
        )

        scan_plm >> trigger_graph_update >> update_community_summaries >> health_check

except NameError:
    # DAG not registered when Airflow is not installed
    pass
