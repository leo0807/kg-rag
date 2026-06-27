#!/usr/bin/env python3
"""
SHACL constraint validation for Neo4j Section nodes.

Validates that exported OWL/Turtle graphs satisfy SectionShape:
  - sh:minCount 1 on :content, :doc_id
  - sh:minCount 1 on outgoing relations (REFERENCES | HAS_TOPIC | BELONGS_TO)

Can be used as a pre-ingest gate: run before writing to Neo4j.

Usage:
    pip install pyshacl rdflib
    # Validate an OWL export file:
    python scripts/validate_shacl.py knowledge-graph.ttl

    # Validate directly from Neo4j (exports on-the-fly, then validates):
    python scripts/validate_shacl.py \
        --neo4j-uri bolt://localhost:7687 \
        --neo4j-user neo4j \
        --neo4j-password password

    # Strict mode — exit code 1 on any violation:
    python scripts/validate_shacl.py knowledge-graph.ttl --strict
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import textwrap
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── SHACL shape definition (inline Turtle) ───────────────────────────────────
SHACL_SHAPES = textwrap.dedent("""\
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix kgc:  <http://aviation.comac.cc/cps/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

kgc:SectionShape
    a sh:NodeShape ;
    sh:targetClass kgc:Section ;

    # content must be present and non-empty
    sh:property [
        sh:path kgc:content ;
        sh:minCount 1 ;
        sh:minLength 1 ;
        sh:datatype xsd:string ;
        sh:message "Section 缺少 content 属性" ;
    ] ;

    # doc_id must be present
    sh:property [
        sh:path kgc:doc_id ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Section 缺少 doc_id 属性" ;
    ] ;

    # chunk_id must be present (primary key)
    sh:property [
        sh:path kgc:chunk_id ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Section 缺少 chunk_id 属性" ;
    ] ;

    # Must have at least one outgoing relation
    sh:or (
        [ sh:property [ sh:path kgc:REFERENCES   ; sh:minCount 1 ] ]
        [ sh:property [ sh:path kgc:HAS_TOPIC    ; sh:minCount 1 ] ]
        [ sh:property [ sh:path kgc:BELONGS_TO   ; sh:minCount 1 ] ]
        [ sh:property [ sh:path kgc:NEXT_SECTION ; sh:minCount 1 ] ]
    ) ;
    sh:message "Section 必须至少有一条出边（REFERENCES / HAS_TOPIC / BELONGS_TO / NEXT_SECTION）" .

kgc:DocumentShape
    a sh:NodeShape ;
    sh:targetClass kgc:Document ;

    sh:property [
        sh:path kgc:doc_id ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Document 缺少 doc_id 属性" ;
    ] ;
    sh:property [
        sh:path kgc:title ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Document 缺少 title 属性" ;
    ] .
""")


def _export_from_neo4j(neo4j_uri: str, neo4j_user: str, neo4j_password: str,
                        out_file: str = "/tmp/kg_validate.ttl") -> str:
    """Run export_owl.py to produce a .ttl then return the path."""
    import subprocess
    script = Path(__file__).parent / "export_owl.py"
    cmd = [
        sys.executable, str(script),
        "--neo4j-uri", neo4j_uri,
        "--neo4j-user", neo4j_user,
        "--neo4j-password", neo4j_password,
        "--output", out_file,
    ]
    log.info("Exporting OWL from Neo4j to %s ...", out_file)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"export_owl.py failed:\n{result.stderr}")
    return out_file


def validate(ttl_file: str, strict: bool = False) -> bool:
    """
    Validate a Turtle file against SHACL SectionShape.

    Returns True if conformant, False if violations found.
    In strict mode, raises SystemExit(1) on violation.
    """
    try:
        from pyshacl import validate as shacl_validate
        from rdflib import Graph
    except ImportError:
        raise RuntimeError("pip install pyshacl rdflib")

    data_graph = Graph()
    data_graph.parse(ttl_file, format="turtle")

    shapes_graph = Graph()
    shapes_graph.parse(data=SHACL_SHAPES, format="turtle")

    conforms, results_graph, results_text = shacl_validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
    )

    if conforms:
        log.info("SHACL validation PASSED — all Section nodes conform to SectionShape")
        return True

    log.error("SHACL validation FAILED:\n%s", results_text)

    # Count violations
    violations = results_text.count("Constraint Violation")
    log.error("%d constraint violation(s) found in %s", violations, ttl_file)

    if strict:
        sys.exit(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ttl_file", nargs="?",
                        help="Path to .ttl file to validate (optional if --neo4j-* given)")
    parser.add_argument("--neo4j-uri",      default=os.getenv("NEO4J_URI", ""))
    parser.add_argument("--neo4j-user",     default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any violation (use in CI/ingest gate)")
    args = parser.parse_args()

    ttl_file = args.ttl_file
    if not ttl_file:
        if not args.neo4j_uri:
            parser.error("Provide either a .ttl file or --neo4j-uri / --neo4j-password")
        ttl_file = _export_from_neo4j(
            args.neo4j_uri, args.neo4j_user, args.neo4j_password
        )

    validate(ttl_file, strict=args.strict)


if __name__ == "__main__":
    main()
