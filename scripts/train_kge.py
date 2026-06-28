#!/usr/bin/env python3
"""
Knowledge Graph Embedding (KGE) training with PyKEEN.
Trains TransE/RotatE for link prediction (predicting missing relations).

Usage:
    pip install pykeen
    python scripts/train_kge.py \
        --neo4j-uri bolt://localhost:7687 \
        --model RotatE \
        --epochs 100 \
        --threshold 0.8

Outputs candidate relations with confidence > threshold to stdout.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def export_triples(neo4j_uri: str, user: str, pwd: str) -> list[tuple[str, str, str]]:
    """Export (head, relation, tail) triples from Neo4j."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        log.error("pip install neo4j")
        sys.exit(1)

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    triples: list[tuple[str, str, str]] = []

    relation_queries = [
        ("MATCH (a:Section)-[r:NEXT_SECTION]->(b:Section) RETURN a.chunk_id, type(r), b.chunk_id", "Section", "Section"),
        ("MATCH (s:Section)-[r:HAS_CONSTRAINT]->(c:Constraint) RETURN s.chunk_id, type(r), c.chunk_id", "Section", "Constraint"),
        ("MATCH (s:Section)-[r:REQUIRES_TOOL]->(t:Tool) RETURN s.chunk_id, type(r), t.name", "Section", "Tool"),
        ("MATCH (s:Section)-[r:USES_MATERIAL]->(m:Material) RETURN s.chunk_id, type(r), m.name", "Section", "Material"),
        ("MATCH (a:Document)-[r:REFERENCES]->(b:Document) RETURN a.name, type(r), b.name", "Document", "Document"),
        ("MATCH (a:Document)-[r:SUPERSEDES]->(b:Document) RETURN a.name, type(r), b.name", "Document", "Document"),
        ("MATCH (s:Section)-[r:WARNS_OF]->(h:Hazard) RETURN s.chunk_id, type(r), h.hazard_id", "Section", "Hazard"),
    ]

    with driver.session() as sess:
        for cypher, _, _ in relation_queries:
            result = sess.run(cypher)
            for row in result:
                vals = list(row.values())
                if len(vals) >= 3 and all(v for v in vals):
                    triples.append((str(vals[0]), str(vals[1]), str(vals[2])))

    driver.close()
    log.info("Exported %d triples", len(triples))
    return triples


def train_kge(triples: list[tuple[str, str, str]], model_name: str = "RotatE",
               epochs: int = 100, embedding_dim: int = 128) -> object | None:
    """Train KGE model with PyKEEN."""
    try:
        from pykeen.triples import TriplesFactory
        from pykeen.pipeline import pipeline
    except ImportError:
        log.error("pip install pykeen")
        return None

    if not triples:
        log.error("No triples found")
        return None

    tf = TriplesFactory.from_labeled_triples(
        triples=[(h, r, t) for h, r, t in triples],
        create_inverse_triples=True,
    )
    training, testing = tf.split([0.8, 0.2])

    result = pipeline(
        training=training,
        testing=testing,
        model=model_name,
        model_kwargs={"embedding_dim": embedding_dim},
        training_kwargs={"num_epochs": epochs},
        random_seed=42,
    )
    return result


def predict_missing_relations(result, threshold: float = 0.8,
                               top_k: int = 50) -> list[dict]:
    """Return high-confidence predicted missing relations."""
    if result is None:
        return []
    try:
        from pykeen.models import predict
        df = result.model.get_all_prediction_df(
            triples_factory=result.training,
            add_novelties=True,
        )
        df_novel = df[df["in_training"] == False]  # noqa: E712
        df_high = df_novel[df_novel["score"] >= threshold].head(top_k)
        return df_high.to_dict(orient="records")
    except Exception as exc:
        log.warning("Prediction failed: %s", exc)
        return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--model", default="RotatE",
                        choices=["TransE", "RotatE", "ComplEx"])
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output-dir", default="models/kge")
    args = parser.parse_args()

    triples = export_triples(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    result = train_kge(triples, args.model, args.epochs, args.embed_dim)

    if result is None:
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.save_to_directory(str(out_dir))
    log.info("Model saved to: %s", out_dir)

    candidates = predict_missing_relations(result, args.threshold)
    print(f"\n✓ {args.model} training complete")
    print(f"  Triples: {len(triples)}")
    print(f"  High-confidence predictions (>{args.threshold}): {len(candidates)}")
    for c in candidates[:10]:
        print(f"  [{c.get('score', 0):.3f}] {c.get('head_label')} "
              f"--{c.get('relation_label')}--> {c.get('tail_label')}")


if __name__ == "__main__":
    main()
