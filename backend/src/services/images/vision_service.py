"""Vision service facade and runtime selector."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..runtime.model_settings import get_runtime_settings_namespace
from .vision_api_providers import _ErnieVLProvider, _HunYuanVLProvider, _QwenVLProvider
from .vision_local_providers import MLXVisionBackend, _InternVL2LocalProvider, _Qwen2VLLocalProvider
from .vision_support import EMPTY_RESULTS

logger = logging.getLogger(__name__)

class VisionService:
    _VALID_TASKS = frozenset(["table", "figure", "formula"])

    def __init__(self):
        runtime_settings = get_runtime_settings_namespace()
        self._mode = runtime_settings.VISION_MODE.lower()
        self._providers = self._build_providers()

    def _build_providers(self) -> list:
        if self._mode == "local":
            return [MLXVisionBackend(), _Qwen2VLLocalProvider(), _InternVL2LocalProvider()]
        return [_QwenVLProvider(), _ErnieVLProvider(), _HunYuanVLProvider()]

    def analyze_image(self, image_path: str, task: str) -> dict[str, Any]:
        """
        Analyze one image with the configured VLM providers.
        """
        if task not in self._VALID_TASKS:
            raise ValueError(f"不支持的 task: {task}，有效值: {self._VALID_TASKS}")

        if not Path(image_path).exists():
            logger.warning("图片不存在: %s", image_path)
            return dict(EMPTY_RESULTS[task])

        for provider in self._providers:
            if not provider.is_available():
                logger.debug("跳过不可用提供方: %s", provider.name)
                continue
            try:
                result = provider.call(image_path, task)
                logger.info(
                    "VisionService [%s] task=%s 完成: %s",
                    provider.name, task, image_path
                )
                return result
            except Exception as e:
                logger.warning(
                    "VisionService [%s] task=%s 失败，尝试下一个: %s",
                    provider.name, task, e
                )

        logger.error("所有 VLM 提供方均失败，task=%s image=%s", task, image_path)
        return dict(EMPTY_RESULTS[task])

    def batch_analyze(
        self,
        items: list[dict],
        task: str,
        image_key: str = "path",
    ) -> list[dict]:
        """
        批量分析，每项结果合并回原 dict。

        Args:
            items:     每项包含 image_key 字段的字典列表
            task:      "table" | "figure" | "formula"
            image_key: items 中图片路径对应的键名

        Returns:
            原 items，每项追加 "vision_result" 字段
        """
        results = []
        for item in items:
            path   = item.get(image_key, "")
            result = self.analyze_image(path, task)
            results.append({**item, "vision_result": result})
        return results


_services: dict[tuple[str, str], VisionService] = {}


def get_vision_service() -> VisionService:
    """按当前运行时配置返回 VisionService。"""
    runtime_settings = get_runtime_settings_namespace()
    key = (runtime_settings.VISION_MODE, runtime_settings.QWEN_VL_MODEL)
    if key not in _services:
        _services[key] = VisionService()
    return _services[key]
