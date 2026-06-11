"""K6.3: HPC cluster job submission (PBS/Slurm) for batch simulation workflows."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_JOB_POLL_INTERVAL = 30  # seconds between status polls


class _ClusterBackend:
    """Base stub — real backends would SSH to the cluster and submit."""
    name = "local"

    async def submit(self, script: str, config: Dict[str, Any]) -> str:
        job_id = f"local-{uuid.uuid4().hex[:8]}"
        logger.info("Local submit (stub) job=%s", job_id)
        return job_id

    async def status(self, job_id: str) -> str:
        return "completed"

    async def cancel(self, job_id: str) -> bool:
        return True


class _SlurmBackend(_ClusterBackend):
    name = "slurm"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.host    = config.get("host", "")
        self.user    = config.get("user", "")
        self.ssh_key = config.get("ssh_key", "")

    async def submit(self, script: str, config: Dict[str, Any]) -> str:
        logger.warning("Slurm SSH submit not implemented — using stub job_id")
        return f"slurm-{uuid.uuid4().hex[:8]}"

    async def status(self, job_id: str) -> str:
        return "running"


class _PBSBackend(_ClusterBackend):
    name = "pbs"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.host    = config.get("host", "")
        self.user    = config.get("user", "")
        self.ssh_key = config.get("ssh_key", "")

    async def submit(self, script: str, config: Dict[str, Any]) -> str:
        logger.warning("PBS qsub not implemented — using stub job_id")
        return f"pbs-{uuid.uuid4().hex[:8]}"

    async def status(self, job_id: str) -> str:
        return "running"


def _get_backend(target: str, config: Dict[str, Any]) -> _ClusterBackend:
    if target == "slurm":
        return _SlurmBackend(config)
    if target == "pbs":
        return _PBSBackend(config)
    return _ClusterBackend()


class ClusterSubmitter:
    """Manage batch submission, monitoring, and result collection for workflows."""

    def _make_script(self, sample: Dict[str, Any], workflow: Any) -> str:
        """Generate a trivial job script; real use would template the solver command."""
        lines = ["#!/bin/bash", f"# Workflow: {getattr(workflow, 'name', '')}"]
        for k, v in sample.items():
            lines.append(f"export SIM_{k.upper()}={v}")
        lines.append("echo 'Simulation complete'")
        return "\n".join(lines)

    async def submit_batch(self, db: AsyncSession, workflow_id: str) -> Dict[str, Any]:
        from ...db.simulation_models import SimulationWorkflow
        from .doe_sampler import doe_sampler

        wf = await db.get(SimulationWorkflow, workflow_id)
        if not wf:
            return {"error": "workflow not found"}

        param_space = wf.parameter_space or {}
        samples = doe_sampler.generate(
            wf.doe_type,
            param_space,
            n_samples=wf.sample_count,
        )

        backend = _get_backend(wf.submit_target, wf.cluster_config or {})
        job_ids: List[str] = []

        for sample in samples:
            script = self._make_script(sample, wf)
            try:
                jid = await backend.submit(script, wf.cluster_config or {})
                job_ids.append(jid)
            except Exception as e:
                logger.error("Submit error for sample %s: %s", sample, e)
                job_ids.append(f"error-{uuid.uuid4().hex[:4]}")

        wf.status      = "running"
        wf.total_runs  = len(samples)
        wf.completed_runs = 0
        # Store job_ids in cluster_config for later monitoring
        cfg = dict(wf.cluster_config or {})
        cfg["job_ids"] = job_ids
        wf.cluster_config = cfg
        await db.commit()

        return {"workflow_id": workflow_id, "total": len(samples), "job_ids": job_ids}

    async def monitor_jobs(self, db: AsyncSession, workflow_id: str) -> Dict[str, Any]:
        from ...db.simulation_models import SimulationWorkflow

        wf = await db.get(SimulationWorkflow, workflow_id)
        if not wf:
            return {"error": "workflow not found"}

        job_ids: List[str] = (wf.cluster_config or {}).get("job_ids", [])
        backend  = _get_backend(wf.submit_target, wf.cluster_config or {})

        statuses: Dict[str, str] = {}
        for jid in job_ids:
            statuses[jid] = await backend.status(jid)

        completed = sum(1 for s in statuses.values() if s == "completed")
        failed    = sum(1 for s in statuses.values() if s in ("failed", "error"))

        wf.completed_runs = completed
        if completed + failed >= len(job_ids) and job_ids:
            wf.status = "failed" if failed > completed else "completed"
        await db.commit()

        return {
            "workflow_id": workflow_id,
            "total": wf.total_runs,
            "completed": completed,
            "failed": failed,
            "status": wf.status,
            "statuses": statuses,
        }

    async def collect_results(self, db: AsyncSession, workflow_id: str) -> Dict[str, Any]:
        from ...db.simulation_models import SimulationWorkflow

        wf = await db.get(SimulationWorkflow, workflow_id)
        if not wf:
            return {"error": "workflow not found"}

        job_ids: List[str] = (wf.cluster_config or {}).get("job_ids", [])
        # In production: SSH-fetch result files and call case_importer.import_case()
        logger.info("Result collection for %d jobs (stub)", len(job_ids))

        wf.status = "results_collected"
        await db.commit()
        return {"workflow_id": workflow_id, "collected": len(job_ids)}


cluster_submitter = ClusterSubmitter()
