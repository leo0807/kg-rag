"""
GET /api/audit/chain/{doc_id}
Returns the complete blockchain-backed change trail for a document.
Suitable for 适航 (airworthiness) audits and NADCAP compliance export.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ...services.blockchain.chain_audit import get_chain_history, verify_chain
from ...core.database import get_driver  # reuse DB dep pattern

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/chain/{doc_id}", summary="文档链上变更轨迹")
async def get_doc_chain(
    doc_id: str,
    verify: bool = Query(default=False, description="同时校验链完整性（慢）"),
) -> dict[str, Any]:
    """
    返回文档从创建至今的完整链上变更记录。

    每条记录包含：
    - version       — 文档版本号
    - content_hash  — SHA-256 内容摘要
    - prev_hash     — 前一条记录的哈希（形成哈希链）
    - record_hash   — 本条记录的哈希（链上存证）
    - operator      — 操作人工号
    - tx_id         — 区块链 TX hash（FISCO BCOS 上链时有值）
    - created_at    — 时间戳

    chain_valid 字段仅在 ?verify=true 时计算。
    """
    try:
        records = await get_chain_history(doc_id)
    except Exception as exc:
        log.error("chain_audit query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Chain query failed")

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No chain records found for doc_id={doc_id}",
        )

    result: dict[str, Any] = {
        "doc_id":  doc_id,
        "count":   len(records),
        "records": records,
    }

    if verify:
        result["chain_valid"] = verify_chain(records)

    return result


@router.get("/chain/{doc_id}/export", summary="导出链上审计报告（JSON）")
async def export_chain(doc_id: str) -> JSONResponse:
    """适航审查一键导出：返回可下载的 JSON 文件。"""
    try:
        records = await get_chain_history(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not records:
        raise HTTPException(status_code=404, detail=f"No records for {doc_id}")

    payload = {
        "doc_id":      doc_id,
        "chain_valid": verify_chain(records),
        "record_count": len(records),
        "records":     records,
    }
    filename = f"chain_audit_{doc_id}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
