"""App-wide settings: model lists, length targets, paths."""

from __future__ import annotations

import os
from pathlib import Path

from fiction.schema import Length

# Fixed short list sized for a 48GB Mac mini, rather than everything pulled locally.
OLLAMA_MODELS: dict[str, str] = {
    "qwen3.6:35b-a3b": "Qwen 3.6 35B-A3B (MoE, fast for its size)",
    "gemma4:26b": "Gemma 4 26B",  # not the -mlx build: it ignores format= and returns prose
    "llama3.1:latest": "Llama 3.1 8B (small, fastest)",
}
DEFAULT_OLLAMA_MODEL = "qwen3.6:35b-a3b"

# Selecting a different Claude model is a later addition; it's just this parameter.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"

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
OLLAMA_HOST = os.environ.get("OLLAMA_HOST")  # None -> ollama's default (localhost:11434)
