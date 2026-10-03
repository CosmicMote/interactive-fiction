"""Save and load. A save is a serialized StoryState plus whether it's still resumable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from fiction.schema import SaveFile, StoryState


class SaveNotFoundError(Exception):
    pass


@dataclass
class SaveSummary:
    filename: str
    name: str
    status: str
    saved_at: datetime
    turns: int
    title: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "story"


def save(state: StoryState, saves_dir: Path, name: str | None = None) -> Path:
    """Write a save. A concluded story's save is the finished, read-only record."""
    saves_dir.mkdir(parents=True, exist_ok=True)
    record = SaveFile(
        name=(name or "").strip() or state.title,
        status="concluded" if state.concluded else "in_progress",
        story=state,
    )
    stamp = record.saved_at.strftime("%Y%m%d-%H%M%S")
    path = saves_dir / f"{_slug(record.name)}-{stamp}-{state.id}.json"
    path.write_text(record.model_dump_json(indent=2))
    return path


def _resolve(saves_dir: Path, filename: str) -> Path:
    path = (saves_dir / filename).resolve()
    if path.parent != saves_dir.resolve() or path.suffix != ".json" or not path.is_file():
        raise SaveNotFoundError(filename)
    return path


def load(saves_dir: Path, filename: str) -> SaveFile:
    path = _resolve(saves_dir, filename)
    try:
        return SaveFile.model_validate_json(path.read_text())
    except ValidationError as e:
        raise SaveNotFoundError(f"{filename} isn't a valid save") from e


def list_saves(saves_dir: Path) -> list[SaveSummary]:
    if not saves_dir.is_dir():
        return []
    summaries = []
    for path in saves_dir.glob("*.json"):
        try:
            record = SaveFile.model_validate_json(path.read_text())
        except (ValidationError, OSError):
            continue
        summaries.append(
            SaveSummary(
                filename=path.name,
                name=record.name,
                status=record.status,
                saved_at=record.saved_at,
                turns=len(record.story.turns),
                title=record.story.title,
            )
        )
    return sorted(summaries, key=lambda s: s.saved_at, reverse=True)
