from __future__ import annotations

from fiction.backends.base import Backend, BackendError
from fiction.backends.claude_backend import ClaudeBackend
from fiction.backends.ollama_backend import OllamaBackend
from fiction.config import MODELS, OLLAMA_HOST
from fiction.schema import StoryConfig

__all__ = ["Backend", "BackendError", "ClaudeBackend", "OllamaBackend", "make_backend", "make_backends"]


def make_backend(model_id: str) -> Backend:
    option = MODELS.get(model_id)
    if option is None:
        raise BackendError(f"Unknown model: {model_id}")
    if option.provider == "ollama":
        return OllamaBackend(option.name, label=option.label, host=OLLAMA_HOST)
    return ClaudeBackend(option.name, label=option.label, effort=option.effort, fallbacks=option.fallbacks)


def make_backends(config: StoryConfig) -> list[Backend]:
    """One backend per model slot. Comparing a model to itself gets two independent instances."""
    return [make_backend(m) for m in config.models]
