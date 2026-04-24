from __future__ import annotations

ALLOWED_RELATIONS = {"REQUIRES_TOOL", "USES_MATERIAL", "ALTERNATIVE_TO", "COMPATIBLE_WITH"}
TYPE_LABEL = {"Tool": "Tool", "Material": "Material", "Process": "Process"}


def normalize_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        name = (value or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        output.append(name)
    return output


def collect_section_entities(item: dict) -> tuple[list[str], list[str], list[str], list[dict]]:
    tools = normalize_names(item.get("tools", []))
    materials = normalize_names(item.get("materials", []))
    processes = normalize_names(item.get("processes", []))
    relations = [
        rel
        for rel in item.get("relations", [])
        if rel.get("rel") in ALLOWED_RELATIONS
        and rel.get("from_type") in TYPE_LABEL
        and rel.get("to_type") in TYPE_LABEL
        and (rel.get("from_name") or "").strip()
        and (rel.get("to_name") or "").strip()
    ]

    section_entities = {
        "Tool": set(tools),
        "Material": set(materials),
        "Process": set(processes),
    }
    for rel in relations:
        section_entities[rel["from_type"]].add(rel["from_name"].strip())
        section_entities[rel["to_type"]].add(rel["to_name"].strip())

    return (
        sorted(section_entities["Tool"]),
        sorted(section_entities["Material"]),
        sorted(section_entities["Process"]),
        relations,
    )

