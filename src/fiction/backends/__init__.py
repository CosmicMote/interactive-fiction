from __future__ import annotations

from fiction.backends.base import Backend, BackendError
from fiction.backends.claude_backend import ClaudeBackend
from fiction.backends.ollama_backend import OllamaBackend, installed_models
from fiction.config import MODELS, OLLAMA_HOST, OLLAMA_HOST_DISPLAY
from fiction.schema import StoryConfig

__all__ = [
    "Backend",
    "BackendError",
    "ClaudeBackend",
    "OllamaBackend",
    "installed_models",
    "local_model_status",
    "make_backend",
    "make_backends",
]


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


def local_model_status(installed: set[str] | None, host: str = OLLAMA_HOST_DISPLAY) -> dict[str, str | None]:
    """For each local catalog model: None if usable, else why not (shown in the UI).

    `installed` is the set from installed_models(), or None when Ollama is unreachable.
    """
    status: dict[str, str | None] = {}
    for model_id, option in MODELS.items():
        if option.provider != "ollama":
            continue
        if installed is None:
            status[model_id] = f"can't reach Ollama at {host}"
        elif option.name not in installed:
            status[model_id] = f"not pulled - run: ollama pull {option.name}"
        else:
            status[model_id] = None
    return status
