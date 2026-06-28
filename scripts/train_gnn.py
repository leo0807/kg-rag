#!/usr/bin/env python3
"""
GNN (GraphSAGE) training script with MLflow tracking.

Trains on the Neo4j knowledge graph to produce structure-aware
node embeddings that supplement text embeddings for retrieval.

Usage:
    pip install mlflow torch torch-geometric neo4j
    python scripts/train_gnn.py \
        --neo4j-uri bolt://localhost:7687 \
        --neo4j-user neo4j \
        --neo4j-password password \
        --epochs 100 \
        --embed-dim 256 \
        --output-model models/gnn_v1.pt

MLflow tracking:
    MLFLOW_TRACKING_URI=http://localhost:5000 python scripts/train_gnn.py ...
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def build_graph_data(neo4j_uri: str, user: str, pwd: str):
    """Extract graph data from Neo4j and build PyG Data object."""
    try:
        from neo4j import GraphDatabase
        import torch
        from torch_geometric.data import Data
    except ImportError:
        log.error("Install: pip install torch torch-geometric neo4j")
        sys.exit(1)

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    node_ids: list[str] = []
    node_features: list[list[float]] = []
    edge_src: list[int] = []
    edge_dst: list[int] = []

    with driver.session() as s:
        # Fetch nodes with embeddings
        result = s.run(
            """
            MATCH (n:Section)
            WHERE n.embedding IS NOT NULL
            RETURN n.chunk_id AS id, n.embedding AS embedding
            LIMIT 50000
            """
        )
        idx_map: dict[str, int] = {}
        for r in result:
            idx = len(node_ids)
            node_ids.append(r["id"])
            idx_map[r["id"]] = idx
            node_features.append(r["embedding"])

        # Fetch edges
        result = s.run(
            """
            MATCH (a:Section)-[]->(b:Section)
            WHERE a.chunk_id IN $ids AND b.chunk_id IN $ids
            RETURN a.chunk_id AS src, b.chunk_id AS dst
            """,
            ids=list(idx_map.keys()),
        )
        for r in result:
            if r["src"] in idx_map and r["dst"] in idx_map:
                edge_src.append(idx_map[r["src"]])
                edge_dst.append(idx_map[r["dst"]])

    driver.close()
    log.info("Graph: %d nodes, %d edges", len(node_ids), len(edge_src))

    if not node_ids:
        log.error("No nodes with embeddings found. Run ingest first.")
        sys.exit(1)

    x = torch.tensor(node_features, dtype=torch.float)
    edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)
    return Data(x=x, edge_index=edge_index), node_ids


def train(data, embed_dim: int = 256, epochs: int = 100,
          lr: float = 1e-3) -> object:
    """Train GraphSAGE encoder."""
    try:
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import GraphSAGE
    except ImportError:
        log.error("Install: pip install torch torch-geometric")
        sys.exit(1)

    in_dim = data.x.size(1)
    model = GraphSAGE(in_dim, hidden_channels=embed_dim,
                      num_layers=2, out_channels=embed_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    model.train()
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        # Self-supervised: reconstruct adjacency (simplified)
        src, dst = data.edge_index
        pos_scores = (out[src] * out[dst]).sum(dim=-1).sigmoid()
        loss = F.binary_cross_entropy(pos_scores, torch.ones_like(pos_scores))
        loss.backward()
        optimizer.step()
        if epoch % 10 == 0:
            log.info("Epoch %d/%d  loss=%.4f", epoch, epochs, loss.item())
            try:
                import mlflow
                mlflow.log_metric("loss", loss.item(), step=epoch)
            except Exception:
                pass

    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--embed-dim", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--output-model", default="models/gnn_v1.pt")
    args = parser.parse_args()

    # MLflow experiment tracking
    try:
        import mlflow
        mlflow.set_experiment("gnn-graphsage")
        mlflow.start_run()
        mlflow.log_params({
            "epochs": args.epochs,
            "embed_dim": args.embed_dim,
            "lr": args.lr,
        })
    except ImportError:
        pass

    data, node_ids = build_graph_data(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    model = train(data, args.embed_dim, args.epochs, args.lr)

    out_path = Path(args.output_model)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import torch
        torch.save({"model_state": model.state_dict(), "node_ids": node_ids,
                    "embed_dim": args.embed_dim}, out_path)
        log.info("Model saved to: %s", out_path)

        import mlflow
        mlflow.pytorch.log_model(model, "gnn-graphsage")
        mlflow.log_artifact(str(out_path))
        mlflow.end_run()
    except Exception as exc:
        log.warning("MLflow save failed: %s", exc)

    print(f"\n✓ GNN training complete. Model: {out_path}")


if __name__ == "__main__":
    main()
