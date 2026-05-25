from test_crud_api import unwrap


class FakeOllamaResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"models": [{"name": "qwen3:1.7b"}, {"name": "bge-m3:latest"}]}


class FakeOllamaClient:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def get(self, path: str):
        assert self.base_url == "http://ollama.test:11434"
        assert self.timeout == 1.0
        assert path == "/api/tags"
        return FakeOllamaResponse()


class FakeOpenAIResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"id": "google/gemma-4-e4b"}, {"id": "text-embedding-nomic-embed-text-v1.5"}]}


class FakeOpenAIClient:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def get(self, path: str):
        assert self.base_url == "http://lmstudio.test/v1"
        assert self.timeout == 1.0
        assert path == "/models"
        return FakeOpenAIResponse()


def test_settings_get_patch_and_model_probe(client, monkeypatch):
    settings = unwrap(client.get("/api/settings"))
    assert settings["chat_model"] == "anthropic/claude-sonnet-4-6"
    assert settings["extraction_model"] == "anthropic/claude-haiku-4-5-20251001"

    updated = unwrap(client.patch("/api/settings", json={"chat_model": "ollama/qwen2.5", "auto_extract_threshold": 0.7}))
    assert updated["chat_model"] == "ollama/qwen2.5"
    assert updated["auto_extract_threshold"] == 0.7

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setattr("app.api.settings.httpx.Client", FakeOllamaClient)
    models = unwrap(client.get("/api/settings/models"))
    anthropic = next(provider for provider in models["providers"] if provider["provider"] == "anthropic")
    ollama = next(provider for provider in models["providers"] if provider["provider"] == "ollama")
    assert anthropic["configured"] is True
    assert "anthropic/claude-sonnet-4-6" in anthropic["models"]
    assert ollama["configured"] is True


def test_model_probe_lists_ollama_tags(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setattr("app.api.settings.httpx.Client", FakeOllamaClient)

    models = unwrap(client.get("/api/settings/models"))

    ollama = next(provider for provider in models["providers"] if provider["provider"] == "ollama")
    assert ollama["configured"] is True
    assert ollama["models"] == ["ollama/qwen3:1.7b", "ollama/bge-m3:latest"]


def test_model_probe_lists_openai_compatible_models(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "http://lmstudio.test/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setattr("app.api.settings.httpx.Client", FakeOpenAIClient)

    models = unwrap(client.get("/api/settings/models"))

    openai = next(provider for provider in models["providers"] if provider["provider"] == "openai")
    assert openai["configured"] is True
    assert openai["models"] == ["openai/google/gemma-4-e4b", "openai/text-embedding-nomic-embed-text-v1.5"]
