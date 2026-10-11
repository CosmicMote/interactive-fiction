from __future__ import annotations

from types import SimpleNamespace

import httpx
import ollama
import pytest

from fiction import config
from fiction.backends import BackendError, ClaudeBackend, OllamaBackend, installed_models, make_backend, make_backends
from fiction.schema import SaveFile, StoryConfig


def test_v1_save_config_upgrades_to_model_list():
    for mode, expected in [
        ("local", ["ollama:qwen3.6:35b-a3b"]),
        ("claude", ["claude:claude-sonnet-5-5"]),
        ("compare", ["ollama:qwen3.6:35b-a3b", "claude:claude-sonnet-5-5"]),
    ]:
        cfg = StoryConfig.model_validate(
            {"length": "short", "mode": mode, "ollama_model": "qwen3.6:35b-a3b", "claude_model": "claude-sonnet-5-5"}
        )
        assert cfg.models == expected


def test_v1_save_file_loads():
    record = SaveFile.model_validate({
        "version": 1, "name": "old", "status": "in_progress",
        "story": {"config": {"length": "short", "mode": "local", "ollama_model": "llama3.1:latest",
                             "claude_model": "claude-sonnet-5-5"}},
    })
    assert record.story.config.models == ["ollama:llama3.1:latest"]


def test_every_catalog_model_builds(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    for model_id, option in config.MODELS.items():
        backend = make_backend(model_id)
        assert isinstance(backend, OllamaBackend if option.provider == "ollama" else ClaudeBackend)
        assert backend.label == option.label


def test_same_model_twice_gets_independent_backends():
    a, b = make_backends(StoryConfig(models=["ollama:llama3.1:latest", "ollama:llama3.1:latest"]))
    assert a is not b


@pytest.mark.parametrize("model_id", [m for m in config.MODELS if m.startswith("claude:")])
def test_claude_request_respects_per_model_settings(monkeypatch, model_id):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    backend = make_backend(model_id)
    sent = {}

    def fake_create(**kwargs):
        sent.update(kwargs)
        text = '{"narration": "n", "established_facts": [], "act": "setup", "concluded": false}'
        return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               content=[SimpleNamespace(type="text", text=text)])

    monkeypatch.setattr(backend._client.beta.messages, "create", fake_create)
    backend.generate_beat("sys", "prompt")
    option = config.MODELS[model_id]
    assert sent["model"] == option.name
    assert sent["output_config"].get("effort") == option.effort
    assert ("fallbacks" in sent) == option.fallbacks


@pytest.mark.parametrize("error", [ConnectionError("refused"), httpx.ConnectTimeout("timed out")])
def test_unreachable_ollama_is_handled(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(ollama.Client, "list", fail)
    monkeypatch.setattr(ollama.Client, "chat", fail)
    assert installed_models("http://192.0.2.1:11434") is None
    with pytest.raises(BackendError, match="Can't reach Ollama"):
        OllamaBackend("llama3.1").generate_beat("system", "prompt")
