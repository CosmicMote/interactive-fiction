from __future__ import annotations

import pytest

from conftest import FakeBackend
from fiction import engine
from fiction.prompts import build_turn_prompt, target_act


def play(state, backend, turns):
    for i in range(turns):
        (candidate,) = engine.propose(state, None if not state.turns else f"input {i}", [backend])
        state = engine.commit(state, None if not state.turns else f"input {i}", candidate)
    return state


def test_short_story_reaches_climax_by_turn_five_and_resolves_on_target():
    assert [target_act(t, 8) for t in range(1, 9)] == [
        "setup", "setup", "rising", "rising", "climax", "climax", "climax", "resolution",
    ]


def test_story_concludes_exactly_on_target_turn_even_if_model_disagrees(make_state):
    state = make_state("short")
    backend = FakeBackend(act="setup", concluded=True)  # model claims it's done every turn
    state = play(state, backend, 7)
    assert not state.concluded
    assert state.act != "resolution"

    state = play(state, FakeBackend(act="climax", concluded=False), 1)
    assert state.concluded
    assert state.act == "resolution"
    assert len(state.turns) == 8


def test_acts_never_move_backward(make_state):
    state = play(make_state(), FakeBackend(act="climax"), 1)
    state = play(state, FakeBackend(act="setup"), 1)
    assert state.act == "climax"


def test_cannot_continue_after_conclusion(make_state):
    state = play(make_state("short"), FakeBackend(), 8)
    with pytest.raises(engine.StoryConcludedError):
        engine.propose(state, "more", [FakeBackend()])


def test_compare_only_picked_facts_carry_forward(make_state):
    state = make_state(mode="compare")
    local, claude = FakeBackend("local"), FakeBackend("claude")
    candidates = engine.propose(state, None, [local, claude])
    assert [c.backend for c in candidates] == ["local", "claude"]

    state = engine.commit(state, None, candidates[1])
    assert state.established_facts == ["claude fact 1"]

    candidates = engine.propose(state, "look around", [local, claude])
    next_prompt = local.prompts[-1]
    assert "claude fact 1" in next_prompt
    assert "local fact" not in next_prompt  # rejected beat never leaks back in
    state = engine.commit(state, "look around", candidates[0])
    assert all(f.startswith("local") for f in state.established_facts)


def test_failed_backend_becomes_error_candidate(make_state):
    candidates = engine.propose(make_state(), None, [FakeBackend("ok"), FakeBackend("bad", fail=True)])
    assert candidates[0].beat is not None
    assert candidates[1].beat is None and "down" in candidates[1].error
    with pytest.raises(ValueError):
        engine.commit(make_state(), None, candidates[1])


def test_prompt_uses_facts_and_recent_exchanges_not_full_transcript(make_state):
    state = play(make_state("long", setup="Noir in a drowned city"), FakeBackend(), 6)
    prompt = build_turn_prompt(state, "I light a cigarette", 24)
    assert "Noir in a drowned city" in prompt
    assert "fake fact 6" in prompt
    assert "fake narration 6." in prompt and "fake narration 5." in prompt
    assert "fake narration 4." not in prompt
    assert "turn 7 of" in prompt
    assert "I light a cigarette" in prompt


def test_final_turn_prompt_demands_resolution(make_state):
    state = play(make_state("short"), FakeBackend(), 7)
    prompt = build_turn_prompt(state, "finish it", 8)
    assert "FINAL turn" in prompt


def test_blank_setup_asks_model_to_invent(make_state):
    prompt = build_turn_prompt(make_state(), None, 8)
    assert "Invent an original setting" in prompt
    assert "opening beat" in prompt
