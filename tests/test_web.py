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
        if config.compare:
            a, b = config.models
            if a == b:
                return [FakeBackend("same"), FakeBackend("same")]
            return [FakeBackend("local"), FakeBackend("claude")]
        return [FakeBackend("solo")]

    return TestClient(create_app(saves_dir=tmp_path, backend_factory=factory))


def start(client, **form):
    data = {"setup_prompt": "", "length": "short", "mode": "single", "model_a": "ollama:llama3.1:latest"} | form
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
    url = start(client, mode="compare", model_b="claude:claude-opus-5-5")
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
    r = client.post("/stories", data={"length": "short", "mode": "single", "model_a": "claude:claude-sonnet-5-5"})
    assert r.status_code == 400
    assert "ANTHROPIC_API_KEY is not set" in r.text


def test_compare_model_against_itself(client):
    url = start(client, mode="compare", model_a="ollama:gemma4:26b", model_b="ollama:gemma4:26b")
    r = client.post(f"{url}/turn")
    assert r.text.count("Use this beat") == 2
    assert "<strong>A</strong> · same" in r.text and "<strong>B</strong> · same" in r.text
    assert "Gemma 4 26B vs. Gemma 4 26B" in r.text


def test_unknown_model_rejected(client):
    r = client.post("/stories", data={"length": "short", "mode": "single", "model_a": "ollama:not-a-model"})
    assert r.status_code == 400


def test_drawer_holds_facts_and_save(client):
    url = start(client)
    r = client.post(f"{url}/turn")
    drawer = r.text[r.text.index('class="drawer"'):]
    assert "solo fact 1" in drawer and 'hx-post="' + url + '/save"' in drawer


def test_delete_save(client, tmp_path):
    url = start(client)
    client.post(f"{url}/turn")
    r = client.post(f"{url}/save", data={"name": "doomed"})
    filename = re.search(r"doomed-[\w-]+\.json", r.text).group(0)
    assert "doomed" in client.get("/").text

    r = client.post(f"/saves/{filename}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert not (tmp_path / filename).exists()
    assert "doomed" not in client.get("/").text
    assert client.post(f"/saves/{filename}/delete").status_code == 404


def test_index_form_has_one_model_picker_until_compare(client):
    html = client.get("/").text
    outside_template = html.split("<template")[0] + html.split("</template>")[1]
    assert 'name="model_a"' in outside_template and 'name="model_b"' not in outside_template
    assert "Model 1" in html and "Model 2" in html
    assert "Model A" not in html
    assert 'href="/static/style.css?v=' in html
    assert 'data-theme-choice="dark"' in html


def make_client(tmp_path, installed):
    return TestClient(create_app(
        saves_dir=tmp_path,
        backend_factory=lambda config: [FakeBackend("solo")],
        list_installed=lambda: installed,
    ))


def test_unpulled_local_models_are_disabled_with_pull_hint(tmp_path):
    client = make_client(tmp_path, {"llama3.1:latest"})
    html = client.get("/").text
    assert re.search(r'value="ollama:gemma4:26b"\s+disabled', html)
    assert "not pulled - run: ollama pull gemma4:26b" in html
    assert not re.search(r'value="ollama:llama3.1:latest"[^>]*disabled', html)
    assert "haven't been pulled yet" in html


def test_ollama_down_disables_all_local_models(tmp_path):
    html = make_client(tmp_path, None).get("/").text
    assert html.count("can&#39;t reach Ollama at localhost:11434") == 6  # 3 models x (Model 1 + Model 2 template)
    assert "Can't reach Ollama at <code>localhost:11434</code>" in html


def test_cannot_start_story_with_unpulled_model(tmp_path):
    client = make_client(tmp_path, {"llama3.1:latest"})
    r = client.post("/stories", data={"length": "short", "mode": "single", "model_a": "ollama:gemma4:26b"})
    assert r.status_code == 400
    assert "ollama pull gemma4:26b" in r.text


def test_served_under_base_path(tmp_path):
    app = create_app(saves_dir=tmp_path, backend_factory=lambda c: [FakeBackend("solo")], base_path="/fiction/")
    client = TestClient(app)
    assert client.get("/", follow_redirects=False).headers["location"] == "/fiction/"
    page = client.get("/fiction/").text
    assert 'action="/fiction/stories"' in page and 'href="/fiction/static/style.css' in page

    r = client.post("/fiction/stories", data={"length": "short", "mode": "single"}, follow_redirects=False)
    url = r.headers["location"]
    assert url.startswith("/fiction/s/")
    r = client.post(f"{url}/turn")
    assert f'hx-post="{url}/save"' in r.text
    filename = re.search(r"[\w-]+\.json", client.post(f"{url}/save", data={"name": "x"}).text).group(0)
    assert client.post(f"/fiction/saves/{filename}/delete", follow_redirects=False).headers["location"] == "/fiction/"
    stylesheet = re.search(r'href="(/fiction/static/style\.css[^"]*)"', page).group(1)
    assert client.get(stylesheet).status_code == 200
