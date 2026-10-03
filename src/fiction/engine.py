"""The turn loop: state + player input -> candidate beat(s) -> canonical next state.

Nothing here knows about the web UI, so any front end can drive it.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from fiction.backends import Backend, BackendError
from fiction.config import TARGET_TURNS
from fiction.prompts import SYSTEM_PROMPT, build_turn_prompt
from fiction.schema import ACT_ORDER, StoryBeat, StoryState, Turn


class StoryConcludedError(Exception):
    pass


@dataclass
class Candidate:
    """One backend's attempt at the next beat. Exactly one of beat/error is set."""

    backend: str
    beat: StoryBeat | None = None
    error: str | None = None


def target_turns(state: StoryState) -> int:
    return TARGET_TURNS[state.config.length]


def propose(state: StoryState, player_input: str | None, backends: list[Backend]) -> list[Candidate]:
    """Generate the next beat from each backend, in parallel. Doesn't modify state."""
    if state.concluded:
        raise StoryConcludedError("This story has concluded.")
    prompt = build_turn_prompt(state, player_input, target_turns(state))

    def run(backend: Backend) -> Candidate:
        try:
            return Candidate(backend.label, beat=backend.generate_beat(SYSTEM_PROMPT, prompt))
        except BackendError as e:
            return Candidate(backend.label, error=str(e))

    if len(backends) == 1:
        return [run(backends[0])]
    with ThreadPoolExecutor(max_workers=len(backends)) as pool:
        return list(pool.map(run, backends))


def normalize_beat(beat: StoryBeat, state: StoryState) -> StoryBeat:
    """Enforce pacing invariants the model may not respect.

    The story concludes exactly on the target turn, and acts never move backward.
    """
    turn = state.next_turn_number
    final = turn >= target_turns(state)
    act = beat.act
    if ACT_ORDER.index(act) < ACT_ORDER.index(state.act):
        act = state.act
    if final:
        act = "resolution"
    elif act == "resolution":
        act = "climax"
    return beat.model_copy(update={"act": act, "concluded": final})


def commit(state: StoryState, player_input: str | None, candidate: Candidate) -> StoryState:
    """Make a candidate canonical. Only its facts carry forward; other candidates are discarded."""
    if state.concluded:
        raise StoryConcludedError("This story has concluded.")
    if candidate.beat is None:
        raise ValueError("Can't commit a candidate that failed.")
    turn = Turn(
        number=state.next_turn_number,
        player_input=player_input,
        beat=normalize_beat(candidate.beat, state),
        backend=candidate.backend,
    )
    return state.model_copy(update={"turns": [*state.turns, turn]})


