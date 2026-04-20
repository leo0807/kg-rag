"""
src/services/query_expander.py
基于图谱 SYNONYM_OF 关系的查询扩展服务
"""
import logging
import re
from neo4j import Driver

logger = logging.getLogger(__name__)

# 航空领域常见的停用词，不参与近义词匹配
_STOP_WORDS = {"什么", "要求", "规定", "如何", "怎么", "哪些", "工艺", "标准", "规范"}

def expand_query(driver: Driver, question: str) -> str:
    """
    对查询语句进行近义词扩展。
    返回扩展后的查询字符串（如 "钛合金 OR TC4 OR Ti-6Al-4V"）
    """
    # 1. 提取潜在的实体词（中文 2 字以上，或英文/数字词）
    potential_terms = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9\-]{2,}', question)
    
    # 过滤停用词
    terms = [t for t in potential_terms if t not in _STOP_WORDS]
    if not terms:
        return question

    expanded_map = {} # term -> set(synonyms)

    try:
        with driver.session() as session:
            # 2. 从 Neo4j 查找近义词
            # 匹配逻辑：(term)-[:SYNONYM_OF]-(synonym)
            result = session.run("""
                UNWIND $terms AS term
                MATCH (e {name: term})-[:SYNONYM_OF]-(syn)
                RETURN term, collect(DISTINCT syn.name) AS synonyms
            """, terms=terms)
            
            for r in result:
                expanded_map[r["term"]] = set(r["synonyms"])
    except Exception as e:
        logger.warning("查询扩展失败（数据库连接问题）: %s", e)
        return question

    if not expanded_map:
        return question

    # 3. 构造扩展后的查询语句 (Elasticsearch / Neo4j Fulltext 语法)
    # 将原词替换为 (原词 OR 近义词1 OR 近义词2)
    final_query = question
    for term, syns in expanded_map.items():
        if syns:
            syn_list = [term] + list(syns)
            # 拼接到一起，用 OR 连接
            expansion = "(" + " OR ".join(syn_list) + ")"
            # 只替换完整的词
            final_query = re.sub(rf'\b{re.escape(term)}\b', expansion, final_query)
            # 针对中文没 \b 的特殊处理
            if final_query == question:
                final_query = final_query.replace(term, expansion)

    logger.info("查询扩展: '%s' -> '%s'", question, final_query)
    return final_query
