from __future__ import annotations

import asyncio
import logging
logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, driver, embedding_service=None, milvus_collection=None, es_client=None):
        self.driver = driver
        self.embedding = embedding_service
        self.milvus = milvus_collection
        self.es = es_client

    async def execute(self, tool_name: str, tool_input: dict) -> dict:
        handlers = {
            "search_sections": self._search_sections,
            "get_section_content": self._get_section_content,
            "compare_documents": self._compare_documents,
            "search_images": self._search_images,
            "get_graph_relations": self._get_graph_relations,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"未知工具: {tool_name}"}
        return await handler(**tool_input)

    async def _search_sections(self, query: str, doc_id: str | None = None, top_k: int = 5) -> dict:
        def _run() -> list[dict]:
            from ...routers.query.core import do_retrieval

            search_query = f"{doc_id} {query}" if doc_id else query
            sections, _score_map, _expansion = do_retrieval(
                self.driver,
                search_query,
                "parallel_rrf",
                top_k,
                doc_id=doc_id or "",
            )
            return sections

        results = await asyncio.to_thread(_run)
        return {
            "sections": [
                {
                    "chunk_id": r["chunk_id"],
                    "doc_id": r["doc_id"],
                    "number": r.get("number", ""),
                    "title": r.get("title", ""),
                    "content": (r.get("content", "") or "")[:500],
                    "page_idx": r.get("page_idx"),
                    "bbox": r.get("bbox"),
                }
                for r in results[:top_k]
            ],
            "count": len(results),
        }

    async def _get_section_content(self, doc_id: str, section_number: str) -> dict:
        def _run() -> dict | None:
            with self.driver.session() as s:
                result = s.run(
                    """
                    MATCH (d:Document {doc_id: $doc_id})-[:HAS_SECTION]->(sec:Section)
                    WHERE sec.number = $number
                    RETURN sec.chunk_id AS chunk_id,
                           sec.title AS title,
                           sec.content AS content,
                           sec.page_idx AS page_idx
                    """,
                    doc_id=doc_id,
                    number=section_number,
                )
                row = result.single()
                return dict(row) if row else None

        row = await asyncio.to_thread(_run)
        if not row:
            return {"error": f"未找到 {doc_id} §{section_number}"}
        return row

    async def _compare_documents(self, doc_id_a: str, doc_id_b: str, topic: str) -> dict:
        a_task = self._search_sections(query=topic, doc_id=doc_id_a, top_k=5)
        b_task = self._search_sections(query=topic, doc_id=doc_id_b, top_k=5)
        images_a_task = self._search_images(topic=topic, doc_id=doc_id_a)
        images_b_task = self._search_images(topic=topic, doc_id=doc_id_b)
        results_a, results_b, images_a, images_b = await asyncio.gather(
            a_task, b_task, images_a_task, images_b_task
        )
        return {
            doc_id_a: {
                "sections": results_a.get("sections", []),
                "images": images_a.get("images", []),
            },
            doc_id_b: {
                "sections": results_b.get("sections", []),
                "images": images_b.get("images", []),
            },
            "images": images_a.get("images", []) + images_b.get("images", []),
            "comparison_steps": [
                f"{doc_id_a} 检索到 {len(results_a.get('sections', []))} 个章节",
                f"{doc_id_b} 检索到 {len(results_b.get('sections', []))} 个章节",
                f"{len(images_a.get('images', [])) + len(images_b.get('images', []))} 张相关图片",
            ],
            "comparison_hint": f"请对比{doc_id_a}和{doc_id_b}关于{topic}的异同",
        }

    async def _search_images(self, topic: str, doc_id: str | None = None) -> dict:
        def _run() -> list[dict]:
            with self.driver.session() as s:
                query = [
                    "MATCH (i:Image)",
                    "WHERE (toLower(coalesce(i.caption, '')) CONTAINS $needle OR toLower(coalesce(i.description, '')) CONTAINS $needle)",
                ]
                if doc_id:
                    query.append("AND i.doc_id = $doc_id")
                query.append(
                    "RETURN i.image_id AS image_id, i.doc_id AS doc_id, coalesce(i.page_num, i.page, 0) AS page_num, i.caption AS caption, i.description AS description, i.minio_path AS minio_path LIMIT 3"
                )
                rows = list(
                    s.run(" ".join(query), needle=(topic or "").lower(), doc_id=doc_id)
                )
                return [dict(row) for row in rows]

        results = await asyncio.to_thread(_run)
        for row in results:
            minio_path = row.get("minio_path") or ""
            row["url"] = f"/api/images/{row.get('image_id')}" if minio_path else None
        return {"images": results, "count": len(results)}

    async def _get_graph_relations(self, doc_id: str, direction: str = "both") -> dict:
        def _run() -> dict:
            with self.driver.session() as s:
                refs = []
                cited = []
                if direction in ("references", "both"):
                    refs = list(s.run(
                        """
                        MATCH (d:Document {doc_id: $id})-[:REFERENCES]->(t:Document)
                        RETURN t.doc_id as doc_id, t.title as title
                        LIMIT 10
                        """,
                        id=doc_id,
                    ))
                if direction in ("referenced_by", "both"):
                    cited = list(s.run(
                        """
                        MATCH (s:Document)-[:REFERENCES]->(d:Document {doc_id: $id})
                        RETURN s.doc_id as doc_id, s.title as title
                        LIMIT 10
                        """,
                        id=doc_id,
                    ))
                return {
                    "references": [dict(r) for r in refs] if direction != "referenced_by" else [],
                    "referenced_by": [dict(r) for r in cited] if direction != "references" else [],
                }

        return await asyncio.to_thread(_run)
