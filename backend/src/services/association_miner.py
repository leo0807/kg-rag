"""
services/association_miner.py
基于 Apriori 算法挖掘文档间实体共现的隐性关联。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _fetch_doc_entities(driver) -> dict[str, set[str]]:
    """从 Neo4j 查询每份文档包含的实体集合。"""
    with driver.session() as s:
        result = s.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)<-[:MENTIONED_IN]-(e)
            WHERE (e:Tool OR e:Material OR e:Process OR e:Constraint)
              AND d.title IS NOT NULL
              AND e.name IS NOT NULL
            RETURN d.name AS doc_id, collect(DISTINCT e.name) AS entities
        """)
        return {r["doc_id"]: set(r["entities"]) for r in result if r["entities"]}


def _fetch_explicit_refs(driver) -> set[tuple[str, str]]:
    """返回已有 REFERENCES 关系的文档对（有向），用于过滤显式引用。"""
    with driver.session() as s:
        result = s.run("""
            MATCH (a:Document)-[:REFERENCES]->(b:Document)
            RETURN a.name AS src, b.name AS tgt
        """)
        return {(r["src"], r["tgt"]) for r in result}


class AssociationMiner:
    """
    文档级别关联规则挖掘：
    - 输入：每份文档涉及的实体集合（事务数据库）
    - 输出：高置信度的实体共现关联，标注对应的文档对
    """

    def mine_document_associations(
        self,
        driver,
        min_support: float = 0.05,
        min_confidence: float = 0.7,
        top_n: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            from mlxtend.frequent_patterns import apriori, association_rules
            from mlxtend.preprocessing import TransactionEncoder
            import pandas as pd
        except ImportError as e:
            logger.error("mlxtend 未安装: %s", e)
            return []

        doc_entities = _fetch_doc_entities(driver)
        if len(doc_entities) < 3:
            logger.warning("文档实体数据不足（%d 份），跳过挖掘", len(doc_entities))
            return []

        explicit_refs = _fetch_explicit_refs(driver)

        doc_ids = list(doc_entities.keys())
        transactions = [list(doc_entities[d]) for d in doc_ids]

        # 编码为二进制矩阵
        te = TransactionEncoder()
        te_array = te.fit(transactions).transform(transactions)
        import pandas as pd
        df = pd.DataFrame(te_array, columns=te.columns_)

        # Apriori 挖掘频繁项集
        try:
            freq_items = apriori(
                df,
                min_support=min_support,
                use_colnames=True,
                max_len=3,
            )
        except Exception as e:
            logger.error("Apriori 挖掘失败: %s", e)
            return []

        if freq_items.empty:
            logger.info("未找到频繁项集，尝试降低 min_support")
            return []

        # 生成关联规则
        try:
            rules = association_rules(
                freq_items,
                metric="confidence",
                min_threshold=min_confidence,
            )
        except Exception as e:
            logger.warning("关联规则生成失败: %s", e)
            return []

        results: list[dict] = []
        seen_pairs: set[tuple[str, str]] = set()

        for _, rule in rules.iterrows():
            ante = list(rule["antecedents"])
            cons = list(rule["consequents"])
            common = ante + cons

            # 找涉及这些实体的文档
            docs_ante = [d for d, ents in doc_entities.items() if all(e in ents for e in ante)]
            docs_cons = [d for d, ents in doc_entities.items() if all(e in ents for e in cons)]

            for doc_a in docs_ante:
                for doc_b in docs_cons:
                    if doc_a == doc_b:
                        continue
                    pair = (min(doc_a, doc_b), max(doc_a, doc_b))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    # 过滤已有显式引用关系的文档对
                    is_explicit = (doc_a, doc_b) in explicit_refs or (doc_b, doc_a) in explicit_refs
                    results.append({
                        "doc_a":          doc_a,
                        "doc_b":          doc_b,
                        "common_entities": common,
                        "confidence":     round(float(rule["confidence"]), 3),
                        "support":        round(float(rule["support"]), 3),
                        "lift":           round(float(rule["lift"]), 3),
                        "relationship":   "显式引用" if is_explicit else "隐性关联",
                        "is_implicit":    not is_explicit,
                    })
            if len(results) >= top_n * 3:
                break

        # 按置信度排序，优先返回隐性关联
        results.sort(key=lambda x: (not x["is_implicit"], -x["confidence"]))
        return results[:top_n]
