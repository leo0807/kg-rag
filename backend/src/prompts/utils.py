from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptRenderResult:
    template_id: str
    version: str
    system: str
    user: str
    messages: list[dict[str, str]]
    model: str
    max_tokens: int
    temperature: float


def stringify_prompt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(stringify_prompt_value(v) for v in value)
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def render_prompt_text(text: str, variables: dict[str, Any]) -> str:
    mapping = {key: stringify_prompt_value(value) for key, value in variables.items()}
    return Template(text or "").safe_substitute(mapping)


def choose_version(template: dict[str, Any], version: str | None = None, ab_test: bool = False) -> tuple[str, dict[str, Any]]:
    versions = template.get("versions") or {}
    if not versions:
        return str(template.get("version") or "1.0"), template

    selected = version or str(template.get("active_version") or "")
    if selected and selected in versions:
        pass
    elif ab_test:
        weighted = [
            (name, int(versions[name].get("weight", 0) or 0))
            for name in versions
            if int(versions[name].get("weight", 0) or 0) > 0
        ]
        if weighted:
            names, weights = zip(*weighted)
            selected = random.choices(list(names), weights=list(weights), k=1)[0]
        else:
            selected = next(iter(versions))
    else:
        selected = template.get("active_version") or next(iter(versions))

    if selected not in versions:
        selected = next(iter(versions))

    merged = dict(template)
    merged.update({k: v for k, v in versions[selected].items() if k != "weight"})
    merged["active_version"] = selected
    return str(selected), merged


def template_summary(template_id: str, template: dict[str, Any]) -> dict[str, Any]:
    versions = template.get("versions") or {}
    version_items = []
    selected_payload: dict[str, Any] = template
    if versions:
        selected_name = str(template.get("active_version") or next(iter(versions)))
        selected_payload = versions.get(selected_name) or next(iter(versions.values()))
        for name, payload in versions.items():
            version_items.append(
                {
                    "name": name,
                    "weight": int(payload.get("weight", 0) or 0),
                    "max_tokens": int(payload.get("max_tokens", template.get("max_tokens", 800)) or 800),
                    "temperature": float(payload.get("temperature", template.get("temperature", 0.3)) or 0.3),
                    "model_preference": str(payload.get("model_preference", template.get("model_preference", "")) or ""),
                }
            )
    else:
        selected_version = str(template.get("version") or "1.0")
        version_items.append(
            {
                "name": selected_version,
                "weight": 100,
                "max_tokens": int(template.get("max_tokens", 800) or 800),
                "temperature": float(template.get("temperature", 0.3) or 0.3),
                "model_preference": str(template.get("model_preference", "") or ""),
            }
        )
    return {
        "id": template_id,
        "description": str(template.get("description", "") or ""),
        "active_version": str(template.get("active_version") or version_items[0]["name"]),
        "model_preference": str(selected_payload.get("model_preference", template.get("model_preference", "")) or ""),
        "max_tokens": int(selected_payload.get("max_tokens", template.get("max_tokens", 800)) or 800),
        "temperature": float(selected_payload.get("temperature", template.get("temperature", 0.3)) or 0.3),
        "versions": version_items,
        "variables": list(template.get("variables", []) or []),
        "file": str(template.get("_file", "") or ""),
    }


def write_template_file(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
