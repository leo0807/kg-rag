"""Structured tools available to the agent."""

TOOLS = [
    {
        "name": "search_sections",
        "description": "在工艺规范中检索相关章节，适合查询具体工艺要求、操作步骤、技术参数",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询，尽量包含规范编号或工艺术语",
                },
                "doc_id": {
                    "type": "string",
                    "description": "限定在特定文档中检索，如 CPS1000，可选",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_section_content",
        "description": "获取指定章节的完整内容，适合已知章节号时精确获取",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "规范编号，如 CPS1000",
                },
                "section_number": {
                    "type": "string",
                    "description": "章节号，如 6.3.2",
                },
            },
            "required": ["doc_id", "section_number"],
        },
    },
    {
        "name": "compare_documents",
        "description": "对比两份规范文档在特定主题上的差异",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id_a": {
                    "type": "string",
                    "description": "第一份规范编号",
                },
                "doc_id_b": {
                    "type": "string",
                    "description": "第二份规范编号",
                },
                "topic": {
                    "type": "string",
                    "description": "对比主题，如'密封圈安装要求'",
                },
            },
            "required": ["doc_id_a", "doc_id_b", "topic"],
        },
    },
    {
        "name": "search_images",
        "description": "检索工艺规范中的相关工程图片，适合需要图示说明的工艺问题",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "规范编号，如 CPS1000，可选",
                },
                "topic": {
                    "type": "string",
                    "description": "图片主题关键词",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_graph_relations",
        "description": "获取某规范与其他规范的引用关系，用于追踪依赖链路",
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "规范编号",
                },
                "direction": {
                    "type": "string",
                    "enum": ["references", "referenced_by", "both"],
                    "description": "引用方向",
                    "default": "both",
                },
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "final_answer",
        "description": "当已收集足够信息，给出最终答案时调用此工具",
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "最终答案",
                },
                "citations": {
                    "type": "array",
                    "description": "引用的规范章节列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "section": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["answer"],
        },
    },
]
