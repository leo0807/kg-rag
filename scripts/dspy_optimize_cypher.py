#!/usr/bin/env python3
"""
DSPy prompt optimization for Text2Cypher generation.

Optimizes the prompt that translates natural language questions
into Cypher queries, using graph execution success as feedback.

Usage:
    pip install dspy-ai neo4j
    python scripts/dspy_optimize_cypher.py \
        --samples-file scripts/eval/cypher_samples.json \
        --neo4j-uri bolt://localhost:7687 \
        --neo4j-user neo4j \
        --neo4j-password password \
        --output config/prompts/cypher.json

Sample format:
    [{"question": "哪些章节涉及液压接头安装?",
      "cypher": "MATCH (s:Section) WHERE s.content CONTAINS '液压接头' RETURN s"}]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def run_cypher_optimize(samples_file: str, neo4j_uri: str, neo4j_user: str,
                         neo4j_pwd: str, output: str, n_trials: int = 20) -> None:
    try:
        import dspy
        from neo4j import GraphDatabase
    except ImportError:
        print("Install: pip install dspy-ai neo4j")
        return

    with open(samples_file) as f:
        samples = json.load(f)

    api_key = os.getenv("OPENAI_API_KEY", "")
    lm = dspy.OpenAI(model="gpt-4o-mini", api_key=api_key, max_tokens=512)
    dspy.settings.configure(lm=lm)

    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pwd))

    class Text2Cypher(dspy.Signature):
        """
        Translate a natural language question about aerospace documents
        into a valid Neo4j Cypher query. Return only the Cypher query, no explanation.
        Graph schema: Document, Section, Tool, Material, Process, Constraint, Hazard nodes.
        Common relations: HAS_SECTION, NEXT_SECTION, REQUIRES_TOOL, USES_MATERIAL,
        HAS_CONSTRAINT, WARNS_OF, REFERENCES, SIMILAR_TO.
        """
        question: str = dspy.InputField()
        cypher: str = dspy.OutputField(desc="Valid Cypher query")

    class CypherGenerator(dspy.Module):
        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(Text2Cypher)

        def forward(self, question: str):
            return self.predict(question=question)

    def can_execute(cypher: str) -> bool:
        """Return True if the Cypher can be parsed and executed."""
        try:
            with neo4j_driver.session() as s:
                s.run(f"EXPLAIN {cypher}")
            return True
        except Exception:
            return False

    def metric(example, prediction, trace=None):
        return 1.0 if can_execute(prediction.cypher) else 0.0

    trainset = [
        dspy.Example(question=s["question"], cypher=s["cypher"]).with_inputs("question")
        for s in samples
    ]

    from dspy.teleprompt import BootstrapFewShot
    optimizer = BootstrapFewShot(metric=metric, max_bootstrapped_demos=4)
    gen = CypherGenerator()
    optimized = optimizer.compile(gen, trainset=trainset[:n_trials])

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "optimized_at": __import__("datetime").datetime.utcnow().isoformat(),
        "demos": [
            {"question": ex.question, "cypher": ex.cypher}
            for ex in (optimized.predict.demos or [])
        ],
    }
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Optimized Text2Cypher prompt saved to: {out_path}")
    neo4j_driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-file", default="scripts/eval/cypher_samples.json")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--output", default="config/prompts/cypher.json")
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()
    run_cypher_optimize(
        args.samples_file, args.neo4j_uri, args.neo4j_user,
        args.neo4j_password, args.output, args.trials,
    )


if __name__ == "__main__":
    main()
