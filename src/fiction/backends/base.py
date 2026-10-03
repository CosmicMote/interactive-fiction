from __future__ import annotations

from typing import Protocol

from fiction.schema import StoryBeat


class BackendError(Exception):
    """A turn couldn't be generated. The message is safe to show the player."""


class Backend(Protocol):
    label: str

    def generate_beat(self, system: str, prompt: str) -> StoryBeat: ...
