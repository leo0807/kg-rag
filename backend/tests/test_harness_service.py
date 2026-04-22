from src.services.ops import harness_service as svc


def setup_function():
    svc.DO_RETRIEVAL = None
    svc.ANSWER_GENERATOR = None


def test_build_execution_plan_detects_drawings_and_references():
    plan = svc.build_execution_plan("CPS1000 工程图纸的引用依据是什么？", doc_id="CPS1000")

    assert plan["strategy"] == "graph_augmented"
    assert "drawings" in plan["intents"]
    assert "references" in plan["intents"]
    assert any(step["tool"] == "drawing_search" for step in plan["steps"])


def test_search_image_evidence_dedupes_duplicate_rows(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_query_image_rows",
        lambda *args, **kwargs: [
            {
                "image_id": "img-1",
                "doc_id": "CPS1000",
                "caption": "主视图",
                "description": "",
                "drawing_summary": "结构总览",
                "is_drawing": True,
                "minio_path": "a.jpg",
                "page": 2,
                "section_number": "3",
                "section_title": "工程图纸",
                "keyword_hits": 2,
            },
            {
                "image_id": "img-1",
                "doc_id": "CPS1000",
                "caption": "重复记录",
                "description": "",
                "drawing_summary": "重复",
                "is_drawing": True,
                "minio_path": "a.jpg",
                "page": 2,
                "section_number": "3",
                "section_title": "工程图纸",
                "keyword_hits": 1,
            },
        ],
    )

    images = svc.search_image_evidence(
        driver=None,
        question="CPS1000 工程图纸",
        doc_id="CPS1000",
        drawing_only=True,
    )

    assert len(images) == 1
    assert images[0]["image_id"] == "img-1"
    assert images[0]["url"] == "/api/images/img-1"


def test_run_harness_query_merges_sections_and_images(monkeypatch):
    monkeypatch.setattr(
        svc,
        "DO_RETRIEVAL",
        lambda driver, question, strategy, top_k, use_hyde=False, hyde_alpha=0.5, doc_id="": (
            [
                {
                    "chunk_id": "CPS1000_3",
                    "doc_id": "CPS1000",
                    "number": "3",
                    "title": "工程图纸",
                    "content": "本章给出工程图纸和装配示意。",
                    "retrieval_trace": ["fulltext:es", "vector:milvus"],
                    "source_type": ["fulltext", "vector"],
                    "rerank_score": 0.91,
                }
            ],
            {},
        ),
    )
    monkeypatch.setattr(
        svc,
        "search_image_evidence",
        lambda *args, **kwargs: [
            {
                "image_id": "img-1",
                "doc_id": "CPS1000",
                "summary": "图纸包含装配关系和件号标注。",
                "caption": "工程图纸",
                "is_drawing": True,
                "keyword_hits": 3,
                "url": "/api/images/img-1",
            }
        ],
    )
    monkeypatch.setattr(
        svc,
        "ANSWER_GENERATOR",
        lambda question, context, history: ("综合章节和图纸后得到答案", {"prompt_tokens": 1, "completion_tokens": 1}),
    )

    result = svc.run_harness_query(
        driver=None,
        question="CPS1000 的工程图纸讲了什么？",
        top_k=5,
        doc_id="CPS1000",
    )

    assert result["answer"] == "综合章节和图纸后得到答案"
    assert result["runtime"]["section_hits"] == 1
    assert result["runtime"]["image_hits"] == 1
    assert result["section_sources"][0]["chunk_id"] == "CPS1000_3"
    assert result["image_sources"][0]["image_id"] == "img-1"
