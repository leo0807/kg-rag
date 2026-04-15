"""
src/routers/ai_status.py
GET /api/ai-status — AI 服务状态健康检查

返回当前各 AI 服务的运行模式、使用模型及可用状态，
供运维人员快速确认 LLM / Embedding / VLM / Reranker 是否正常。

探测策略（快速、不产生计费）：
  LLM  local  → GET {OLLAMA_BASE_URL}/api/tags 确认 Ollama 在线，并校验目标模型已下载
  LLM  api    → POST 最小 chat 请求（max_tokens=1，timeout=6s）
  Embed local → 检查模型路径是否存在；若单例已加载则复用（不重复初始化）
  Embed api   → 用单词 "test" 调用 embed()，timeout=6s
  VLM         → 仅检查密钥 / 本地路径是否配置（避免昂贵图片调用）
  Reranker    → 检查本地路径 / API 配置项是否已填写
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


# ─────────────────────────────────────────────────────────────────────────────
# 响应模型
# ─────────────────────────────────────────────────────────────────────────────

class ServiceInfo(BaseModel):
    mode:       str
    provider:   str   = ""
    model:      str   = ""
    available:  bool  = False
    latency_ms: int   = -1    # -1 = 未探测
    note:       str   = ""


class AIStatusResponse(BaseModel):
    timestamp: int
    llm:       ServiceInfo
    embedding: ServiceInfo
    vlm:       ServiceInfo
    reranker:  ServiceInfo


# ─────────────────────────────────────────────────────────────────────────────
# 各服务探测函数
# ─────────────────────────────────────────────────────────────────────────────

async def _probe_llm() -> ServiceInfo:
    mode     = (settings.LLM_MODE     or "api").lower()
    provider = (settings.LLM_PROVIDER or "").lower()

    # 确定显示用的模型名
    _model_map = {
        "qwen":      settings.LLM_QWEN_MODEL     or "qwen-plus",
        "deepseek":  settings.LLM_DEEPSEEK_MODEL or "deepseek-chat",
        "ernie":     settings.LLM_ERNIE_MODEL     or "ernie-4.5-8k",
        "anthropic": settings.LLM_MODEL,
    }
    if mode == "local":
        _local_map = {
            "qwen":     settings.LOCAL_LLM_QWEN_MODEL     or "qwen2.5:7b",
            "deepseek": settings.LOCAL_LLM_DEEPSEEK_MODEL or "deepseek-r1:7b",
        }
        model = _local_map.get(provider, settings.OLLAMA_MODEL or "qwen2.5:7b")
    else:
        model = _model_map.get(provider, settings.LLM_MODEL)

    t0 = time.monotonic()

    # ── 本地 Ollama ──────────────────────────────────────────────────────────
    if mode == "local":
        try:
            import httpx
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                resp.raise_for_status()
                tags_data  = resp.json()
                model_list = [m.get("name", "") for m in tags_data.get("models", [])]
                # 宽松匹配：模型名前缀匹配（qwen2.5:7b 匹配 qwen2.5:7b-instruct 等）
                base = model.split(":")[0]
                found = any(base in m for m in model_list)
            latency_ms = int((time.monotonic() - t0) * 1000)
            note = "" if found else f"Ollama 在线但未找到模型 {model}，请先 ollama pull {model}"
            return ServiceInfo(mode=mode, provider=provider or "ollama", model=model,
                               available=found, latency_ms=latency_ms, note=note)
        except Exception as e:
            return ServiceInfo(mode=mode, provider=provider or "ollama", model=model,
                               available=False,
                               latency_ms=int((time.monotonic() - t0) * 1000),
                               note=f"Ollama 不可达: {e}")

    # ── 文心一言：仅校验密钥，不发 chat 请求（access_token 换取需额外延迟）────
    if provider == "ernie":
        ok = bool(settings.ERNIE_API_KEY and settings.ERNIE_SECRET_KEY)
        return ServiceInfo(mode=mode, provider=provider, model=model,
                           available=ok,
                           note="" if ok else "ERNIE_API_KEY / ERNIE_SECRET_KEY 未配置")

    # ── API 模式：发一次最小 chat 请求 ─────────────────────────────────────
    try:
        from ..services.llm_service import get_llm_service
        llm  = get_llm_service()
        text = await asyncio.to_thread(
            llm.chat,
            [{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout=6,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return ServiceInfo(mode=mode, provider=provider or "openai_compat",
                           model=llm.model_name,
                           available=bool(text), latency_ms=latency_ms)
    except Exception as e:
        return ServiceInfo(mode=mode, provider=provider or "openai_compat", model=model,
                           available=False,
                           latency_ms=int((time.monotonic() - t0) * 1000),
                           note=str(e)[:120])


async def _probe_embedding() -> ServiceInfo:
    mode     = (settings.EMBEDDING_MODE     or "local").lower()
    provider = (settings.EMBEDDING_PROVIDER or "").lower()

    if mode == "local":
        # 先看单例是否已加载（懒加载场景不强制初始化）
        from ..services import embedding_service as _esvc
        model_path = Path(settings.EMBEDDING_MODEL) if settings.EMBEDDING_MODEL \
                     else Path(__file__).parent.parent.parent / "models" / "bge-m3"
        path_ok = model_path.exists()

        if _esvc._service is not None:
            # 已加载 → 做一次真实 embed
            t0 = time.monotonic()
            try:
                await asyncio.to_thread(_esvc._service.embed, "test")
                return ServiceInfo(mode=mode, model=str(model_path), available=True,
                                   latency_ms=int((time.monotonic() - t0) * 1000))
            except Exception as e:
                return ServiceInfo(mode=mode, model=str(model_path), available=False,
                                   latency_ms=int((time.monotonic() - t0) * 1000),
                                   note=str(e)[:120])
        else:
            note = "" if path_ok else f"模型目录不存在: {model_path}"
            return ServiceInfo(mode=mode, model=str(model_path),
                               available=path_ok, latency_ms=-1,
                               note=note or "模型路径存在（首次调用时懒加载）")

    # API 模式 —— 真实调用
    if provider == "qwen":
        model = settings.EMBEDDING_QWEN_MODEL or "text-embedding-v3"
        key_ok = bool(settings.DASHSCOPE_API_KEY)
    else:
        model  = settings.EMBEDDING_MODEL or "text-embedding-ada-002"
        key_ok = bool(settings.EMBEDDING_API_KEY)

    if not key_ok:
        return ServiceInfo(mode=mode, provider=provider or "openai_compat", model=model,
                           available=False, note="API Key 未配置")

    t0 = time.monotonic()
    try:
        from ..services.embedding_service import get_embedding_service
        svc = get_embedding_service()
        await asyncio.to_thread(svc.embed, "test")
        return ServiceInfo(mode=mode, provider=provider or "openai_compat", model=model,
                           available=True, latency_ms=int((time.monotonic() - t0) * 1000))
    except Exception as e:
        return ServiceInfo(mode=mode, provider=provider or "openai_compat", model=model,
                           available=False,
                           latency_ms=int((time.monotonic() - t0) * 1000),
                           note=str(e)[:120])


async def _probe_vlm() -> ServiceInfo:
    """VLM 不发真实请求（图片调用昂贵），仅核查密钥 / 路径配置。"""
    mode = (settings.VISION_MODE or "api").lower()

    if mode == "local":
        primary  = Path(settings.LOCAL_VLM_PATH)
        backup   = Path(settings.LOCAL_VLM_BACKUP_PATH)
        if primary.exists():
            return ServiceInfo(mode=mode, provider="qwen2-vl-local",
                               model=str(primary), available=True,
                               note="路径存在（首次调用时懒加载）")
        if backup.exists():
            return ServiceInfo(mode=mode, provider="internvl2-local",
                               model=str(backup), available=True,
                               note="主选路径不存在，使用备用 InternVL2")
        return ServiceInfo(mode=mode, available=False,
                           note=f"本地 VLM 路径均不存在: {primary} / {backup}")

    # API 模式 —— 按优先级检查密钥
    if settings.DASHSCOPE_API_KEY:
        return ServiceInfo(mode=mode, provider="qwen-vl",
                           model=settings.QWEN_VL_MODEL or "qwen-vl-max",
                           available=True, note="密钥已配置（未发送实际请求）")
    if settings.ERNIE_API_KEY and settings.ERNIE_SECRET_KEY:
        return ServiceInfo(mode=mode, provider="ernie-vl",
                           model="ernie-4.0-vl-8k", available=True,
                           note="密钥已配置（未发送实际请求）")
    if settings.HUNYUAN_API_KEY:
        return ServiceInfo(mode=mode, provider="hunyuan-vl",
                           model="hunyuan-vision", available=True,
                           note="密钥已配置（未发送实际请求）")
    return ServiceInfo(mode=mode, available=False,
                       note="未找到可用 VLM API Key（DASHSCOPE / ERNIE / HUNYUAN）")


async def _probe_reranker() -> ServiceInfo:
    mode  = (settings.RERANKER_MODE or "local").lower()
    model = settings.RERANKER_MODEL or "models/bge-reranker-v2-m3"

    if mode == "local":
        path_ok = Path(model).exists()
        note    = "" if path_ok else f"模型路径不存在: {model}"
        return ServiceInfo(mode=mode, model=model,
                           available=path_ok,
                           note=note or "路径存在（首次调用时懒加载）")

    # API 模式
    key_ok = bool(settings.RERANKER_API_KEY and settings.RERANKER_API_URL)
    return ServiceInfo(mode=mode, model=model, available=key_ok,
                       note="" if key_ok else "RERANKER_API_URL / RERANKER_API_KEY 未配置")


# ─────────────────────────────────────────────────────────────────────────────
# 路由
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/ai-status", response_model=AIStatusResponse, summary="AI 服务状态")
async def ai_status():
    """
    返回当前各 AI 服务的运行模式、使用模型及可用状态。

    - **llm**       — 文本推理服务（LLM）
    - **embedding** — 文本向量化服务
    - **vlm**       — 视觉语言模型服务
    - **reranker**  — 检索重排序服务

    各服务同时探测，总延迟 ≤ 单个最慢服务超时时间（默认 6s）。
    """
    llm_info, emb_info, vlm_info, rnk_info = await asyncio.gather(
        _probe_llm(),
        _probe_embedding(),
        _probe_vlm(),
        _probe_reranker(),
        return_exceptions=False,
    )
    return AIStatusResponse(
        timestamp = int(time.time()),
        llm       = llm_info,
        embedding = emb_info,
        vlm       = vlm_info,
        reranker  = rnk_info,
    )
