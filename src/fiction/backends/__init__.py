from __future__ import annotations

from fiction.backends.base import Backend, BackendError
from fiction.backends.claude_backend import ClaudeBackend
from fiction.backends.ollama_backend import OllamaBackend
from fiction.config import OLLAMA_HOST
from fiction.schema import StoryConfig

__all__ = ["Backend", "BackendError", "ClaudeBackend", "OllamaBackend", "make_backends"]


def make_backends(config: StoryConfig) -> list[Backend]:
    """Backends for a story's mode. Compare mode is always local vs. Claude, in that order."""
    if config.mode == "local":
        return [OllamaBackend(config.ollama_model, host=OLLAMA_HOST)]
    if config.mode == "claude":
        return [ClaudeBackend(config.claude_model)]
    return [OllamaBackend(config.ollama_model, host=OLLAMA_HOST), ClaudeBackend(config.claude_model)]
