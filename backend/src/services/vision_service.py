"""
src/services/vision_service.py
统一视觉语言模型（VLM）服务

通过 VISION_MODE 环境变量切换两种运行模式：
  api   — 调用云端 VLM API（通义千问VL → 文心一言VL → 混元VL，按优先级自动降级）
  local — 加载本地模型（Qwen2-VL → InternVL2，按优先级自动降级）

主要接口：
  VisionService.analyze_image(image_path, task) → dict

task 取值：
  table   — 提取表格内容，返回 {"headers": [...], "rows": [[...]]}
  figure  — 理解示意图，返回 {"description": "...", "relations": [...], "steps": [...]}
  formula — 识别数学公式，返回 {"latex": "..."}
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 任务专用 Prompt ────────────────────────────────────────────────────────────

_PROMPTS: dict[str, str] = {
    "table": """你是一个航空工艺规范专家。请仔细分析图片中的表格，提取完整的行列数据。

要求：
- headers：表格第一行的列名列表（字符串数组，使用图中实际文字）
- rows：其余每行数据（二维字符串数组，行列顺序与原表一致，使用图中实际数据）
- caption：若表格有标题则填写，否则为空字符串

无论图中是否有表格，都必须只输出 JSON，不得复述问题、不得输出示例文字、不得输出任何解释。
- 若图中有表格：{"headers": ["实际列名1", "实际列名2"], "rows": [["实际值1", "实际值2"]], "caption": "实际标题或空字符串"}
- 若图中没有表格：{"headers": [], "rows": [], "caption": "", "note": "无表格"}""",

    "figure": """你是一个航空制造工艺规范专家。请仔细分析这张工艺示意图，理解其中的装配关系或工艺流程。

要求：
- description：对图片内容的详细中文描述（100字以内）
- relations：图中零件/组件之间的装配或连接关系（字符串数组，如 "A 装入 B"）
- steps：图中展示的操作步骤（字符串数组，顺序描述）
- tools：图中出现的工具名称（字符串数组）
- dimensions：图中标注的尺寸或规格（字符串数组）

只输出如下 JSON，不含任何额外文字：
{"description": "...", "relations": [...], "steps": [...], "tools": [...], "dimensions": [...]}""",

    "formula": """请识别图片中的数学公式或技术参数公式，转换为 LaTeX 格式。

要求：
- latex：完整的 LaTeX 公式字符串（不含 $$ 分隔符）
- description：公式的中文含义说明（30字以内）

