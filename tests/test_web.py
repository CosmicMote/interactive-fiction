from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from conftest import FakeBackend
from fiction.backends import BackendError
from fiction.web.app import create_app


@pytest.fixture
def client(tmp_path):
    def factory(config):
        if config.mode == "compare":
            return [FakeBackend("local"), FakeBackend("claude")]
        return [FakeBackend("solo")]

    return TestClient(create_app(saves_dir=tmp_path, backend_factory=factory))


def start(client, **form):
    data = {"setup_prompt": "", "length": "short", "mode": "local", "ollama_model": "llama3.1:latest"} | form
    r = client.post("/stories", data=data, follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"]


def test_single_mode_play_to_end_and_save(client):
    url = start(client)
    assert "Writing the opening" in client.get(url).text
    r = client.post(f"{url}/turn")  # opening
    assert "solo narration 1." in r.text
    for i in range(7):
        r = client.post(f"{url}/turn", data={"player_input": f"action {i}"})
    assert "The End" in r.text
    assert 'name="player_input"' not in r.text

    r = client.post(f"{url}/save", data={"name": "done"})
    assert "Finished record saved" in r.text
    filename = re.search(r"done-[\w-]+\.json", r.text).group(0)

    r = client.post(f"/saves/{filename}/open", follow_redirects=False)
    assert r.headers["location"] == f"/saves/{filename}"
    page = client.get(f"/saves/{filename}").text
    assert "read-only" in page and 'name="player_input"' not in page


def test_empty_input_after_opening_is_rejected(client):
    url = start(client)
    client.post(f"{url}/turn")
    r = client.post(f"{url}/turn", data={"player_input": "   "})
    assert "Write something" in r.text


def test_compare_mode_pick(client):
    url = start(client, mode="compare")
    r = client.post(f"{url}/turn")
    assert "Use this beat" in r.text
    assert "local narration 1." in r.text and "claude narration 1." in r.text
    r = client.post(f"{url}/choose", data={"index": 1})
    assert "claude fact 1" in r.text
    assert "local fact 1" not in r.text


def test_resume_in_progress_save(client):
    url = start(client)
    client.post(f"{url}/turn")
    r = client.post(f"{url}/save", data={"name": "midway"})
    filename = re.search(r"midway-[\w-]+\.json", r.text).group(0)
    r = client.post(f"/saves/{filename}/open", follow_redirects=False)
    assert r.headers["location"].startswith("/s/")
    page = client.get(r.headers["location"]).text
    assert 'name="player_input"' in page and "solo narration 1." in page


def test_backend_setup_error_shows_on_form(tmp_path):
    def factory(config):
        raise BackendError("ANTHROPIC_API_KEY is not set, so the Claude backend is unavailable.")

    client = TestClient(create_app(saves_dir=tmp_path, backend_factory=factory))
    r = client.post("/stories", data={"length": "short", "mode": "claude", "ollama_model": "llama3.1:latest"})
    assert r.status_code == 400
    assert "ANTHROPIC_API_KEY is not set" in r.text
