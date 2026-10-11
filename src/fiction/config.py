"""App-wide settings: model catalog, length targets, paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fiction.schema import Length


@dataclass(frozen=True)
class ModelOption:
    id: str  # "<provider>:<model name>", the value stored in StoryConfig.models
    provider: Literal["ollama", "claude"]
    name: str  # what the provider's API calls it
    label: str  # shown in the UI and transcript
    note: str = ""
    # Claude only. Haiku 4.5 rejects `effort`; server-side refusal fallbacks
    # exist only for the newer models.
    effort: str | None = None
    fallbacks: bool = False


def _ollama(name: str, label: str, note: str = "") -> ModelOption:
    return ModelOption(f"ollama:{name}", "ollama", name, label, note)


def _claude(name: str, label: str, note: str = "", effort: str | None = "low", fallbacks: bool = True) -> ModelOption:
    return ModelOption(f"claude:{name}", "claude", name, label, note, effort, fallbacks)


# Local list is fixed and sized for a 48GB Mac mini, rather than everything pulled locally.
MODELS: dict[str, ModelOption] = {
    m.id: m
    for m in [
        _ollama("qwen3.6:35b-a3b", "Qwen 3.6 35B-A3B", "MoE, fast for its size"),
        # Not the -mlx build: it ignores format= and returns prose.
        _ollama("gemma4:26b", "Gemma 4 26B"),
        _ollama("llama3.1:latest", "Llama 3.1 8B", "small, fastest"),
        _claude("claude-sonnet-5-5", "Claude Sonnet 5.5"),
        _claude("claude-opus-5-5", "Claude Opus 5.5", "stronger, ~2x Sonnet's price"),
        _claude("claude-haiku-4-5", "Claude Haiku 4.5", "fastest, cheapest", effort=None, fallbacks=False),
        _claude("claude-fable-5-1", "Claude Fable 5.1", "most capable, slow, ~5x Sonnet's price"),
    ]
}

DEFAULT_OLLAMA_MODEL = "ollama:qwen3.6:35b-a3b"
DEFAULT_CLAUDE_MODEL = "claude:claude-sonnet-5-5"

# Target turn counts, opening beat included. A target, not a hard cutoff:
# the prompt paces toward it and the final turn resolves the story.
TARGET_TURNS: dict[Length, int] = {
    "short": 8,
    "medium": 16,
    "long": 24,
}

# How many recent exchanges to send for voice continuity, alongside established_facts.
RECENT_EXCHANGES = 2

SAVES_DIR = Path(os.environ.get("FICTION_SAVES_DIR", Path.cwd() / "saves"))
# Point at another machine (e.g. a Mac mini with a GPU) with OLLAMA_HOST=http://<host>:11434.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST") or None  # None -> ollama's default (localhost:11434)
OLLAMA_HOST_DISPLAY = OLLAMA_HOST or "localhost:11434"
# Serve under a path prefix (e.g. BASE_PATH=/interactive-fiction) behind a reverse proxy that
# forwards the full path. Empty serves at the root.
def normalize_base_path(value: str) -> str:
    """'/a/', 'a' and '/a' all become '/a'; '' and '/' become ''."""
    value = value.strip("/")
    return f"/{value}" if value else ""


BASE_PATH = normalize_base_path(os.environ.get("BASE_PATH", ""))


def claude_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
