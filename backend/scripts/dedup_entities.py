"""
scripts/dedup_entities.py
实体去重与归一化脚本

功能：
- 使用 Levenshtein 相似度找出高度相似的 Tool/Material/Process 节点
- 预览潜在重复项（dry_run=True）
- 执行归一化合并（保留优先名称，迁移所有关系）

用法：
    python scripts/dedup_entities.py --dry-run          # 预览重复项
    python scripts/dedup_entities.py --threshold 0.85  # 合并（相似度>=0.85）
    python scripts/dedup_entities.py --type Tool       # 只处理 Tool 节点
"""
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def levenshtein_ratio(s1: str, s2: str) -> float:
    """计算两个字符串的 Levenshtein 相似度（0-1）"""
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    # dp table
    dp = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        new_dp = [i]
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            new_dp.append(min(dp[j] + 1, new_dp[-1] + 1, dp[j - 1] + cost))
        dp = new_dp
    dist = dp[len2]
    return 1.0 - dist / max(len1, len2)


def find_duplicates(
    driver,
    node_type: str,
    threshold: float = 0.85,
) -> list[tuple[str, str, float]]:
    """找出所有相似度超过阈值的实体对"""
    with driver.session() as session:
        result = session.run(
            f"MATCH (e:{node_type}) RETURN e.name AS name ORDER BY e.name"
        )
        names = [r["name"] for r in result if r["name"]]

    logger.info("共 %d 个 %s 节点，开始计算相似度...", len(names), node_type)

    duplicates = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ratio = levenshtein_ratio(names[i], names[j])
            if ratio >= threshold:
                duplicates.append((names[i], names[j], ratio))

    duplicates.sort(key=lambda x: -x[2])
    return duplicates


def merge_entities(
    driver,
    node_type: str,
    keep_name: str,
    merge_name: str,
) -> int:
    """将 merge_name 节点的所有关系迁移到 keep_name，然后删除 merge_name"""
    with driver.session() as session:
        # 获取需要迁移的关系类型
        result = session.run(f"""
            MATCH (src:{node_type} {{name: $merge_name}})-[r]->(tgt)
            RETURN DISTINCT type(r) AS rel_type, tgt
        """, merge_name=merge_name)
        out_rels = [(r["rel_type"], r["tgt"]) for r in result]

        result = session.run(f"""
            MATCH (src)-[r]->(tgt:{node_type} {{name: $merge_name}})
            RETURN DISTINCT type(r) AS rel_type, src
        """, merge_name=merge_name)
        in_rels = [(r["rel_type"], r["src"]) for r in result]

        # 创建 keep 节点（如果不存在）并迁移关系
        session.run(f"""
            MERGE (keep:{node_type} {{name: $keep_name}})
        """, keep_name=keep_name)

        # 迁移出边
        for rel_type, tgt in out_rels:
            tgt_id = tgt.element_id
            session.run(f"""
                MATCH (keep:{node_type} {{name: $keep}})
                MATCH (tgt) WHERE elementId(tgt) = $tgt_id
                MERGE (keep)-[:{rel_type}]->(tgt)
            """, keep=keep_name, tgt_id=tgt_id)

        # 迁移入边
        for rel_type, src in in_rels:
            src_id = src.element_id
            session.run(f"""
                MATCH (src) WHERE elementId(src) = $src_id
                MATCH (keep:{node_type} {{name: $keep}})
                MERGE (src)-[:{rel_type}]->(keep)
            """, src_id=src_id, keep=keep_name)

        # 删除 merge_name 节点
        session.run(f"""
            MATCH (e:{node_type} {{name: $merge_name}})
            DETACH DELETE e
        """, merge_name=merge_name)

    logger.info("合并: %s → %s (迁移 %d 出边, %d 入边)", merge_name, keep_name, len(out_rels), len(in_rels))
    return len(out_rels) + len(in_rels)


def main():
    parser = argparse.ArgumentParser(description="实体去重与归一化")
    parser.add_argument("--threshold", type=float, default=0.85, help="相似度阈值 (默认 0.85)")
    parser.add_argument("--type",      default="",               help="节点类型: Tool|Material|Process，空=全部")
    parser.add_argument("--dry-run",   action="store_true",      help="只预览，不执行合并")
    parser.add_argument("--auto",      action="store_true",      help="自动合并（不询问），相似度>=0.92 时")
    args = parser.parse_args()

    from src.core.database import get_driver
    driver = get_driver()

    node_types = [args.type] if args.type else ["Tool", "Material", "Process"]
    total_merged = 0

    for ntype in node_types:
        dups = find_duplicates(driver, ntype, threshold=args.threshold)
        if not dups:
            logger.info("%s: 未发现重复项", ntype)
            continue

        logger.info("\n%s 重复项（%d 对）：", ntype, len(dups))
        for a, b, score in dups:
            logger.info("  %.3f  %s  ↔  %s", score, a, b)

        if args.dry_run:
            continue

        for a, b, score in dups:
            # 保留较短的（通常更规范），合并较长的
            keep_name  = a if len(a) <= len(b) else b
            merge_name = b if keep_name == a else a

            if args.auto and score >= 0.92:
                merged = merge_entities(driver, ntype, keep_name, merge_name)
                total_merged += 1
            else:
                ans = input(f"合并 '{merge_name}' → '{keep_name}' (相似度={score:.3f})? [y/N/skip] ").strip().lower()
                if ans == "y":
                    merged = merge_entities(driver, ntype, keep_name, merge_name)
                    total_merged += 1
                elif ans == "skip":
                    break

    if not args.dry_run:
        logger.info("\n合并完成，共合并 %d 个节点", total_merged)


if __name__ == "__main__":
    main()
