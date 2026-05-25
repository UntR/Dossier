from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

completion = None


class LLMClient:
    def stream_chat(self, model: str, messages: list[dict[str, str]]) -> Iterator[str]:
        if not self._provider_configured(model):
            yield "未配置可用模型。请先在设置中配置 Anthropic、OpenAI、Google API key，或启动 Ollama / LM Studio。"
            return
        completion_fn = _completion()
        if completion_fn is None:
            yield "LiteLLM 依赖未安装，无法调用模型。"
            return
        try:
            for chunk in completion_fn(**_completion_kwargs(model, messages, stream=True)):
                content = _chunk_content(chunk)
                if content:
                    yield content
        except Exception as exc:
            yield f"模型调用失败：{exc}"

    def complete_json(self, model: str, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        if not self._provider_configured(model):
            return None
        completion_fn = _completion()
        if completion_fn is None:
            return None
        try:
            response = completion_fn(**_completion_kwargs(model, messages, response_format={"type": "json_object"}))
        except Exception:
            return None
        content = _message_content(response)
        if not content:
            return None
        return json.loads(content)

    def _provider_configured(self, model: str) -> bool:
        if model.startswith("anthropic/"):
            return bool(os.getenv("ANTHROPIC_API_KEY"))
        if model.startswith("openai/"):
            return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_BASE"))
        if model.startswith("gemini/"):
            return bool(os.getenv("GOOGLE_API_KEY"))
        if model.startswith("ollama/"):
            return bool(os.getenv("OLLAMA_BASE_URL"))
        return False


def _completion():
    global completion
    if completion is not None:
        return completion
    try:
        from litellm import completion as litellm_completion
    except ImportError:  # pragma: no cover - exercised only when dependency is missing at runtime
        return None
    completion = litellm_completion
    return completion


def _completion_kwargs(model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    request = {"model": model, "messages": messages, **kwargs}
    if model.startswith("openai/"):
        api_base = os.getenv("OPENAI_API_BASE")
        if api_base:
            request["api_base"] = api_base
            request["api_key"] = os.getenv("OPENAI_API_KEY") or "lm-studio"
            if request.get("response_format") == {"type": "json_object"}:
                request["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "dossier_json",
                        "schema": {"type": "object"},
                        "strict": False,
                    },
                }
    if model.startswith("ollama/"):
        api_base = os.getenv("OLLAMA_BASE_URL")
        if api_base:
            request["api_base"] = api_base
    return request


def _chunk_content(chunk: Any) -> str | None:
    choice = _first_choice(chunk)
    delta = _value(choice, "delta")
    return _value(delta, "content")


def _message_content(response: Any) -> str | None:
    choice = _first_choice(response)
    message = _value(choice, "message")
    return _value(message, "content")


def _first_choice(value: Any) -> Any:
    choices = _value(value, "choices") or []
    return choices[0] if choices else None


def _value(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
