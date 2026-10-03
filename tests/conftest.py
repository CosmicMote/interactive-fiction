from __future__ import annotations

import pytest

from fiction.backends import BackendError
from fiction.schema import StoryBeat, StoryConfig, StoryState


class FakeBackend:
    """Deterministic backend: each beat adds one fact tagged with the backend's name."""

    def __init__(self, name: str = "fake", act: str = "rising", concluded: bool = False, fail: bool = False):
        self.label = name
        self.act = act
        self.concluded = concluded
        self.fail = fail
        self.prompts: list[str] = []

    def generate_beat(self, system: str, prompt: str) -> StoryBeat:
        self.prompts.append(prompt)
        if self.fail:
            raise BackendError(f"{self.label} is down")
        n = len(self.prompts)
        return StoryBeat(
            narration=f"{self.label} narration {n}.\n\nSecond paragraph.",
            established_facts=[f"{self.label} fact {i}" for i in range(1, n + 1)],
            act=self.act,
            concluded=self.concluded,
        )


@pytest.fixture
def make_state():
    def _make(length: str = "short", mode: str = "local", setup: str = "") -> StoryState:
        return StoryState(
            config=StoryConfig(
                setup_prompt=setup, length=length, mode=mode,
                ollama_model="llama3.1:latest", claude_model="claude-sonnet-5-5",
            )
        )

    return _make
