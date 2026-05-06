"""
scripts/run_association_mining.py
在离线环境中运行关联规则挖掘，结果写入 Redis。

用法：
    python scripts/run_association_mining.py
    python scripts/run_association_mining.py --min-support 0.03 --min-confidence 0.6
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REDIS_KEY_DOC  = "mining:document_associations"
REDIS_KEY_META = "mining:last_run"
REDIS_TTL      = 7 * 24 * 3600


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-support",    type=float, default=0.05)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--top-n",          type=int,   default=50)
    args = parser.parse_args()

    from src.core.database import get_driver
    from src.services.association_miner import AssociationMiner
    from src.services.infra.cache import get_redis

    logger.info("开始挖掘 min_support=%.2f min_confidence=%.2f", args.min_support, args.min_confidence)
    driver = get_driver()
    miner  = AssociationMiner()
    results = miner.mine_document_associations(
        driver,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        top_n=args.top_n,
    )

    implicit = sum(1 for r in results if r.get("is_implicit"))
    logger.info("挖掘完成：共 %d 组关联，其中隐性 %d 组", len(results), implicit)

    r = get_redis()
    r.setex(REDIS_KEY_DOC,  REDIS_TTL, json.dumps(results, ensure_ascii=False))
    r.setex(REDIS_KEY_META, REDIS_TTL, str(int(time.time())))
    logger.info("结果已写入 Redis key=%s", REDIS_KEY_DOC)

    # 打印摘要
    print(f"\n发现 {len(results)} 组关联（隐性 {implicit} 组）")
    for assoc in results[:5]:
        print(f"  {assoc['doc_a']} <-> {assoc['doc_b']}"
              f"  conf={assoc['confidence']:.2f}"
              f"  [{assoc['relationship']}]"
              f"  共同实体: {', '.join(assoc['common_entities'][:3])}")


if __name__ == "__main__":
    main()
