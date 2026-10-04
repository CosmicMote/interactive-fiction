from __future__ import annotations

import pytest

from conftest import FakeBackend
from fiction import engine, storage


def advance(state, n):
    backend = FakeBackend()
    for _ in range(n):
        text = "go on" if state.turns else None
        (c,) = engine.propose(state, text, [backend])
        state = engine.commit(state, text, c)
    return state


def test_round_trip_in_progress(tmp_path, make_state):
    state = advance(make_state("short", setup="Space opera"), 3)
    path = storage.save(state, tmp_path, "My run")
    record = storage.load(tmp_path, path.name)
    assert record.status == "in_progress"
    assert record.name == "My run"
    assert record.story == state
    # Loading hands the same state back to the loop.
    resumed = advance(record.story, 1)
    assert len(resumed.turns) == 4


def test_concluded_save_is_finished_record(tmp_path, make_state):
    state = advance(make_state("short"), 8)
    path = storage.save(state, tmp_path)
    assert storage.load(tmp_path, path.name).status == "concluded"


def test_list_saves_newest_first_and_skips_junk(tmp_path, make_state):
    storage.save(advance(make_state(), 1), tmp_path, "first")
    storage.save(advance(make_state(), 2), tmp_path, "second")
    (tmp_path / "junk.json").write_text("{not json")
    names = [s.name for s in storage.list_saves(tmp_path)]
    assert names == ["second", "first"]


def test_load_rejects_path_traversal(tmp_path):
    with pytest.raises(storage.SaveNotFoundError):
        storage.load(tmp_path, "../etc/passwd.json")


def test_delete_rejects_path_traversal(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    saves = tmp_path / "saves"
    saves.mkdir()
    with pytest.raises(storage.SaveNotFoundError):
        storage.delete(saves, "../outside.json")
    assert outside.exists()
