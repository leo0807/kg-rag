#!/usr/bin/env python3
"""
Export Neo4j knowledge graph to OWL 2 Turtle format.
Enables SPARQL queries via Apache Jena Fuseki and cross-system interoperability.

Usage:
    python scripts/export_owl.py \
        --neo4j-uri bolt://localhost:7687 \
        --neo4j-user neo4j \
        --neo4j-password password \
        --output knowledge-graph.ttl

Requirements:
    pip install neo4j rdflib
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def build_ontology(neo4j_uri: str, user: str, pwd: str):
    """Build RDFLib graph from Neo4j."""
    try:
        from neo4j import GraphDatabase
        from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, XSD, URIRef
    except ImportError:
        log.error("Install: pip install neo4j rdflib")
        return None

    CPS = Namespace("http://aviation.corp/cps/ontology#")
    g = Graph()
    g.bind("cps", CPS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology header
    onto = URIRef("http://aviation.corp/cps/ontology")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal("CPS Aviation Knowledge Ontology", lang="en")))

    # Class definitions
    for cls_name in ["Document", "Section", "Tool", "Material", "Process",
                      "Constraint", "Standard", "Component", "Person",
                      "Equipment", "Step", "Hazard", "Inspection", "ChangeRecord"]:
        cls_uri = CPS[cls_name]
        g.add((cls_uri, RDF.type, OWL.Class))
        g.add((cls_uri, RDFS.label, Literal(cls_name)))

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, pwd))
    with driver.session() as s:
        # Export Document nodes
        for r in s.run("MATCH (d:Document) RETURN d.name AS id, d.title AS title LIMIT 10000"):
            node_uri = CPS[f"Document/{r['id']}"]
            g.add((node_uri, RDF.type, CPS.Document))
            g.add((node_uri, RDFS.label, Literal(r["title"] or r["id"])))

        # Export Section nodes
        for r in s.run(
            "MATCH (d:Document)-[:HAS_SECTION]->(s:Section) "
            "RETURN s.chunk_id AS id, s.title AS title, d.name AS doc_id LIMIT 100000"
        ):
            node_uri = CPS[f"Section/{r['id']}"]
            doc_uri = CPS[f"Document/{r['doc_id']}"]
            g.add((node_uri, RDF.type, CPS.Section))
            g.add((node_uri, RDFS.label, Literal(r["title"] or r["id"])))
            g.add((doc_uri, CPS.hasSection, node_uri))

        # Export Tool/Material/Process entities
        for entity_type in ["Tool", "Material", "Process"]:
            for r in s.run(
                f"MATCH (e:{entity_type}) RETURN e.name AS name LIMIT 50000"
            ):
                uri = CPS[f"{entity_type}/{r['name'].replace(' ', '_')}"]
                g.add((uri, RDF.type, CPS[entity_type]))
                g.add((uri, RDFS.label, Literal(r["name"])))

        # Export Standard nodes
        for r in s.run("MATCH (st:Standard) RETURN st.std_id AS id, st.name AS name LIMIT 10000"):
            uri = CPS[f"Standard/{r['id']}"]
            g.add((uri, RDF.type, CPS.Standard))
            g.add((uri, RDFS.label, Literal(r["name"] or r["id"])))

        # Export key relations as OWL object properties
        for r in s.run(
            "MATCH (d:Document)-[:COMPLIES_WITH]->(st:Standard) "
            "RETURN d.name AS doc, st.std_id AS std LIMIT 50000"
        ):
            doc_uri = CPS[f"Document/{r['doc']}"]
            std_uri = CPS[f"Standard/{r['std']}"]
            g.add((doc_uri, CPS.compliesWith, std_uri))

        for r in s.run(
            "MATCH (a:Document)-[:REFERENCES]->(b:Document) "
            "RETURN a.name AS src, b.name AS dst LIMIT 100000"
        ):
            g.add((CPS[f"Document/{r['src']}"], CPS.references,
                   CPS[f"Document/{r['dst']}"]))

    driver.close()
    log.info("Graph built: %d triples", len(g))
    return g


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--output", default="knowledge-graph.ttl")
    args = parser.parse_args()

    g = build_ontology(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    if g is None:
        return

    out = Path(args.output)
    g.serialize(destination=str(out), format="turtle")
    log.info("OWL ontology saved to: %s (%d triples)", out, len(g))
    print(f"\n✓ Exported {len(g)} triples to: {out}")
    print(f"  Load in Fuseki: ./fuseki-server --file={out} /knowledge")


if __name__ == "__main__":
    main()
