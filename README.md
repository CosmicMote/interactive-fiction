# Interactive Fiction

A locally-run web app where you and a model co-write a story one turn at a time. Each turn the model returns a structured `StoryBeat` (narration, established facts, act, concluded), and that becomes the input to the next turn. See [the spec](<Interactive Fiction Generator - Spec for Claude Code.md>) for the design.

## Run it

Requires [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com/) (for local models).

```bash
uv run fiction
```

Then open http://127.0.0.1:8000.

- **Local models:** pull the ones you want to use with `ollama pull qwen3.6:35b-a3b`, `ollama pull gemma4:26b`, or `ollama pull llama3.1`.
- **Claude models:** set `ANTHROPIC_API_KEY` in the environment before starting. Sonnet 5.5 is the default; Opus 5.5, Haiku 4.5 and Fable 5.1 are also offered.
- **Compare mode:** pick any two models, including the same one twice.
- **Story notes:** facts, progress and Save are in a drawer at the right edge. Hover to peek, or click the Notes tab to pin it open.
- **Port:** 8000 by default; set `PORT` to change it.
- **Saves:** written to `./saves` as JSON. Override the location with `FICTION_SAVES_DIR`. Delete them from the home page (with confirmation).
- **Theme:** Light / System / Dark switcher in the header, remembered per browser.
- **Ollama host:** override with `OLLAMA_HOST`.

## Develop

```bash
uv run pytest
```

Layout (`src/fiction/`):

| Module | Role |
|---|---|
| `schema.py` | `StoryBeat`, `StoryState`, `SaveFile` |
| `prompts.py` | System prompt, per-turn prompt (facts + last 2 exchanges + pacing), act targets |
| `engine.py` | `propose()` candidates from one or two backends, `commit()` the chosen one, enforce pacing |
| `backends/` | `OllamaBackend`, `ClaudeBackend`, sharing one `generate_beat(system, prompt)` interface |
| `storage.py` | Save, load, list |
| `web/` | FastAPI + Jinja2 + HTMX UI. The only layer that knows about HTTP |

The model catalog (with per-model Claude settings), length targets, and defaults are in `config.py`.
