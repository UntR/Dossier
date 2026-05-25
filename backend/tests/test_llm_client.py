import json

from app.llm import client as llm_client
from app.llm.client import LLMClient


def test_litellm_is_loaded_lazily():
    assert llm_client.completion is None


def test_stream_chat_uses_litellm_completion_when_provider_configured(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return [
            {"choices": [{"delta": {"content": "第一段"}}]},
            {"choices": [{"delta": {"content": "第二段"}}]},
        ]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    chunks = list(LLMClient().stream_chat("anthropic/claude-haiku-4-5-20251001", [{"role": "user", "content": "hi"}]))

    assert chunks == ["第一段", "第二段"]
    assert calls == [
        {
            "model": "anthropic/claude-haiku-4-5-20251001",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
    ]


def test_stream_chat_passes_ollama_base_url_to_litellm(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return [{"choices": [{"delta": {"content": "ok"}}]}]

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    chunks = list(LLMClient().stream_chat("ollama/qwen3:1.7b", [{"role": "user", "content": "hi"}]))

    assert chunks == ["ok"]
    assert calls == [
        {
            "model": "ollama/qwen3:1.7b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "api_base": "http://ollama.test:11434",
        }
    ]


def test_stream_chat_passes_openai_api_base_to_litellm(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return [{"choices": [{"delta": {"content": "ok"}}]}]

    monkeypatch.setenv("OPENAI_API_BASE", "http://lmstudio.test/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    chunks = list(LLMClient().stream_chat("openai/google/gemma-4-e4b", [{"role": "user", "content": "hi"}]))

    assert chunks == ["ok"]
    assert calls == [
        {
            "model": "openai/google/gemma-4-e4b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "api_base": "http://lmstudio.test/v1",
            "api_key": "lm-studio",
        }
    ]


def test_complete_json_uses_litellm_json_mode(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": json.dumps({"events": [{"title": "模型事件"}]}, ensure_ascii=False)}}]}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    result = LLMClient().complete_json("anthropic/claude-haiku-4-5-20251001", [{"role": "user", "content": "extract"}])

    assert result == {"events": [{"title": "模型事件"}]}
    assert calls == [
        {
            "model": "anthropic/claude-haiku-4-5-20251001",
            "messages": [{"role": "user", "content": "extract"}],
            "response_format": {"type": "json_object"},
        }
    ]


def test_complete_json_passes_ollama_base_url_to_litellm(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": json.dumps({"events": []})}}]}

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    result = LLMClient().complete_json("ollama/qwen3:1.7b", [{"role": "user", "content": "extract"}])

    assert result == {"events": []}
    assert calls == [
        {
            "model": "ollama/qwen3:1.7b",
            "messages": [{"role": "user", "content": "extract"}],
            "response_format": {"type": "json_object"},
            "api_base": "http://ollama.test:11434",
        }
    ]


def test_complete_json_uses_json_schema_for_openai_api_base(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": json.dumps({"events": []})}}]}

    monkeypatch.setenv("OPENAI_API_BASE", "http://lmstudio.test/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    result = LLMClient().complete_json("openai/google/gemma-4-e4b", [{"role": "user", "content": "extract"}])

    assert result == {"events": []}
    assert calls == [
        {
            "model": "openai/google/gemma-4-e4b",
            "messages": [{"role": "user", "content": "extract"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "dossier_json",
                    "schema": {"type": "object"},
                    "strict": False,
                },
            },
            "api_base": "http://lmstudio.test/v1",
            "api_key": "lm-studio",
        }
    ]


def test_complete_json_returns_none_when_model_call_fails(monkeypatch):
    def fake_completion(**kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setenv("OPENAI_API_BASE", "http://lmstudio.test/v1")
    monkeypatch.setattr("app.llm.client.completion", fake_completion, raising=False)

    assert LLMClient().complete_json("openai/google/gemma-4-e4b", [{"role": "user", "content": "extract"}]) is None
