from __future__ import annotations

import logging
from pathlib import Path

from .vision_support import PROMPTS, parse_json_response

logger = logging.getLogger(__name__)


class MLXVisionBackend:
    name = "mlx-vlm-local"

    def __init__(self):
        from ...core.config import settings
        import os

        self._model_path = os.path.expanduser(settings.LOCAL_VLM_PATH)
        self._model = None
        self._processor = None
        self._config = None
        self._generate = None
        self._apply_chat_template = None

    def is_available(self) -> bool:
        if not Path(self._model_path).exists():
            return False
        try:
            import mlx_vlm  # noqa: F401

            return True
        except ImportError:
            return False

    def _load(self) -> None:
        if self._model is not None:
            return
        from mlx_vlm import generate, load
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config

        logger.info("加载本地 MLX VLM 模型: %s", self._model_path)
        self._model, self._processor = load(self._model_path)
        self._config = load_config(self._model_path)
        self._generate = generate
        self._apply_chat_template = apply_chat_template
        logger.info("MLX VLM 模型加载完成: %s", self._model_path)

    def call(self, image_path: str, task: str) -> dict:
        self._load()
        formatted = self._apply_chat_template(self._processor, self._config, PROMPTS[task], num_images=1)
        output = self._generate(self._model, self._processor, formatted, image_path, max_tokens=512)
        text = output.text if hasattr(output, "text") else str(output)
        return parse_json_response(text, task)

    def analyze(self, image_path: str, task: str) -> dict:
        return self.call(image_path, task)


class _Qwen2VLLocalProvider:
    name = "qwen2-vl-local"

    def __init__(self):
        from ...core.config import settings

        self._model_path = settings.LOCAL_VLM_PATH
        self._model = None
        self._processor = None

    def is_available(self) -> bool:
        return Path(self._model_path).exists()

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

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
        image = _PILImage.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": PROMPTS[task]},
                ],
            }
        ]
        text_input = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[text_input], images=[image], return_tensors="pt").to(self._model.device)
        out_ids = self._model.generate(**inputs, max_new_tokens=1024)
        trimmed = [out_ids[i][inputs.input_ids.shape[1] :] for i in range(len(out_ids))]
        response = self._processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return parse_json_response(response, task)


class _InternVL2LocalProvider:
    name = "internvl2-local"

    def __init__(self):
        from ...core.config import settings

        self._model_path = settings.LOCAL_VLM_BACKUP_PATH
        self._model = None
        self._tokenizer = None

    def is_available(self) -> bool:
        return Path(self._model_path).exists()

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModel, AutoTokenizer

        logger.info("加载本地 InternVL2 模型: %s", self._model_path)
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_path, trust_remote_code=True)
        self._model = AutoModel.from_pretrained(
            self._model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        ).eval()

    def call(self, image_path: str, task: str) -> dict:
        import torch
        import torchvision.transforms as T
        from PIL import Image as _PILImage
        from torchvision.transforms.functional import InterpolationMode

        self._load()
        image = _PILImage.open(image_path).convert("RGB")

        def _build_transform(input_size=448):
            return T.Compose(
                [
                    T.Lambda(lambda img: img.convert("RGB")),
                    T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
                    T.ToTensor(),
                    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ]
            )

        pixel_values = _build_transform()(image).unsqueeze(0).to(
            dtype=torch.bfloat16,
            device=next(self._model.parameters()).device,
        )
        response = self._model.chat(
            self._tokenizer,
            pixel_values,
            f"<image>\n{PROMPTS[task]}",
            dict(max_new_tokens=1024, do_sample=False),
        )
        return parse_json_response(response, task)
