"""
LoRA fine-tuning pipeline for Qwen2.5-7B using LLaMA-Factory.

Usage:
    # Export training data first
    python scripts/export_finetune_data.py --format alpaca --output data/finetune.json

    # Run fine-tuning (requires GPU, LLaMA-Factory installed)
    python scripts/finetune_qwen.py --data data/finetune.json --output output/qwen-cps

    # Instruction-only mode (no GPU needed, prints config)
    python scripts/finetune_qwen.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# LLaMA-Factory fine-tuning config
# ---------------------------------------------------------------------------

LLAMAFACTORY_CONFIG = {
    "model_name_or_path": "Qwen/Qwen2.5-7B-Instruct",
    "stage": "sft",
    "do_train": True,
    "finetuning_type": "lora",
    "lora_target": "q_proj,v_proj",
    "lora_rank": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "dataset_dir": ".",
    "template": "qwen",
    "cutoff_len": 2048,
    "overwrite_cache": True,
    "preprocessing_num_workers": 4,
    "output_dir": "output/qwen-cps",
    "logging_steps": 10,
    "save_steps": 200,
    "plot_loss": True,
    "overwrite_output_dir": True,
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 8,
    "learning_rate": 1e-4,
    "num_train_epochs": 3,
    "lr_scheduler_type": "cosine",
    "warmup_ratio": 0.1,
    "bf16": True,
    "report_to": "none",
}


def _write_dataset_info(data_path: str, dataset_name: str) -> None:
    """Register dataset in LLaMA-Factory's dataset_info.json."""
    info_path = Path("dataset_info.json")
    info: dict = {}
    if info_path.exists():
        info = json.loads(info_path.read_text())
    info[dataset_name] = {
        "file_name": str(data_path),
        "columns": {"prompt": "instruction", "query": "input", "response": "output"},
    }
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    log.info("Registered dataset '%s' in dataset_info.json", dataset_name)


def _run_llamafactory(config: dict) -> int:
    """Launch LLaMA-Factory train via subprocess."""
    config_path = Path("output/_lf_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    cmd = [sys.executable, "-m", "llamafactory.train", str(config_path)]
    log.info("Running: %s", " ".join(cmd))
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# Fallback: Axolotl config
# ---------------------------------------------------------------------------

AXOLOTL_CONFIG_TEMPLATE = """\
base_model: Qwen/Qwen2.5-7B-Instruct
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

load_in_8bit: false
load_in_4bit: true
strict: false

datasets:
  - path: {data_path}
    type: alpaca

dataset_prepared_path: last_run_prepared
val_set_size: 0.05
output_dir: {output_dir}

adapter: lora
lora_r: 8
lora_alpha: 16
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj

sequence_len: 2048
sample_packing: false

gradient_accumulation_steps: 8
micro_batch_size: 2
num_epochs: 3
optimizer: adamw_bnb_8bit
lr_scheduler: cosine
learning_rate: 0.0001

train_on_inputs: false
group_by_length: false
bf16: auto
fp16: false

logging_steps: 10
flash_attention: false

warmup_ratio: 0.1
evals_per_epoch: 1
saves_per_epoch: 1
"""


def _run_axolotl(data_path: str, output_dir: str) -> int:
    """Launch Axolotl training via subprocess."""
    config_path = Path("output/_axolotl_config.yml")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        AXOLOTL_CONFIG_TEMPLATE.format(data_path=data_path, output_dir=output_dir)
    )
    cmd = [sys.executable, "-m", "axolotl.cli.train", str(config_path)]
    log.info("Running: %s", " ".join(cmd))
    return subprocess.call(cmd)


# ---------------------------------------------------------------------------
# MLflow metric logging
# ---------------------------------------------------------------------------

def _try_log_mlflow(run_name: str, params: dict) -> None:
    try:
        import mlflow  # noqa: PLC0415

        mlflow.set_experiment("qwen-cps-finetune")
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(
                {k: v for k, v in params.items() if isinstance(v, (str, int, float, bool))}
            )
            log.info("MLflow run logged: %s", run_name)
    except ImportError:
        log.info("MLflow not installed — skipping metric logging")
    except Exception as exc:
        log.warning("MLflow logging failed: %s", exc)


