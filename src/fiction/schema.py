"""Data model shared by every layer: the beat contract, story state, and save files."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Act = Literal["setup", "rising", "climax", "resolution"]
ACT_ORDER: tuple[Act, ...] = ("setup", "rising", "climax", "resolution")

Length = Literal["short", "medium", "long"]
Mode = Literal["local", "claude", "compare"]


class StoryBeat(BaseModel):
    """The structured output both backends must return each turn.

    `extra="forbid"` makes the generated JSON Schema carry
    `additionalProperties: false`, which Claude's structured outputs require.
    """

    model_config = ConfigDict(extra="forbid")

    narration: str  # next chunk of prose shown to the player
    established_facts: list[str]  # running list of what's now true in the story
    act: Act
    concluded: bool  # True only on the turn that ends the story


class StoryConfig(BaseModel):
    """Choices made at story creation. Fixed for the life of the story."""

    setup_prompt: str = ""
    length: Length = "medium"
    mode: Mode = "local"
    ollama_model: str
    claude_model: str


class Turn(BaseModel):
    number: int
    player_input: str | None  # None for the opening beat
    beat: StoryBeat
    backend: str  # label of the backend whose beat became canonical


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StoryState(BaseModel):
    """Everything needed to continue (or redisplay) a story.

    `turns` keeps the full transcript for display and the finished record,
    but only `established_facts` plus the last couple of exchanges are ever
    sent back to a model (see prompts.build_turn_prompt).
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: StoryConfig
    created_at: datetime = Field(default_factory=_now)
    turns: list[Turn] = Field(default_factory=list)

    @property
    def established_facts(self) -> list[str]:
        return self.turns[-1].beat.established_facts if self.turns else []

    @property
    def act(self) -> Act:
        return self.turns[-1].beat.act if self.turns else "setup"

    @property
    def concluded(self) -> bool:
        return bool(self.turns) and self.turns[-1].beat.concluded

    @property
    def next_turn_number(self) -> int:
        return len(self.turns) + 1

    @property
    def title(self) -> str:
        setup = self.config.setup_prompt.strip()
        if not setup:
            return "An invented story"
        first_line = setup.splitlines()[0]
        return first_line if len(first_line) <= 60 else first_line[:57].rstrip() + "…"


SaveStatus = Literal["in_progress", "concluded"]


class SaveFile(BaseModel):
    """On-disk save. `status` decides whether loading resumes play or shows a read-only record."""

    version: int = 1
    name: str
    status: SaveStatus
    saved_at: datetime = Field(default_factory=_now)
    story: StoryState
