from __future__ import annotations

NODE_TYPES: dict = {
    # ── 检索节点（9）────────────────────────────────────────
    "vector_search": {
        "label": "向量检索", "category": "retrieval", "color": "#1B6BB5", "icon": "database",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
        },
    },
    "bm25_search": {
        "label": "全文检索", "category": "retrieval", "color": "#1B6BB5", "icon": "search",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
        },
    },
    "graph_search": {
        "label": "图谱检索", "category": "retrieval", "color": "#1B6BB5", "icon": "share2",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "depth": {"type": "int", "default": 2, "min": 1, "max": 4, "label": "图谱深度"},
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
        },
    },
    "keyword_search": {
        "label": "关键词检索", "category": "retrieval", "color": "#1B6BB5", "icon": "type",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
            "fields": {"type": "multiselect", "default": ["title", "content"], "options": ["title", "content", "number"], "label": "搜索字段"},
            "operator": {"type": "select", "default": "OR", "options": ["AND", "OR"], "label": "关键词逻辑"},
        },
    },
    "fuzzy_search": {
        "label": "模糊检索", "category": "retrieval", "color": "#1B6BB5", "icon": "search-code",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
            "fuzziness": {"type": "select", "default": "AUTO", "options": ["0", "1", "2", "AUTO"], "label": "模糊度"},
        },
    },
    "semantic_search": {
        "label": "语义检索", "category": "retrieval", "color": "#1B6BB5", "icon": "brain",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
            "threshold": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0, "label": "相似度阈值"},
            "model": {"type": "select", "default": "bge-m3", "options": ["bge-m3", "bge-large", "bge-small"], "label": "Embedding模型"},
        },
    },
    "multi_query_search": {
        "label": "多查询检索", "category": "retrieval", "color": "#1B6BB5", "icon": "layers",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "num_queries": {"type": "int", "default": 3, "min": 2, "max": 5, "label": "扩展查询数"},
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "每路召回数量"},
        },
    },
    "section_filter_search": {
        "label": "章节范围检索", "category": "retrieval", "color": "#1B6BB5", "icon": "filter",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "召回数量"},
            "level_min": {"type": "int", "default": 1, "min": 1, "max": 4, "label": "最小章节层级"},
            "level_max": {"type": "int", "default": 4, "min": 1, "max": 4, "label": "最大章节层级"},
            "doc_filter": {"type": "text", "default": "", "label": "文档范围（逗号分隔编号）"},
        },
    },
    "table_search": {
        "label": "表格检索", "category": "retrieval", "color": "#1B6BB5", "icon": "table",
        "inputs": ["query"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "召回数量"},
            "min_rows": {"type": "int", "default": 2, "min": 1, "max": 10, "label": "最少行数"},
        },
    },
    # ── 处理节点（14）───────────────────────────────────────
    "rrf_fusion": {
        "label": "RRF融合", "category": "processing", "color": "#5A9E28", "icon": "git-merge",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "k": {"type": "int", "default": 60, "min": 1, "max": 200, "label": "RRF常数k"},
            "alpha": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "融合权重"},
            "alpha_source": {"type": "select", "default": "fixed", "options": ["fixed", "redis"], "label": "alpha来源"},
            "alpha_redis_key": {"type": "text", "default": "search:hybrid_alpha", "label": "Redis键"},
        },
    },
    "rerank": {
        "label": "重排序", "category": "processing", "color": "#5A9E28", "icon": "bar-chart",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "保留数量"},
        },
    },
    "hyde": {
        "label": "HyDE增强", "category": "processing", "color": "#5A9E28", "icon": "zap",
        "inputs": ["query"], "outputs": ["query"],
        "params": {
            "alpha": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "融合权重"},
        },
    },
    "graph_expand": {
        "label": "图谱扩展", "category": "processing", "color": "#5A9E28", "icon": "maximize",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "hops": {"type": "int", "default": 1, "min": 1, "max": 3, "label": "扩展跳数"},
        },
    },
    "dedup": {
        "label": "结果去重", "category": "processing", "color": "#5A9E28", "icon": "copy-x",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "similarity_threshold": {"type": "float", "default": 0.9, "min": 0.5, "max": 1.0, "label": "重复判定阈值"},
            "keep": {"type": "select", "default": "first", "options": ["first", "highest_score"], "label": "保留策略"},
        },
    },
    "score_filter": {
        "label": "分数过滤", "category": "processing", "color": "#5A9E28", "icon": "sliders",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "min_score": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "最低分数"},
            "max_results": {"type": "int", "default": 10, "min": 1, "max": 50, "label": "最多保留数"},
        },
    },
    "context_window": {
        "label": "上下文扩展", "category": "processing", "color": "#5A9E28", "icon": "expand",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "before_sections": {"type": "int", "default": 1, "min": 0, "max": 3, "label": "向前扩展章节数"},
            "after_sections": {"type": "int", "default": 1, "min": 0, "max": 3, "label": "向后扩展章节数"},
        },
    },
    "keyword_highlight": {
        "label": "关键词高亮", "category": "processing", "color": "#5A9E28", "icon": "highlighter",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "max_fragments": {"type": "int", "default": 3, "min": 1, "max": 10, "label": "最大片段数"},
            "fragment_size": {"type": "int", "default": 150, "min": 50, "max": 500, "label": "片段长度"},
        },
    },
    "doc_diversity": {
        "label": "文档多样性", "category": "processing", "color": "#5A9E28", "icon": "shuffle",
        "inputs": ["candidates"], "outputs": ["candidates"],
        "params": {
            "max_per_doc": {"type": "int", "default": 2, "min": 1, "max": 5, "label": "每文档最多保留"},
            "total_keep": {"type": "int", "default": 8, "min": 1, "max": 20, "label": "总保留数"},
        },
    },
    "query_expand": {
        "label": "查询扩展", "category": "processing", "color": "#5A9E28", "icon": "git-branch",
        "inputs": ["query"], "outputs": ["query"],
        "params": {
            "expand_type": {"type": "select", "default": "synonym", "options": ["synonym", "llm", "both"], "label": "扩展方式"},
            "max_terms": {"type": "int", "default": 5, "min": 1, "max": 10, "label": "最大扩展词数"},
        },
    },
    "query_rewrite": {
        "label": "查询改写", "category": "processing", "color": "#5A9E28", "icon": "pencil",
        "inputs": ["query"], "outputs": ["query"],
        "params": {
            "style": {"type": "select", "default": "technical", "options": ["technical", "simplified", "formal"], "label": "改写风格"},
            "add_context": {"type": "bool", "default": True, "label": "添加航空领域上下文"},
        },
    },
    "mmr_diversity": {
        "label": "MMR多样性排序", "category": "processing", "color": "#5A9E28", "icon": "layout-grid",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "lambda_param": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "label": "相关性/多样性平衡"},
            "top_k": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "保留数量"},
        },
    },
    "cross_encoder": {
        "label": "交叉编码器", "category": "processing", "color": "#5A9E28", "icon": "arrow-left-right",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "top_k": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "保留数量"},
            "model": {"type": "select", "default": "bge-reranker-v2-m3", "options": ["bge-reranker-v2-m3", "bge-reranker-large"], "label": "模型"},
        },
    },
    "entity_link": {
        "label": "实体链接", "category": "processing", "color": "#5A9E28", "icon": "link",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "expand_entity": {"type": "bool", "default": True, "label": "展开实体关联章节"},
            "max_entity_docs": {"type": "int", "default": 3, "min": 1, "max": 10, "label": "最多关联文档数"},
        },
    },
    # ── 生成节点（7）────────────────────────────────────────
    "llm_generate": {
        "label": "LLM生成", "category": "generation", "color": "#D4820A", "icon": "message-square",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "max_tokens": {"type": "int", "default": 1000, "min": 100, "max": 4000, "label": "最大Token"},
            "temperature": {"type": "float", "default": 0.1, "min": 0.0, "max": 1.0, "label": "温度"},
        },
    },
    "self_rag": {
        "label": "Self-RAG", "category": "generation", "color": "#D4820A", "icon": "refresh-cw",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "max_iterations": {"type": "int", "default": 3, "min": 1, "max": 5, "label": "最大迭代"},
        },
    },
    "summary_generate": {
        "label": "摘要生成", "category": "generation", "color": "#D4820A", "icon": "file-text",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "max_tokens": {"type": "int", "default": 300, "min": 100, "max": 1000, "label": "最大Token"},
            "format": {"type": "select", "default": "paragraph", "options": ["paragraph", "bullets", "numbered"], "label": "输出格式"},
        },
    },
    "structured_extract": {
        "label": "结构化提取", "category": "generation", "color": "#D4820A", "icon": "table-2",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "output_schema": {"type": "textarea", "default": '{"value": "", "unit": "", "condition": ""}', "label": "输出JSON结构"},
            "extract_type": {"type": "select", "default": "parameter", "options": ["parameter", "procedure", "material", "tool"], "label": "提取类型"},
        },
    },
    "checklist_generate": {
        "label": "清单生成", "category": "generation", "color": "#D4820A", "icon": "list-checks",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "max_items": {"type": "int", "default": 10, "min": 3, "max": 30, "label": "最多条目数"},
            "include_source": {"type": "bool", "default": True, "label": "附带来源引用"},
        },
    },
    "compare_generate": {
        "label": "对比生成", "category": "generation", "color": "#D4820A", "icon": "columns",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "aspects": {"type": "textarea", "default": "材料, 工艺, 参数, 注意事项", "label": "对比维度（逗号分隔）"},
            "format": {"type": "select", "default": "table", "options": ["table", "paragraph"], "label": "输出格式"},
        },
    },
    "citation_generate": {
        "label": "引用式生成", "category": "generation", "color": "#D4820A", "icon": "quote",
        "inputs": ["query", "candidates"], "outputs": ["answer"],
        "params": {
            "citation_style": {"type": "select", "default": "inline", "options": ["inline", "footnote", "endnote"], "label": "引用样式"},
            "max_tokens": {"type": "int", "default": 800, "min": 200, "max": 2000, "label": "最大Token"},
        },
    },
    # ── 控制节点（5）────────────────────────────────────────
    "condition_branch": {
        "label": "条件分支", "category": "control", "color": "#6B48C8", "icon": "git-fork",
        "inputs": ["query"], "outputs": ["query_a", "query_b"],
        "params": {
            "condition": {"type": "select", "default": "query_length", "options": ["query_length", "keyword_match", "always_a"], "label": "分支条件"},
            "threshold": {"type": "int", "default": 20, "min": 5, "max": 100, "label": "阈值（字符数）"},
        },
    },
    "merge": {
        "label": "结果合并", "category": "control", "color": "#6B48C8", "icon": "merge",
        "inputs": ["candidates_a", "candidates_b"], "outputs": ["candidates"],
        "params": {
            "strategy": {"type": "select", "default": "concat", "options": ["concat", "interleave", "union"], "label": "合并策略"},
            "dedup_after": {"type": "bool", "default": True, "label": "合并后去重"},
        },
    },
    "cache_check": {
        "label": "缓存检查", "category": "control", "color": "#6B48C8", "icon": "database-zap",
        "inputs": ["query"], "outputs": ["query"],
        "params": {
            "ttl_minutes": {"type": "int", "default": 60, "min": 5, "max": 1440, "label": "缓存时效（分钟）"},
            "similarity_threshold": {"type": "float", "default": 0.95, "min": 0.8, "max": 1.0, "label": "命中阈值"},
        },
    },
    "ab_test": {
        "label": "A/B 测试", "category": "control", "color": "#6B48C8", "icon": "flask-conical",
        "inputs": ["query"], "outputs": ["query_a", "query_b"],
        "params": {
            "ratio_a": {"type": "float", "default": 0.5, "min": 0.1, "max": 0.9, "label": "A组流量比例"},
            "experiment_name": {"type": "text", "default": "exp_1", "label": "实验名称"},
        },
    },
    "feedback_loop": {
        "label": "反馈循环", "category": "control", "color": "#6B48C8", "icon": "repeat",
        "inputs": ["query", "candidates"], "outputs": ["candidates"],
        "params": {
            "max_iterations": {"type": "int", "default": 2, "min": 1, "max": 5, "label": "最大迭代次数"},
            "quality_threshold": {"type": "float", "default": 0.8, "min": 0.5, "max": 1.0, "label": "质量阈值"},
        },
    },
}
