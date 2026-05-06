"""
services/model_manager.py
轻量级模型生命周期管理器：
- 追踪各模型的加载状态与最后使用时间
- 后台定时检查并卸载超时闲置的模型
- 提供内存使用快照供健康检查接口消费
"""
from __future__ import annotations

import gc
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL = 60      # 每分钟检查一次
_DEFAULT_IDLE_TIMEOUT = 300  # 5 分钟无使用则卸载


class ModelManager:
    """
    全局单例，用于跟踪"已加载"的大型模型。
    各 Service 在加载/卸载模型时调用 register/unregister，
    调用模型前调用 touch() 更新最后使用时间。
    """

    _instance: "ModelManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ModelManager":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._models: dict[str, dict[str, Any]] = {}
                obj._idle_timeout = _DEFAULT_IDLE_TIMEOUT
                obj._timer: threading.Timer | None = None
                obj._start_cleanup_loop()
                cls._instance = obj
        return cls._instance

    # ── 模型注册 ────────────────────────────────────────────────────────────

    def register(self, name: str, obj: Any) -> None:
        """记录模型已加载。"""
        self._models[name] = {"obj": obj, "last_used": time.time(), "loaded_at": time.time()}
        logger.info("[ModelManager] 注册模型: %s", name)

    def unregister(self, name: str) -> None:
        """主动卸载模型（释放内存）。"""
        entry = self._models.pop(name, None)
        if entry:
            del entry["obj"]
            gc.collect()
            logger.info("[ModelManager] 已卸载模型: %s", name)

    def touch(self, name: str) -> None:
        """更新最后使用时间（每次推理前调用）。"""
        if name in self._models:
            self._models[name]["last_used"] = time.time()

    def is_loaded(self, name: str) -> bool:
        return name in self._models

    # ── 状态查询 ────────────────────────────────────────────────────────────

    def loaded_models(self) -> list[dict]:
        now = time.time()
        return [
            {
                "name":      k,
                "idle_secs": int(now - v["last_used"]),
                "age_secs":  int(now - v["loaded_at"]),
            }
            for k, v in self._models.items()
        ]

    def memory_info(self) -> dict:
        """返回系统内存快照及已加载模型列表。"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb":     round(mem.total / 1e9, 1),
                "used_gb":      round(mem.used / 1e9, 1),
                "available_gb": round(mem.available / 1e9, 1),
                "percent":      round(mem.percent, 1),
                "models_loaded": self.loaded_models(),
            }
        except Exception as e:
            logger.debug("psutil 获取内存信息失败: %s", e)
            return {
                "total_gb":     0,
                "used_gb":      0,
                "available_gb": 0,
                "percent":      0,
                "models_loaded": self.loaded_models(),
            }

    # ── 自动卸载闲置模型 ────────────────────────────────────────────────────

    def _cleanup_idle(self) -> None:
        now = time.time()
        to_unload = [
            name for name, info in list(self._models.items())
            if now - info["last_used"] > self._idle_timeout
        ]
        for name in to_unload:
            logger.info("[ModelManager] 卸载闲置模型 (idle>%ds): %s", self._idle_timeout, name)
            self.unregister(name)

    def _start_cleanup_loop(self) -> None:
        def _loop():
            while True:
                time.sleep(_CLEANUP_INTERVAL)
                try:
                    self._cleanup_idle()
                except Exception as exc:
                    logger.debug("ModelManager cleanup 异常: %s", exc)

        t = threading.Thread(target=_loop, daemon=True, name="model-manager-cleanup")
        t.start()


# 全局单例
model_manager = ModelManager()
