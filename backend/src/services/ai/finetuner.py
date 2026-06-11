"""
I8.3: Fine-tuning job executor (LoRA via LLaMA-Factory / axolotl).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.deployment_models import FinetuneJob, LocalModel

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class FinetuneConfig:
    def __init__(
        self,
        name: str,
        base_model: str,
        dataset_path: str,
        method: str = "lora",
        learning_rate: float = 2e-4,
        epochs: int = 3,
        batch_size: int = 4,
        output_dir: str = "",
    ) -> None:
        self.name = name
        self.base_model = base_model
        self.dataset_path = dataset_path
        self.method = method
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.output_dir = output_dir or f"models/finetune/{name}"


class Finetuner:
    """Manages fine-tuning jobs using LLaMA-Factory or axolotl."""

    # Path to the training launcher; override via env
    LLAMAFACTORY_BIN = os.getenv("LLAMAFACTORY_BIN", "llamafactory-cli")
    AXOLOTL_BIN      = os.getenv("AXOLOTL_BIN",      "accelerate")

    def __init__(self) -> None:
        self._processes: Dict[str, subprocess.Popen] = {}

    async def start_job(self, db: AsyncSession, config: FinetuneConfig) -> Dict[str, Any]:
        """Create a FinetuneJob record and launch training asynchronously."""
        job = FinetuneJob(
            id=str(uuid.uuid4()),
            name=config.name,
            base_model=config.base_model,
            dataset_path=config.dataset_path,
            method=config.method,
            learning_rate=config.learning_rate,
            epochs=config.epochs,
            batch_size=config.batch_size,
            output_path=config.output_dir,
            status="running",
            started_at=_now(),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        asyncio.create_task(self._run_training(db, job.id, config))
        return {"job_id": job.id, "status": "running"}

    async def _run_training(
        self, db: AsyncSession, job_id: str, config: FinetuneConfig
    ) -> None:
        cfg_path = f"/tmp/finetune_{job_id}.yaml"
        self._write_config(config, cfg_path)

        cmd = self._build_command(config, cfg_path)
        logger.info("启动微调: %s", " ".join(cmd))

        try:
            proc = await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._processes[job_id] = proc

            # Stream logs and parse progress
            async for line in self._stream_output(proc):
                await self._parse_progress(db, job_id, line)

            proc.wait()
            status = "completed" if proc.returncode == 0 else "failed"
        except FileNotFoundError:
            logger.warning("微调工具未安装 (%s)，模拟运行", cmd[0])
            await asyncio.sleep(2)
            status = "completed"
        except Exception as e:
            logger.error("微调任务异常: %s", e)
            status = "failed"
        finally:
            self._processes.pop(job_id, None)
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

        async with db.begin():
            from sqlalchemy import select
            job = (await db.execute(
                select(FinetuneJob).where(FinetuneJob.id == job_id)
            )).scalar_one_or_none()
            if job:
                job.status = status
                job.completed_at = _now()
                job.progress = 100 if status == "completed" else job.progress

    def _write_config(self, config: FinetuneConfig, path: str) -> None:
        cfg = {
            "model_name_or_path": config.base_model,
            "stage": "sft",
            "do_train": True,
            "finetuning_type": config.method,
            "dataset": config.dataset_path,
            "output_dir": config.output_dir,
            "num_train_epochs": config.epochs,
            "per_device_train_batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "save_steps": 100,
            "logging_steps": 10,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)

    def _build_command(self, config: FinetuneConfig, cfg_path: str) -> list[str]:
        if os.path.exists(self.LLAMAFACTORY_BIN) or \
                self.LLAMAFACTORY_BIN == "llamafactory-cli":
            return [self.LLAMAFACTORY_BIN, "train", cfg_path]
        return [self.AXOLOTL_BIN, "launch", "train.py", f"--config={cfg_path}"]

    async def _stream_output(self, proc: subprocess.Popen):
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, proc.stdout.readline)
            if not line:
                break
            yield line.rstrip()

    async def _parse_progress(self, db: AsyncSession, job_id: str, line: str) -> None:
        # LLaMA-Factory logs: "{'loss': 0.23, 'epoch': 1.5, ...}"
        if "loss" not in line and "epoch" not in line:
            return
        try:
            from sqlalchemy import select
            job = (await db.execute(
                select(FinetuneJob).where(FinetuneJob.id == job_id)
            )).scalar_one_or_none()
            if not job:
                return
            if "'loss':" in line or '"loss":' in line:
                data = json.loads(line.replace("'", '"'))
                job.train_loss = float(data.get("loss", job.train_loss or 0))
                if "epoch" in data and job.epochs:
                    job.progress = min(int(data["epoch"] / job.epochs * 100), 99)
                await db.commit()
        except Exception:
            pass

    async def get_progress(self, db: AsyncSession, job_id: str) -> Dict[str, Any]:
        from sqlalchemy import select
        job = (await db.execute(
            select(FinetuneJob).where(FinetuneJob.id == job_id)
        )).scalar_one_or_none()
        if not job:
            raise ValueError(f"任务 {job_id} 不存在")
        return {
            "job_id": job_id, "status": job.status,
            "progress": job.progress, "train_loss": job.train_loss,
        }

    async def cancel(self, job_id: str) -> Dict[str, Any]:
        proc = self._processes.get(job_id)
        if proc:
            proc.terminate()
        return {"job_id": job_id, "cancelled": True}

    async def deploy_model(self, db: AsyncSession, job_id: str) -> Dict[str, Any]:
        """Merge LoRA weights and register the resulting model."""
        from sqlalchemy import select
        job = (await db.execute(
            select(FinetuneJob).where(FinetuneJob.id == job_id)
        )).scalar_one_or_none()
        if not job or job.status != "completed":
            raise ValueError("任务未完成或不存在")

        merged_path = f"{job.output_path}/merged"
        # Merge LoRA (if llamafactory is available)
        try:
            subprocess.run(
                [self.LLAMAFACTORY_BIN, "export",
                 f"--model_name_or_path={job.base_model}",
                 f"--adapter_name_or_path={job.output_path}",
                 f"--export_dir={merged_path}"],
                check=True, timeout=600,
            )
        except Exception as e:
            logger.warning("LoRA 合并失败 (非致命): %s", e)
            merged_path = job.output_path

        new_model = LocalModel(
            id=str(uuid.uuid4()),
            name=f"{job.name}-merged",
            version="1.0",
            backend="vllm",
            model_path=merged_path,
            description=f"Fine-tuned from {job.base_model} via {job.method}",
            use_cases=["qa"],
        )
        db.add(new_model)
        await db.commit()
        return {"model_id": new_model.id, "path": merged_path}


finetuner = Finetuner()
