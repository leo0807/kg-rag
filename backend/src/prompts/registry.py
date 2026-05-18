from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .utils import choose_version, render_prompt_text, template_summary, write_template_file


class PromptRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, dict[str, Any]] = {}
        self._files: dict[str, Path] = {}
        self.reload()

    def reload(self) -> None:
        self._templates.clear()
        self._files.clear()
        templates_dir = Path(__file__).parent / "templates"
        if not templates_dir.exists():
            return
        for yaml_file in sorted(templates_dir.rglob("*.yaml")):
            with yaml_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            template_id = str(data.get("id") or yaml_file.stem).strip()
            if not template_id:
                continue
            data["_file"] = str(yaml_file)
            self._templates[template_id] = data
            self._files[template_id] = yaml_file

    def list_templates(self) -> list[dict[str, Any]]:
        return [template_summary(template_id, tpl) for template_id, tpl in sorted(self._templates.items())]

    def get(self, template_id: str, version: str | None = None, ab_test: bool = False) -> dict[str, Any]:
        tpl = self._templates.get(template_id)
        if not tpl:
            raise ValueError(f"未知模板: {template_id}")
        selected_version, merged = choose_version(tpl, version=version, ab_test=ab_test)
        return {
            **template_summary(template_id, tpl),
            "selected_version": selected_version,
            "template": merged,
        }

    def render(
        self,
        template_id: str,
        version: str | None = None,
        ab_test: bool = False,
        **variables: Any,
    ) -> dict[str, Any]:
        record = self.get(template_id, version=version, ab_test=ab_test)
        tpl = record["template"]
        declared = {name: "" for name in tpl.get("variables", []) or []}
        declared.update(variables)
        system = render_prompt_text(str(tpl.get("system", "") or ""), declared)
        user = render_prompt_text(str(tpl.get("user", "") or ""), declared)
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if user.strip():
            messages.append({"role": "user", "content": user})
        return {
            "template_id": template_id,
            "version": record["selected_version"],
            "system": system,
            "user": user,
            "messages": messages,
            "model": str(tpl.get("model_preference", "") or ""),
            "max_tokens": int(tpl.get("max_tokens", 800) or 800),
            "temperature": float(tpl.get("temperature", 0.3) or 0.3),
        }

    def update_template(
        self,
        template_id: str,
        payload: dict[str, Any],
        version: str | None = None,
    ) -> dict[str, Any]:
        tpl = self._templates.get(template_id)
        if not tpl:
            raise ValueError(f"未知模板: {template_id}")
        path = self._files[template_id]
        versions = tpl.get("versions") or {}
        if versions:
            selected_version = version or payload.get("version") or tpl.get("active_version") or next(iter(versions))
            if selected_version not in versions:
                raise ValueError(f"未知版本: {selected_version}")
            selected = versions[selected_version]
            for key in ("description", "model_preference", "max_tokens", "temperature", "system", "user", "variables"):
                if key in payload and payload[key] is not None:
                    selected[key] = payload[key]
                    if key == "description":
                        tpl["description"] = payload[key]
            if "weight" in payload and payload["weight"] is not None:
                selected["weight"] = int(payload["weight"])
            if "active_version" in payload and payload["active_version"]:
                tpl["active_version"] = str(payload["active_version"])
        else:
            for key in ("description", "model_preference", "max_tokens", "temperature", "system", "user", "variables", "version"):
                if key in payload and payload[key] is not None:
                    tpl[key] = payload[key]
            if "active_version" in payload and payload["active_version"]:
                tpl["active_version"] = str(payload["active_version"])
        data = {k: v for k, v in tpl.items() if k != "_file"}
        write_template_file(path, data)
        self.reload()
        return self.get(template_id, version=payload.get("version") or version)


registry = PromptRegistry()
