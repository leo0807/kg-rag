#!/usr/bin/env python3
"""
CPS Knowledge Base MCP Server
Exposes the knowledge base as MCP tools for Claude Desktop / Cursor / Zed.

Usage (stdio):
    python mcp_server/server.py

Config for Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "cps-knowledge-base": {
          "command": "python",
          "args": ["/path/to/kg-rag/mcp_server/server.py"],
          "env": {
            "BACKEND_URL": "http://localhost:8000",
            "API_KEY": "your-api-key"
          }
        }
      }
    }
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import httpx

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
log = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

_HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "query_knowledge_base",
        "description": "Query the CPS aerospace knowledge base with a natural language question. Returns answer and source sections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask"},
                "strategy": {
                    "type": "string",
                    "enum": ["parallel", "graph_augmented", "sequential", "multi_hop"],
                    "description": "Retrieval strategy (default: parallel)",
                    "default": "parallel",
                },
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["question"],
        },
    },
    {
        "name": "search_documents",
        "description": "Search documents in the knowledge base by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_section_content",
        "description": "Get full content of a document's sections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID"},
                "section_filter": {"type": "string", "description": "Optional title filter"},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "get_entity_graph",
        "description": "Get knowledge graph data (nodes and relations) for a document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "max_nodes": {"type": "integer", "default": 100},
            },
        },
    },
    {
        "name": "search_entities",
        "description": "Search for entities (Tool, Material, Process, Component) in the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Entity name or keyword"},
                "entity_type": {
                    "type": "string",
                    "enum": ["Tool", "Material", "Process", "Component", "Hazard"],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "compare_documents",
        "description": "Compare two documents and return chapter-level differences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id_a": {"type": "string"},
                "doc_id_b": {"type": "string"},
            },
            "required": ["doc_id_a", "doc_id_b"],
        },
    },
    {
        "name": "get_graph_path",
        "description": "Find the shortest knowledge path between two nodes in the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_id": {"type": "string", "description": "Source node chunk_id"},
                "to_id": {"type": "string", "description": "Target node chunk_id"},
            },
            "required": ["from_id", "to_id"],
        },
    },
]


# ─── Tool handlers ────────────────────────────────────────────────────────────

def _call(method: str, path: str, **kwargs) -> Any:
    with httpx.Client(base_url=BACKEND_URL, headers=_HEADERS, timeout=60) as c:
        r = getattr(c, method)(path, **kwargs)
        r.raise_for_status()
        return r.json()


def handle_query_knowledge_base(args: dict) -> str:
    data = _call(
        "post", "/api/query",
        json={
            "question": args["question"],
            "strategy": args.get("strategy", "parallel"),
            "top_k": args.get("top_k", 5),
        },
    )
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    source_text = "\n".join(
        f"- [{s.get('title', '')}] ({s.get('doc_id', '')})"
        for s in sources[:5]
    )
    return f"{answer}\n\n**来源:**\n{source_text}"


def handle_search_documents(args: dict) -> str:
    data = _call("get", "/api/documents", params={"q": args["query"], "limit": args.get("limit", 10)})
    docs = data.get("documents", data) if isinstance(data, dict) else data
    if not docs:
        return "No documents found."
    return "\n".join(
        f"- {d.get('name', d.get('doc_id', ''))} — {d.get('title', '')}"
        for d in docs
    )


def handle_get_section_content(args: dict) -> str:
    data = _call("get", f"/api/documents/{args['doc_id']}/sections")
    sections = data.get("sections", data) if isinstance(data, dict) else data
    filt = args.get("section_filter", "").lower()
    result = []
    for s in sections:
        title = s.get("title", "")
        if filt and filt not in title.lower():
            continue
        result.append(f"### {title}\n{s.get('content', '')[:500]}")
    return "\n\n".join(result[:10]) if result else "No sections found."


def handle_get_entity_graph(args: dict) -> str:
    params = {"max_nodes": args.get("max_nodes", 100)}
    if "doc_id" in args:
        params["doc_id"] = args["doc_id"]
    data = _call("get", "/api/graph/data", params=params)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    return f"Graph: {len(nodes)} nodes, {len(edges)} edges.\nNode types: {set(n.get('type') for n in nodes)}"


def handle_search_entities(args: dict) -> str:
    params = {"q": args["query"]}
    if "entity_type" in args:
        params["type"] = args["entity_type"]
    data = _call("get", "/api/entities", params=params)
    entities = data.get("entities", data) if isinstance(data, dict) else data
    if not entities:
        return "No entities found."
    return "\n".join(
        f"- [{e.get('type', '')}] {e.get('name', '')} — {e.get('description', '')}"
        for e in entities[:20]
    )


def handle_compare_documents(args: dict) -> str:
    data = _call(
        "get", "/api/compare",
        params={"doc_a": args["doc_id_a"], "doc_b": args["doc_id_b"]},
    )
    diffs = data.get("differences", [])
    if not diffs:
        return "No significant differences found."
    lines = [f"Found {len(diffs)} differences:"]
    for d in diffs[:10]:
        lines.append(f"- {d.get('section', '')}: {d.get('change_type', '')}")
    return "\n".join(lines)


def handle_get_graph_path(args: dict) -> str:
    data = _call(
        "get", "/api/graph/path",
        params={"from_id": args["from_id"], "to_id": args["to_id"]},
    )
    if not data:
        return "No path found between the two nodes."
    path = data[0] if isinstance(data, list) else data
    nodes = path.get("nodes", [])
    rels = path.get("relations", [])
    parts = []
    for i, n in enumerate(nodes):
        parts.append(f"[{n.get('label', '')}] {n.get('title', n.get('id', ''))}")
        if i < len(rels):
            parts.append(f"  --{rels[i]}-->")
    return "\n".join(parts)


HANDLERS = {
    "query_knowledge_base": handle_query_knowledge_base,
    "search_documents": handle_search_documents,
    "get_section_content": handle_get_section_content,
    "get_entity_graph": handle_get_entity_graph,
    "search_entities": handle_search_entities,
    "compare_documents": handle_compare_documents,
    "get_graph_path": handle_get_graph_path,
}


# ─── JSON-RPC dispatcher ──────────────────────────────────────────────────────

def dispatch(request: dict) -> dict:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cps-knowledge-base", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        try:
            content = handler(tool_args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": content}],
                    "isError": False,
                },
            }
        except Exception as exc:
            log.exception("Tool %s failed", tool_name)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# ─── Stdio transport ──────────────────────────────────────────────────────────

def run_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = dispatch(request)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    run_stdio()
