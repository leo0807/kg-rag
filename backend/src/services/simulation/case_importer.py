"""K1.2: Multi-format simulation result importer with parser dispatch."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS: Dict[str, str] = {
    ".odb": "abaqus",
    ".rst": "ansys",
    ".cas": "fluent",
    ".op2": "nastran",
    ".dat": "generic",
    ".csv": "csv",
    ".json": "json",
}


# ── Generic parsers (no proprietary libs required) ───────────────────────────

class GenericCSVParser:
    async def parse(self, file_path: str) -> Dict[str, Any]:
        rows: List[Dict] = []
        try:
            with open(file_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
        except Exception as e:
            logger.warning("CSV parse error: %s", e)
        return {"format": "csv", "rows": rows, "parameters": {}, "results": []}


class GenericJSONParser:
    async def parse(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return {"format": "json", "raw": data,
                    "parameters": data.get("parameters", {}),
                    "results": data.get("results", [])}
        except Exception as e:
            logger.warning("JSON parse error: %s", e)
            return {"format": "json", "rows": [], "parameters": {}, "results": []}


class StubParser:
    """Placeholder for proprietary formats (Abaqus/Ansys/Fluent/Nastran)."""

    def __init__(self, fmt: str) -> None:
        self.fmt = fmt

    async def parse(self, file_path: str) -> Dict[str, Any]:
        logger.info("Stub parser for %s: %s — binary parsing not available", self.fmt, file_path)
        return {
            "format": self.fmt,
            "file": os.path.basename(file_path),
            "note": f"{self.fmt} binary parsing requires optional dependencies",
            "parameters": {},
            "results": [],
        }


# ── Main importer ─────────────────────────────────────────────────────────────

class SimulationCaseImporter:
    """
    Dispatch file imports to the correct parser, extract parameters/results,
    persist to DB and link to Neo4j knowledge graph.
    """

    def _detect_format(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return SUPPORTED_FORMATS.get(ext, "unknown")

    def _get_parser(self, fmt: str):
        if fmt == "csv":
            return GenericCSVParser()
        if fmt == "json":
            return GenericJSONParser()
        if fmt in ("abaqus", "ansys", "fluent", "nastran", "generic"):
            return StubParser(fmt)
        raise ValueError(f"Unsupported format: {fmt}")

    def _extract_parameters(self, case_data: Dict) -> List[Dict]:
        raw = case_data.get("parameters", {})
        params: List[Dict] = []
        if isinstance(raw, dict):
            for name, val in raw.items():
                num = None
                try:
                    num = float(val) if not isinstance(val, dict) else None
                except (TypeError, ValueError):
                    pass
                params.append({
                    "parameter_name": name,
                    "parameter_type": "boundary",
                    "value": val,
                    "numeric_value": num,
                })
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    params.append(item)
        return params

    def _extract_results(self, case_data: Dict) -> List[Dict]:
        raw = case_data.get("results", [])
        results: List[Dict] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    results.append({
                        "result_type":  item.get("type", "stress"),
                        "result_name":  item.get("name", "result"),
                        "max_value":    item.get("max"),
                        "min_value":    item.get("min"),
                        "avg_value":    item.get("avg"),
                        "unit":         item.get("unit", ""),
                        "pass_status":  item.get("pass_status", "unknown"),
                        "detail_data":  item.get("detail", {}),
                        "distribution": item.get("distribution", {}),
                        "critical_locations": item.get("critical_locations", []),
                    })
        elif isinstance(raw, dict):
            for k, v in raw.items():
                results.append({
                    "result_type": "generic",
                    "result_name": k,
                    "detail_data": v,
                    "pass_status": "unknown",
                })
        return results

    async def _extract_images(self, case_data: Dict) -> List[Dict]:
        return case_data.get("images", [])

    async def _save_case(
        self,
        db,
        metadata: Dict,
        params: List[Dict],
        results: List[Dict],
        images: List[Dict],
    ) -> Dict:
        from ...db.simulation_models import SimulationCase, SimulationParameter, SimulationResult
        import uuid as _uuid

        case_id = str(_uuid.uuid4())
        case = SimulationCase(
            id=case_id,
            case_name=metadata.get("case_name", "未命名案例"),
            case_code=metadata.get("case_code"),
            description=metadata.get("description", ""),
            domain=metadata.get("domain", "structural"),
            application=metadata.get("application", ""),
            software=metadata.get("software", ""),
            software_version=metadata.get("software_version", ""),
            related_specs=metadata.get("related_specs", []),
            related_sections=metadata.get("related_sections", []),
            inputs=metadata.get("inputs", {}),
            outputs=metadata.get("outputs", {}),
            images=images,
            author_id=metadata.get("author_id"),
            project_code=metadata.get("project_code", ""),
            confidence_level=metadata.get("confidence_level", "初步"),
            tenant_id=metadata.get("tenant_id"),
        )
        db.add(case)

        for p in params:
            db.add(SimulationParameter(case_id=case_id, **p))

        for r in results:
            db.add(SimulationResult(case_id=case_id, **r))

        await db.flush()
        return {"id": case_id, "case_name": case.case_name}

    async def _link_to_kg(self, case_info: Dict) -> None:
        """Create Neo4j SimulationCase node (best-effort, non-blocking)."""
        try:
            from ...services.graph.connection import get_neo4j_driver
            async with get_neo4j_driver() as driver:
                async with driver.session() as session:
                    await session.run(
                        "MERGE (n:SimulationCase {id: $id}) "
                        "SET n.name = $name, n.domain = $domain",
                        id=case_info["id"],
                        name=case_info.get("case_name", ""),
                        domain=case_info.get("domain", ""),
                    )
        except Exception as e:
            logger.debug("Neo4j link skipped: %s", e)

    async def import_case(self, db, file_path: str, metadata: Dict) -> Dict:
        fmt = self._detect_format(file_path)
        if fmt == "unknown":
            raise ValueError(f"不支持的文件格式: {Path(file_path).suffix}")

        parser = self._get_parser(fmt)
        case_data = await parser.parse(file_path)

        params  = self._extract_parameters(case_data)
        results = self._extract_results(case_data)
        images  = await self._extract_images(case_data)

        case_info = await self._save_case(db, metadata, params, results, images)
        await self._link_to_kg(case_info)

        return {**case_info, "parameters": len(params), "results": len(results),
                "images": len(images), "format": fmt}


case_importer = SimulationCaseImporter()
