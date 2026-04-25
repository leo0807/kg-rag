from __future__ import annotations

from ..runtime.model_settings import get_runtime_settings_namespace
from .vision_support import PROMPTS, load_image_b64, parse_json_response


class _QwenVLProvider:
    name = "qwen-vl"

    def __init__(self):
        runtime_settings = get_runtime_settings_namespace()
        self._api_key = runtime_settings.DASHSCOPE_API_KEY
        self._model = runtime_settings.QWEN_VL_MODEL

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, image_path: str, task: str) -> dict:
        import requests

        b64, media_type = load_image_b64(image_path)
        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                            {"type": "text", "text": PROMPTS[task]},
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
        return parse_json_response(body["choices"][0]["message"]["content"], task)


class _ErnieVLProvider:
    name = "ernie-vl"

    def __init__(self):
        runtime_settings = get_runtime_settings_namespace()
        self._api_key = runtime_settings.ERNIE_API_KEY
        self._secret_key = runtime_settings.ERNIE_SECRET_KEY

    def is_available(self) -> bool:
        return bool(self._api_key and self._secret_key)

    def _get_access_token(self) -> str:
        import requests

        resp = requests.post(
            "https://aip.baidubce.com/oauth/2.0/token",
            params={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._secret_key,
            },
            timeout=10,
        )
        return resp.json()["access_token"]

    def call(self, image_path: str, task: str) -> dict:
        import requests

        b64, _ = load_image_b64(image_path)
        token = self._get_access_token()
        resp = requests.post(
            "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-4.0-vl-8k"
            f"?access_token={token}",
            headers={"Content-Type": "application/json"},
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_base64", "image_base64": b64},
                            {"type": "text", "text": PROMPTS[task]},
                        ],
                    }
                ]
            },
            timeout=60,
        )
        body = resp.json()
        if "result" not in body:
            raise RuntimeError(f"文心一言无 result: {body.get('error_msg', body)}")
        return parse_json_response(body["result"], task)


class _HunYuanVLProvider:
    name = "hunyuan-vl"

    def __init__(self):
        runtime_settings = get_runtime_settings_namespace()
        self._api_key = runtime_settings.HUNYUAN_API_KEY

    def is_available(self) -> bool:
        return bool(self._api_key)

    def call(self, image_path: str, task: str) -> dict:
        import requests

        b64, media_type = load_image_b64(image_path)
        resp = requests.post(
            "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={
                "model": "hunyuan-vision",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                            {"type": "text", "text": PROMPTS[task]},
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
        return parse_json_response(body["choices"][0]["message"]["content"], task)
