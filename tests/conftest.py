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
    def _make(length: str = "short", compare: bool = False, setup: str = "") -> StoryState:
        models = ["ollama:llama3.1:latest", "claude:claude-sonnet-5-5"] if compare else ["ollama:llama3.1:latest"]
        return StoryState(config=StoryConfig(setup_prompt=setup, length=length, models=models))

    return _make
