#!/usr/bin/env python3
"""
DSPy prompt optimization for entity extraction.

Uses DSPy ChainOfThought with annotated samples to auto-optimize
the entity extraction prompt. Outputs the best prompt to
config/prompts/entity.json.

Usage:
    pip install dspy-ai
    python scripts/dspy_optimize_entity.py \
        --samples-file scripts/eval/entity_samples.json \
        --llm-model gpt-4o-mini \
        --output config/prompts/entity.json

Sample format (entity_samples.json):
    [
      {
        "text": "使用扭矩扳手将液压管接头拧紧至 35 N·m",
        "entities": {
          "Tool": ["扭矩扳手"],
          "Material": ["液压管接头"],
          "Process": ["拧紧"],
          "Constraint": [{"parameter": "力矩", "value": "35", "unit": "N·m"}]
        }
      }
    ]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def run_dspy_optimize(samples_file: str, llm_model: str, output: str,
                      n_trials: int = 20) -> None:
    try:
        import dspy
    except ImportError:
        print("dspy-ai not installed. Run: pip install dspy-ai")
        return

    with open(samples_file) as f:
        samples = json.load(f)

    # Configure DSPy LLM
    api_key = os.getenv("OPENAI_API_KEY", "")
    lm = dspy.OpenAI(model=llm_model, api_key=api_key, max_tokens=1024)
    dspy.settings.configure(lm=lm)

    # Define the extraction signature
    class EntityExtraction(dspy.Signature):
        """
        Extract structured entities from Chinese aerospace procedure text.
        Return JSON with keys: Tool, Material, Process, Constraint.
        Each Constraint has: parameter, value, unit.
        """
        text: str = dspy.InputField(desc="Procedure text to extract from")
        entities_json: str = dspy.OutputField(desc="JSON string with extracted entities")

    class EntityExtractor(dspy.Module):
        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(EntityExtraction)

        def forward(self, text: str):
            return self.predict(text=text)

    # Build trainset
    trainset = []
    for s in samples:
        trainset.append(
            dspy.Example(
                text=s["text"],
                entities_json=json.dumps(s["entities"], ensure_ascii=False),
            ).with_inputs("text")
        )

    # Metric: JSON parse success + key overlap
    def metric(example, prediction, trace=None):
        try:
            predicted = json.loads(prediction.entities_json)
            expected = example.entities_json if isinstance(
                example.entities_json, dict) else json.loads(example.entities_json)
            overlap = sum(
                1 for k in expected if k in predicted and predicted[k]
            ) / max(len(expected), 1)
            return overlap
        except Exception:
            return 0.0

    # Optimize with BootstrapFewShot
    from dspy.teleprompt import BootstrapFewShot
    optimizer = BootstrapFewShot(metric=metric, max_bootstrapped_demos=4,
                                  max_labeled_demos=4)
    extractor = EntityExtractor()
    optimized = optimizer.compile(extractor, trainset=trainset[:n_trials])

    # Save optimized prompt
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    optimized_prompt = {
        "model": llm_model,
        "optimized_at": __import__("datetime").datetime.utcnow().isoformat(),
        "system_prompt": lm.history[-1]["prompt"] if lm.history else "",
        "demos": [
            {"text": ex.text, "entities_json": ex.entities_json}
            for ex in (optimized.predict.demos or [])
        ],
    }
    with open(out_path, "w") as f:
        json.dump(optimized_prompt, f, indent=2, ensure_ascii=False)
    print(f"Optimized prompt saved to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-file", default="scripts/eval/entity_samples.json")
    parser.add_argument("--llm-model", default="gpt-4o-mini")
    parser.add_argument("--output", default="config/prompts/entity.json")
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()
    run_dspy_optimize(args.samples_file, args.llm_model, args.output, args.trials)


if __name__ == "__main__":
    main()
