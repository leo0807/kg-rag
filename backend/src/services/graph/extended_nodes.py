"""
Extended graph node types: Standard, Component, Person, Equipment,
Step, Hazard, Inspection, ChangeRecord — and their relations.
"""
from __future__ import annotations

import logging
from datetime import datetime
from neo4j import Driver

logger = logging.getLogger(__name__)


# ─── Standard (规范节点) ────────────────────────────────────────────────────

def merge_standard(driver: Driver, std_id: str, name: str, org: str = "",
                   version: str = "", category: str = "") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (st:Standard {std_id: $std_id})
            SET st.name = $name, st.org = $org,
                st.version = $version, st.category = $category
            """,
            std_id=std_id, name=name, org=org,
            version=version, category=category,
        )


def link_document_complies(driver: Driver, doc_id: str, std_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (d:Document {name: $doc_id})
            MATCH (st:Standard {std_id: $std_id})
            MERGE (d)-[:COMPLIES_WITH]->(st)
            """,
            doc_id=doc_id, std_id=std_id,
        )


# ─── Component (零件节点) ────────────────────────────────────────────────────

def merge_component(driver: Driver, part_no: str, name: str = "",
                    description: str = "") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (c:Component {part_no: $part_no})
            SET c.name = $name, c.description = $description
            """,
            part_no=part_no, name=name, description=description,
        )


def link_section_applies_to(driver: Driver, chunk_id: str, part_no: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (sec:Section {chunk_id: $chunk_id})
            MATCH (c:Component {part_no: $part_no})
            MERGE (sec)-[:APPLIES_TO]->(c)
            """,
            chunk_id=chunk_id, part_no=part_no,
        )


# ─── Person / Role (人员节点) ────────────────────────────────────────────────

def merge_person(driver: Driver, person_id: str, name: str,
                 role: str = "", department: str = "") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (p:Person {person_id: $person_id})
            SET p.name = $name, p.role = $role, p.department = $department
            """,
            person_id=person_id, name=name, role=role, department=department,
        )


def link_document_authored(driver: Driver, doc_id: str, person_id: str,
                            rel: str = "AUTHORED_BY") -> None:
    """rel can be AUTHORED_BY / REVIEWED_BY / APPROVED_BY"""
    with driver.session() as s:
        s.run(
            f"""
            MATCH (d:Document {{name: $doc_id}})
            MATCH (p:Person {{person_id: $person_id}})
            MERGE (d)-[:{rel}]->(p)
            """,
            doc_id=doc_id, person_id=person_id,
        )


# ─── Equipment (设备/工装节点) ───────────────────────────────────────────────

def merge_equipment(driver: Driver, equip_id: str, name: str,
                    calibration_due: str = "", equipment_type: str = "") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (e:Equipment {equip_id: $equip_id})
            SET e.name = $name, e.calibration_due = $calibration_due,
                e.equipment_type = $equipment_type
            """,
            equip_id=equip_id, name=name,
            calibration_due=calibration_due, equipment_type=equipment_type,
        )


def link_section_requires_equipment(driver: Driver, chunk_id: str,
                                     equip_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (sec:Section {chunk_id: $chunk_id})
            MATCH (e:Equipment {equip_id: $equip_id})
            MERGE (sec)-[:REQUIRES_EQUIPMENT]->(e)
            """,
            chunk_id=chunk_id, equip_id=equip_id,
        )


# ─── Step (工序步骤节点) ─────────────────────────────────────────────────────

def write_steps(driver: Driver, chunk_id: str,
                steps: list[dict]) -> None:
    """
    steps: [{"order": 1, "text": "...", "step_id": "..."}]
    Creates Step nodes and chains them with NEXT_STEP.
    """
    if not steps:
        return
    with driver.session() as s:
        prev_id: str | None = None
        for step in sorted(steps, key=lambda x: x["order"]):
            s.run(
                """
                MATCH (sec:Section {chunk_id: $chunk_id})
                MERGE (st:Step {step_id: $step_id})
                SET st.text = $text, st.order = $order, st.doc_chunk = $chunk_id
                MERGE (sec)-[:HAS_STEP {order: $order}]->(st)
                """,
                chunk_id=chunk_id,
                step_id=step["step_id"],
                text=step["text"],
                order=step["order"],
            )
            if prev_id:
                s.run(
                    """
                    MATCH (a:Step {step_id: $a}), (b:Step {step_id: $b})
                    MERGE (a)-[:NEXT_STEP]->(b)
                    """,
                    a=prev_id, b=step["step_id"],
                )
            prev_id = step["step_id"]


def link_steps_precedes(driver: Driver, step_a: str, step_b: str) -> None:
    """Cross-section PRECEDES relation."""
    with driver.session() as s:
        s.run(
            """
            MATCH (a:Step {step_id: $a}), (b:Step {step_id: $b})
            MERGE (a)-[:PRECEDES]->(b)
            MERGE (b)-[:FOLLOWS]->(a)
            """,
            a=step_a, b=step_b,
        )


# ─── Hazard (危险源节点) ─────────────────────────────────────────────────────

def merge_hazard(driver: Driver, hazard_id: str, description: str,
                 severity: str = "medium") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (h:Hazard {hazard_id: $hazard_id})
            SET h.description = $description, h.severity = $severity
            """,
            hazard_id=hazard_id, description=description, severity=severity,
        )