只输出如下 JSON，不含任何额外文字：
{"latex": "...", "description": "..."}""",
}

_EMPTY_RESULTS: dict[str, dict] = {
    "table":   {"headers": [], "rows": [], "caption": ""},
    "figure":  {"description": "", "relations": [], "steps": [], "tools": [], "dimensions": []},
    "formula": {"latex": "", "description": ""},
}


def _load_image_b64(image_path: str) -> tuple[str, str]:
    """返回 (base64字符串, media_type)"""
    ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, media_type


def _parse_json_response(content: str, task: str) -> dict:
    """从 LLM 返回文本中提取 JSON，容错处理 markdown 代码块。"""
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        logger.warning("VisionService JSON 解析失败，task=%s，内容预览: %.100s", task, content)
        return dict(_EMPTY_RESULTS[task])


# ─────────────────────────────────────────────────────────────────────────────
# API 提供方
# ─────────────────────────────────────────────────────────────────────────────

class _QwenVLProvider:
    """通义千问VL — 使用 DashScope OpenAI 兼容端点"""

    name = "qwen-vl"

    def __init__(self):
        from ..core.config import settings
        self._api_key = settings.DASHSCOPE_API_KEY
        self._model   = settings.QWEN_VL_MODEL

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, image_path: str, task: str) -> dict:
        import requests
        b64, media_type = _load_image_b64(image_path)
        prompt = _PROMPTS[task]

        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 2048,
            },
            timeout=60,
        )
        body = resp.json()
        if "choices" not in body:
            raise RuntimeError(f"DashScope 无 choices: {body.get('error', body)}")
        return _parse_json_response(body["choices"][0]["message"]["content"], task)


class _ErnieVLProvider:
    """文心一言VL — 百度 AI 开放平台"""

    name = "ernie-vl"

    def __init__(self):
        from ..core.config import settings
        self._api_key    = settings.ERNIE_API_KEY
        self._secret_key = settings.ERNIE_SECRET_KEY

    def is_available(self) -> bool:
        return bool(self._api_key and self._secret_key)

    def _get_access_token(self) -> str:
        import requests
        resp = requests.post(
            "https://aip.baidubce.com/oauth/2.0/token",
            params={
                "grant_type":    "client_credentials",
                "client_id":     self._api_key,
                "client_secret": self._secret_key,
            },
            timeout=10,
        )
        return resp.json()["access_token"]

    def call(self, image_path: str, task: str) -> dict:
        import requests
        b64, _ = _load_image_b64(image_path)
        token  = self._get_access_token()
        prompt = _PROMPTS[task]

        resp = requests.post(
            f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-4.0-vl-8k"
            f"?access_token={token}",
            headers={"Content-Type": "application/json"},
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_base64", "image_base64": b64},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ]
            },
            timeout=60,
        )
        body = resp.json()
        if "result" not in body:
            raise RuntimeError(f"文心一言无 result: {body.get('error_msg', body)}")
        return _parse_json_response(body["result"], task)


class _HunYuanVLProvider:
    """混元VL — 腾讯云 OpenAI 兼容端点"""

    name = "hunyuan-vl"

    def __init__(self):
        from ..core.config import settings
        self._api_key = settings.HUNYUAN_API_KEY

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, image_path: str, task: str) -> dict:
        import requests
        b64, media_type = _load_image_b64(image_path)
        prompt = _PROMPTS[task]

        resp = requests.post(
            "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model": "hunyuan-vision",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 2048,
            },
            timeout=60,
        )
        body = resp.json()
        if "choices" not in body:
            raise RuntimeError(f"混元VL 无 choices: {body.get('error', body)}")
        return _parse_json_response(body["choices"][0]["message"]["content"], task)


# ─────────────────────────────────────────────────────────────────────────────
# 本地模型提供方
# ─────────────────────────────────────────────────────────────────────────────

class MLXVisionBackend:
    """
    MLX 本地 VLM 后端（Apple Silicon 专用）。

    通过 mlx-vlm 加载量化模型，速度远快于 transformers + torch 方式。
    单例懒加载：仅在首次 call() 时加载模型，不重复初始化。

    使用方式（在 VisionService 内由 VISION_MODE=local 触发）：
        backend = MLXVisionBackend()
        result  = backend.analyze("path/to/image.png", "figure")
    """

    name = "mlx-vlm-local"

    def __init__(self):
        from ..core.config import settings
        import os
        self._model_path = os.path.expanduser(settings.LOCAL_VLM_PATH)
        # 延迟加载字段
        self._model     = None
        self._processor = None
        self._config    = None
        self._generate            = None
        self._apply_chat_template = None

    def is_available(self) -> bool:
        """检查模型路径存在 + mlx_vlm 已安装。"""
        if not Path(self._model_path).exists():
            return False
        try:
            import mlx_vlm  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self) -> None:
        """首次调用时加载模型（后续调用直接复用）。"""
        if self._model is not None:
            return
        from mlx_vlm import load, generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config

        logger.info("加载本地 MLX VLM 模型: %s", self._model_path)
        self._model, self._processor = load(self._model_path)
        self._config                 = load_config(self._model_path)
        self._generate               = generate
        self._apply_chat_template    = apply_chat_template
        logger.info("MLX VLM 模型加载完成: %s", self._model_path)

    def call(self, image_path: str, task: str) -> dict:
        """
        调用 MLX VLM 分析图片。
        返回与其他提供方一致的结构化 dict。
        """
        self._load()
        prompt = _PROMPTS[task]

        # 格式化 prompt（携带图片占位符）
        formatted = self._apply_chat_template(
            self._processor,
            self._config,
            prompt,
            num_images=1,
        )

        # 生成回答（签名：generate(model, processor, prompt, image, max_tokens)）
        output = self._generate(
            self._model,
            self._processor,
            formatted,    # prompt 在前
            image_path,   # image 在后
            max_tokens=512,
        )

        # mlx_vlm.generate() 返回 GenerationResult 对象，需提取文本
        if hasattr(output, "text"):
            text = output.text
        else:
            text = str(output)

        return _parse_json_response(text, task)

    # 兼容旧式 analyze() 调用（与用户指定接口保持一致）
    def analyze(self, image_path: str, task: str) -> dict:
        return self.call(image_path, task)


class _Qwen2VLLocalProvider:
    """Qwen2-VL 本地推理"""

    name = "qwen2-vl-local"

    def __init__(self):
        from ..core.config import settings
        self._model_path = settings.LOCAL_VLM_PATH
        self._model      = None
        self._processor  = None

    def is_available(self) -> bool:
        return Path(self._model_path).exists()

    def _load(self):
        if self._model is not None:
            return
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        import torch
        logger.info("加载本地 Qwen2-VL 模型: %s", self._model_path)
        self._processor = AutoProcessor.from_pretrained(self._model_path)
        self._model = Qwen2VLForConditionalGeneration.from_pretrained(
            self._model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

    def call(self, image_path: str, task: str) -> dict:
        from PIL import Image as _PILImage
        self._load()
        prompt   = _PROMPTS[task]
        image    = _PILImage.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text_input = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=[text_input], images=[image], return_tensors="pt"
        ).to(self._model.device)
        out_ids = self._model.generate(**inputs, max_new_tokens=1024)
        trimmed = [
            out_ids[i][inputs.input_ids.shape[1]:]
            for i in range(len(out_ids))
        ]
        response = self._processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        return _parse_json_response(response, task)


class _InternVL2LocalProvider:
    """InternVL2 本地推理"""

    name = "internvl2-local"

    def __init__(self):
        from ..core.config import settings
        self._model_path = settings.LOCAL_VLM_BACKUP_PATH
        self._model      = None
        self._tokenizer  = None

    def is_available(self) -> bool:
        return Path(self._model_path).exists()

    def _load(self):
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModel
        import torch
        logger.info("加载本地 InternVL2 模型: %s", self._model_path)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_path, trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            self._model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        ).eval()

    def call(self, image_path: str, task: str) -> dict:
        import torch
        from PIL import Image as _PILImage
        self._load()
        prompt = _PROMPTS[task]
        image  = _PILImage.open(image_path).convert("RGB")

        # InternVL2 需要特殊预处理
        import torchvision.transforms as T
        from torchvision.transforms.functional import InterpolationMode

        def _build_transform(input_size=448):
            return T.Compose([
                T.Lambda(lambda img: img.convert("RGB")),
                T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

        pixel_values = _build_transform()(image).unsqueeze(0).to(
            dtype=torch.bfloat16, device=next(self._model.parameters()).device
        )
        generation_config = dict(max_new_tokens=1024, do_sample=False)
        response = self._model.chat(
            self._tokenizer,
            pixel_values,
            f"<image>\n{prompt}",
            generation_config,
        )
        return _parse_json_response(response, task)


# ─────────────────────────────────────────────────────────────────────────────
# VisionService 主类
# ─────────────────────────────────────────────────────────────────────────────

class VisionService:
    """
    统一 VLM 接口。

    使用 VISION_MODE 环境变量（默认 "api"）决定运行模式：
    - api:   按优先级尝试 QwenVL → ErnieVL → HunYuanVL，主服务不可用时自动切换备选
    - local: 按优先级尝试 Qwen2-VL → InternVL2
    """

    _VALID_TASKS = frozenset(["table", "figure", "formula"])

    def __init__(self):
        from ..core.config import settings
        self._mode      = settings.VISION_MODE.lower()
        self._providers = self._build_providers()

    def _build_providers(self) -> list:
        if self._mode == "local":
            # 优先：MLX 本地推理（Apple Silicon，量化快）
            # 降级：transformers Qwen2-VL → InternVL2
            return [
                MLXVisionBackend(),
                _Qwen2VLLocalProvider(),
                _InternVL2LocalProvider(),
            ]
        # api 模式：按优先级尝试 QwenVL → ErnieVL → HunYuanVL
        return [_QwenVLProvider(), _ErnieVLProvider(), _HunYuanVLProvider()]

    def analyze_image(self, image_path: str, task: str) -> dict[str, Any]:
        """
        分析图片，返回结构化结果。

        Args:
            image_path: 图片本地路径
            task:       "table" | "figure" | "formula"

        Returns:
            dict — 根据 task 返回不同字段，失败时返回对应的空结构
        """
        if task not in self._VALID_TASKS:
            raise ValueError(f"不支持的 task: {task}，有效值: {self._VALID_TASKS}")

        if not Path(image_path).exists():
            logger.warning("图片不存在: %s", image_path)
            return dict(_EMPTY_RESULTS[task])

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
        return dict(_EMPTY_RESULTS[task])

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


# ── 模块级单例（延迟初始化）────────────────────────────────────────────────────

_service: VisionService | None = None


def get_vision_service() -> VisionService:
    """获取全局 VisionService 单例（首次调用时初始化）。"""
    global _service
    if _service is None:
        _service = VisionService()
    return _service
