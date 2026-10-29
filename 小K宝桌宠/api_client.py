"""OpenAI 兼容接口的轻量客户端，带有限网络重试。"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class APIError(RuntimeError):
    pass


class APIClient:
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 75) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout
        if not self.base_url.startswith(("https://", "http://")):
            raise APIError("接口地址必须以 https:// 或 http:// 开头。")
        if not self.api_key:
            raise APIError("尚未填写 API Key。")
        if not self.model:
            raise APIError("尚未填写模型名称。")

    @staticmethod
    def _http_message(error: HTTPError) -> str:
        try:
            body = json.loads(error.read().decode("utf-8"))
            return body.get("error", {}).get("message") or body.get("message") or str(body)
        except Exception:
            return str(error.reason)

    @staticmethod
    def _retry_delay(error: HTTPError, attempt: int) -> float:
        retry_after = error.headers.get("Retry-After") if error.headers else None
        try:
            return min(10.0, max(0.5, float(retry_after)))
        except (TypeError, ValueError):
            return float(attempt + 1)

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_network_error: Exception | None = None

        for attempt in range(3):
            request = Request(
                self.base_url + path,
                data=data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "XiaoKPet/2.1",
                },
                method="GET" if data is None else "POST",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                message = self._http_message(error)
                if error.code in self.RETRYABLE_STATUS and attempt < 2:
                    time.sleep(self._retry_delay(error, attempt))
                    continue
                raise APIError(f"接口返回 {error.code}：{message}") from error
            except (URLError, TimeoutError) as error:
                last_network_error = error
                if attempt < 2:
                    time.sleep(float(attempt + 1))
                    continue
            except json.JSONDecodeError as error:
                raise APIError("接口返回了无法识别的数据。") from error

        if isinstance(last_network_error, TimeoutError):
            raise APIError("连接有点慢，重试后仍然超时。请稍后再发一次。") from last_network_error
        reason = getattr(last_network_error, "reason", last_network_error)
        raise APIError(f"网络连接不稳定，自动重试后仍未成功：{reason}") from last_network_error

    def list_models(self) -> list[str]:
        result = self._request("/models")
        models = [item.get("id", "") for item in result.get("data", []) if isinstance(item, dict)]
        models = sorted(model for model in models if model)
        if not models:
            raise APIError("接口没有返回可用模型。")
        return models

    def chat(self, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        result = self._request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": messages,
                "max_tokens": 500,
                "stream": False,
            },
        )
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise APIError("接口没有返回有效的聊天内容。") from error
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        content = str(content).strip()
        if not content:
            raise APIError("接口返回了空白回复。")
        usage = result.get("usage", {}) if isinstance(result.get("usage", {}), dict) else {}
        return content, usage
