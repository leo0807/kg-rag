"""
Airflow DAG: graph_analytics

Runs weekly (Sunday 03:00 UTC). Computes PageRank, Betweenness Centrality,
and community detection for the knowledge graph.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import os

try:
    from airflow import DAG
    from airflow.providers.http.operators.http import SimpleHttpOperator
    from airflow.operators.python import PythonOperator
except ImportError:
    pass

API_KEY = os.getenv("BACKEND_API_KEY", "")

default_args = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

try:
    with DAG(
        dag_id="graph_analytics",
        description="Weekly graph algorithm computation (PageRank, Louvain, Betweenness)",
        schedule="0 3 * * 0",
        start_date=datetime(2026, 1, 1),
        catchup=False,
        default_args=default_args,
        tags=["graph", "analytics", "weekly"],
        max_active_runs=1,
    ) as dag:

        compute_pagerank = SimpleHttpOperator(
            task_id="compute_pagerank",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/pagerank/compute",
            method="POST",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        compute_communities = SimpleHttpOperator(
            task_id="compute_louvain_communities",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/communities/compute",
            method="POST",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        compute_betweenness = SimpleHttpOperator(
            task_id="compute_betweenness",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/betweenness/compute",
            method="POST",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        scan_conflicts = SimpleHttpOperator(
            task_id="scan_constraint_conflicts",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/conflicts",
            method="GET",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        scan_dangling = SimpleHttpOperator(
            task_id="scan_dangling_references",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/scan-dangling",
            method="POST",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        update_community_summaries = SimpleHttpOperator(
            task_id="update_community_summaries",
            http_conn_id="kg_rag_backend",
            endpoint="/api/graph/communities",
            method="GET",
            headers={"X-API-Key": API_KEY},
            dag=dag,
        )

        (compute_pagerank >> compute_communities >>
         compute_betweenness >> scan_conflicts >>
         scan_dangling >> update_community_summaries)

except NameError:
    pass
