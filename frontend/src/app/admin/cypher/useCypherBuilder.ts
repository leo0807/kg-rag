import { useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";

export type NodeType = "Document" | "Section" | "Image" | "Table" | "Tool" | "Material" | "Process" | "Entity";
export type RelType = "" | "HAS_SECTION" | "REFERENCES" | "HAS_IMAGE" | "HAS_TABLE" | "HAS_SUBSECTION" | "REQUIRES_TOOL" | "USES_MATERIAL" | "NEXT_SECTION";
export type RelDir = "→" | "←" | "↔";

export const NODE_TYPES: NodeType[] = ["Document", "Section", "Image", "Table", "Tool", "Material", "Process", "Entity"];
export const REL_TYPES: RelType[] = ["", "HAS_SECTION", "REFERENCES", "HAS_IMAGE", "HAS_TABLE", "HAS_SUBSECTION", "REQUIRES_TOOL", "USES_MATERIAL", "NEXT_SECTION"];
export const REL_DIRS: RelDir[] = ["→", "←", "↔"];

export const NODE_PROPS: Record<NodeType, string[]> = {
  Document: ["doc_id", "title", "version", "issue_date"],
  Section:  ["chunk_id", "number", "title", "level"],
  Image:    ["chunk_id", "caption"],
  Table:    ["chunk_id", "caption"],
  Tool:     ["name"],
  Material: ["name"],
  Process:  ["name"],
  Entity:   ["name", "type"],
};

export const TEMPLATES = [
  { label: "查看文档的所有章节",   cypher: 'MATCH (d:Document {doc_id: "CPS1000"})-[:HAS_SECTION]->(s:Section)\nRETURN d.doc_id, s.number, s.title\nORDER BY s.seq_index\nLIMIT 50' },
  { label: "引用最多的文档 Top10", cypher: 'MATCH (d:Document)<-[:REFERENCES]-()\nRETURN d.doc_id, d.title, count(*) AS refs\nORDER BY refs DESC\nLIMIT 10' },
  { label: "统计各类节点数量",     cypher: 'MATCH (n)\nRETURN labels(n)[0] AS type, count(n) AS cnt\nORDER BY cnt DESC' },
  { label: "查找没有图片的文档",   cypher: 'MATCH (d:Document)\nWHERE NOT (d)-[:HAS_IMAGE]->()\nRETURN d.doc_id, d.title\nORDER BY d.doc_id LIMIT 25' },
  { label: "特定实体出现的章节",   cypher: 'MATCH (e:Entity {name: "液压接头"})<-[]-(s:Section)\nRETURN e.name, s.number, s.title LIMIT 25' },
  { label: "两文档间的引用路径",   cypher: 'MATCH p=(a:Document {doc_id: "CPS1000"})-[:REFERENCES*1..3]-(b:Document {doc_id: "CPS2000"})\nRETURN p LIMIT 10' },
];

export interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
  error: string | null;
}

export function useCypherBuilder() {
  const [nodeType, setNodeType] = useState<NodeType>("Document");
  const [propKey, setPropKey] = useState("");
  const [propVal, setPropVal] = useState("");
  const [relType, setRelType] = useState<RelType>("HAS_SECTION");
  const [relDir, setRelDir] = useState<RelDir>("→");
  const [targetType, setTargetType] = useState<NodeType | "">("Section");
  const [limitVal, setLimitVal] = useState(25);
  const [orderBy, setOrderBy] = useState("");
  const [cypher, setCypher] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);

  const buildCypher = useCallback(() => {
    const a = nodeType[0].toLowerCase();
    const propClause = propKey && propVal ? ` {${propKey}: "${propVal}"}` : "";
    let q = `MATCH (${a}:${nodeType}${propClause})`;
    if (relType && targetType) {
      const tb = targetType[0].toLowerCase();
      const tb2 = tb === a ? tb + "2" : tb;
      const rel = relDir === "→" ? `-[:${relType}]->(${tb2}:${targetType})`
        : relDir === "←" ? `<-[:${relType}]-(${tb2}:${targetType})`
        : `-[:${relType}]-(${tb2}:${targetType})`;
      q += rel + `\nRETURN ${a}.*, ${tb2}.*`;
    } else {
      q += `\nRETURN ${a}.*`;
    }
    if (orderBy) q += `\nORDER BY ${orderBy}`;
    q += `\nLIMIT ${limitVal}`;
    setCypher(q);
  }, [nodeType, propKey, propVal, relType, relDir, targetType, limitVal, orderBy]);

  async function execute() {
    if (!cypher.trim()) return;
    setRunning(true);
    try {
      const data = await fetchApi<QueryResult>("/api/admin/cypher/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: cypher }),
      });
      setResult(data);
    } catch (e) {
      setResult({ columns: [], rows: [], total: 0, error: String(e) });
    } finally {
      setRunning(false);
    }
  }

  return {
    nodeType, setNodeType, propKey, setPropKey, propVal, setPropVal,
    relType, setRelType, relDir, setRelDir, targetType, setTargetType,
    limitVal, setLimitVal, orderBy, setOrderBy,
    cypher, setCypher, running, result, setResult,
    buildCypher, execute,
    applyTemplate: (t: typeof TEMPLATES[number]) => { setCypher(t.cypher); setResult(null); },
  };
}