# ---------------------------------------------------------------------------
# Ollama export guidance
# ---------------------------------------------------------------------------

OLLAMA_GUIDE = """
After fine-tuning, export and deploy with Ollama:

1. Merge LoRA adapters:
   python -c "
   from peft import PeftModel
   from transformers import AutoModelForCausalLM, AutoTokenizer
   base = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-7B-Instruct')
   model = PeftModel.from_pretrained(base, '{output_dir}')
   model = model.merge_and_unload()
   model.save_pretrained('{output_dir}-merged')
   AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct').save_pretrained('{output_dir}-merged')
   "

2. Convert to GGUF (requires llama.cpp):
   python llama.cpp/convert_hf_to_gguf.py {output_dir}-merged \\
     --outfile {output_dir}-merged/model.gguf --outtype q4_k_m

3. Create Modelfile:
   cat > Modelfile << 'EOF'
   FROM {output_dir}-merged/model.gguf
   SYSTEM "你是航空工艺知识助手，专注于 CPS 规范问答。"
   EOF

4. Import into Ollama:
   ollama create qwen-cps -f Modelfile

5. Update .env:
   LLM_MODEL=qwen-cps
   LLM_BASE_URL=http://localhost:11434/v1
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune Qwen2.5-7B on CPS QA data")
    parser.add_argument("--data", default="data/finetune.json", help="Path to Alpaca-format JSON")
    parser.add_argument("--output", default="output/qwen-cps", help="Output directory")
    parser.add_argument(
        "--backend",
        choices=["llamafactory", "axolotl", "auto"],
        default="auto",
        help="Training backend",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    args = parser.parse_args()

    output_dir = args.output

    if args.dry_run:
        print("=== LLaMA-Factory config ===")
        print(json.dumps({**LLAMAFACTORY_CONFIG, "output_dir": output_dir}, indent=2))
        print("\n=== Axolotl config ===")
        print(AXOLOTL_CONFIG_TEMPLATE.format(data_path=args.data, output_dir=output_dir))
        print("\n=== Ollama deployment guide ===")
        print(OLLAMA_GUIDE.format(output_dir=output_dir))
        return

    if not Path(args.data).exists():
        log.error("Training data not found: %s", args.data)
        log.error("Run: python scripts/export_finetune_data.py --format alpaca --output %s", args.data)
        sys.exit(1)

    _try_log_mlflow(
        run_name=f"qwen-cps-lora",
        params={**LLAMAFACTORY_CONFIG, "data_path": args.data, "output_dir": output_dir},
    )

    # Detect backend
    backend = args.backend
    if backend == "auto":
        try:
            import llamafactory  # noqa: F401
            backend = "llamafactory"
        except ImportError:
            pass
        if backend == "auto":
            try:
                import axolotl  # noqa: F401
                backend = "axolotl"
            except ImportError:
                pass

    if backend == "auto":
        log.error("No training backend found. Install one of:")
        log.error("  pip install llamafactory")
        log.error("  pip install axolotl")
        log.error("\nOr run with --dry-run to see the config.")
        sys.exit(1)

    if backend == "llamafactory":
        dataset_name = "cps_finetune"
        _write_dataset_info(args.data, dataset_name)
        config = {
            **LLAMAFACTORY_CONFIG,
            "dataset": dataset_name,
            "output_dir": output_dir,
        }
        rc = _run_llamafactory(config)
    else:
        rc = _run_axolotl(args.data, output_dir)

    if rc == 0:
        log.info("Training complete. Output: %s", output_dir)
        log.info(OLLAMA_GUIDE.format(output_dir=output_dir))
    else:
        log.error("Training failed with exit code %d", rc)
        sys.exit(rc)


if __name__ == "__main__":
    main()