def link_section_warns_of(driver: Driver, chunk_id: str, hazard_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (sec:Section {chunk_id: $chunk_id})
            MATCH (h:Hazard {hazard_id: $hazard_id})
            MERGE (sec)-[:WARNS_OF]->(h)
            """,
            chunk_id=chunk_id, hazard_id=hazard_id,
        )


# ─── Inspection (检验节点) ───────────────────────────────────────────────────

def merge_inspection(driver: Driver, insp_id: str, method: str,
                     frequency: str = "", acceptance_criteria: str = "") -> None:
    with driver.session() as s:
        s.run(
            """
            MERGE (i:Inspection {insp_id: $insp_id})
            SET i.method = $method, i.frequency = $frequency,
                i.acceptance_criteria = $acceptance_criteria
            """,
            insp_id=insp_id, method=method, frequency=frequency,
            acceptance_criteria=acceptance_criteria,
        )


def link_section_requires_inspection(driver: Driver, chunk_id: str,
                                      insp_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (sec:Section {chunk_id: $chunk_id})
            MATCH (i:Inspection {insp_id: $insp_id})
            MERGE (sec)-[:REQUIRES_INSPECTION]->(i)
            """,
            chunk_id=chunk_id, insp_id=insp_id,
        )


# ─── ChangeRecord (变更记录节点) ─────────────────────────────────────────────

def write_change_record(driver: Driver, doc_id: str, record_id: str,
                        reason: str, approver: str = "",
                        effective_date: str = "") -> None:
    if not effective_date:
        effective_date = datetime.utcnow().isoformat()
    with driver.session() as s:
        s.run(
            """
            MATCH (d:Document {name: $doc_id})
            MERGE (cr:ChangeRecord {record_id: $record_id})
            SET cr.reason = $reason, cr.approver = $approver,
                cr.effective_date = $effective_date, cr.doc_id = $doc_id
            MERGE (d)-[:HAS_CHANGE_RECORD]->(cr)
            """,
            doc_id=doc_id, record_id=record_id, reason=reason,
            approver=approver, effective_date=effective_date,
        )


# ─── Cross-node relations ────────────────────────────────────────────────────

def link_conflicts_with(driver: Driver, chunk_a: str, chunk_b: str,
                         description: str = "") -> None:
    """Mark conflicting constraint sections."""
    with driver.session() as s:
        s.run(
            """
            MATCH (a:Section {chunk_id: $a}), (b:Section {chunk_id: $b})
            MERGE (a)-[:CONFLICTS_WITH {description: $desc}]->(b)
            """,
            a=chunk_a, b=chunk_b, desc=description,
        )


def link_derived_from(driver: Driver, chunk_derived: str,
                       chunk_source: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (a:Section {chunk_id: $a}), (b:Section {chunk_id: $b})
            MERGE (a)-[:DERIVED_FROM]->(b)
            """,
            a=chunk_derived, b=chunk_source,
        )


def link_validated_by(driver: Driver, constraint_chunk_id: str,
                       test_doc_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (c:Constraint {chunk_id: $c_id})
            MATCH (d:Document {name: $doc_id, type: 'test_report'})
            MERGE (c)-[:VALIDATED_BY]->(d)
            """,
            c_id=constraint_chunk_id, doc_id=test_doc_id,
        )


def link_supersedes_section(driver: Driver, new_chunk_id: str,
                             old_chunk_id: str) -> None:
    with driver.session() as s:
        s.run(
            """
            MATCH (new:Section {chunk_id: $new}), (old:Section {chunk_id: $old})
            MERGE (new)-[:SUPERSEDES_SECTION]->(old)
            """,
            new=new_chunk_id, old=old_chunk_id,
        )
