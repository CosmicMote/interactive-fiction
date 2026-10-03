# Interactive Fiction Generator - Spec for Claude Code

Oct 3, 2026 - prepared by @Jeff Fowler

## Overview

A locally-run, web-based app where the user and the model co-write a story one turn at a time through free-form text. It's deliberately not a game - no inventory, no win condition, no choice menus. Each turn the app generates the next beat as structured data (narration plus a short list of established facts), and that structured output becomes the input to the next turn. That loop is the whole engine; everything else in this spec is detail on top of it.

## User flow

1. **Start a story.** The player optionally gives a short setup prompt (genre, setting, tone) that nudges the kind of story generated, without itself becoming part of `established_facts`. Left blank, the app invents a setting on its own.
2. **Choose a length.** Short / medium / long, which sets a target turn count and paces the story toward a resolution rather than an arbitrary stop.
3. **Choose a model mode.** A single backend (local via Ollama, or the Claude API) by default, or Compare mode, which runs both per turn (see Compare mode below). Single-model play is the primary use case, so Compare mode should default off.
4. **Play.** The player reacts to the current scene in free text. The app generates the next beat and shows it. Repeat.
5. **Ending.** On the turn that reaches the length target, the app resolves the story rather than just stopping.
6. **Save.** The player can save at any point; loading a save resumes the loop from that state. See Save and load for how save semantics work once a story concludes.

## Data model

Both backends return the same structure, so the schema is the one piece of the system that doesn't change based on model choice.

```python
from pydantic import BaseModel
from typing import Literal

class StoryBeat(BaseModel):
    narration: str                   # next chunk of prose shown to the player
    established_facts: list[str]     # running list of what's now true in the story
    act: Literal["setup", "rising", "climax", "resolution"]
    concluded: bool                  # True only on the turn that ends the story
```

`established_facts` is deliberately a flat list of short statements, not a nested game-state object - it's the compact memory the model works from each turn, not a simulation to maintain.

## Model backend architecture

&#91;embedded content: backend architecture - 2 implementations, 1 shared schema\]

Calling either backend passes the same `StoryBeat.model_json_schema()` to the model: Ollama via its `format` parameter, Claude via `output_config.format`. The loop and the schema don't change based on which one is active - only which function `generate_beat()` calls into.

## Compare mode

An optional toggle set at story creation, off by default. When on, each turn calls both backends with the same state and the same player input, and shows both resulting beats before continuing.

The player picks which beat becomes canonical. **Only the picked beat's `established_facts` get carried forward** - the rejected beat is discarded entirely, never merged. Blending facts from both would let details from a path the story never actually took leak into later turns, which breaks internal consistency even though nothing visibly "wrong" happened on screen.

For the initial version, Compare mode is always local vs. Claude, not a free choice between any two backends. Letting the player pick which Claude model to compare against is a reasonable later addition - it's a parameter on `ClaudeBackend`, not a new backend, so it shouldn't need to change the architecture above.

## Pacing and length control

The length the player picks at story start sets a target turn count, not a hard cutoff. Each turn, the backend is told roughly how far along it is relative to that target, and the `act` field should move forward accordingly - a short story should be nudging toward `climax` by turn 5 or 6.

On the turn that reaches the target, the prompt should explicitly instruct the model to resolve the story rather than continue it, and the returned beat should set `concluded: true`. This produces an ending on a beat, rather than the story just stopping mid-scene.

## Context management

Don't feed the full turn-by-turn transcript back into the model every turn. `established_facts` is the compact memory meant to carry state forward - feed that, plus maybe the last exchange or two for voice continuity, instead of the whole history.

This matters more for the local backend than the Claude one: a quantized model's usable context is smaller than its advertised window, and a growing raw transcript will eventually crowd out the instructions themselves or slow generation down. It's a near-free win here, since `established_facts` already exists for a different reason.

## Save and load

A save is a serialization of the current state - `established_facts`, `act` progress, and whatever's needed to reconstruct the scene - to disk. Loading a save hands that state back to the loop as its starting point, so the mechanism is the same whether the story is mid-play or finished.

Saves are resumable while a story hasn't concluded. Once a story concludes, the player additionally has the option to save a finished, read-only record of the whole thing - so a save file needs to track whether the story is still in progress, since that determines whether loading it resumes play or just displays the finished narration.

## Tech stack

Python 3.13, managed with [uv](https://docs.astral.sh/uv/). Pydantic v2 for `StoryBeat` and the save format.

**Web UI: FastAPI + Jinja2 templates + [HTMX](https://htmx.org/), plain CSS with color tokens.** Gradio was the original suggestion, but planned post-V1 features - narration streamed word by word, and a color scheme that shifts with the story's tone - are awkward in Gradio (its themes are fixed at launch, and streaming a field out of partial JSON needs control of the transport). With FastAPI + HTMX, word-by-word becomes an SSE route, and tone theming becomes swapping CSS custom properties keyed off `body[data-tone]`. V1 has no build step and no Node toolchain. The engine, backends, and storage never import web code, so the UI layer can be replaced (e.g. with a React/Svelte front end) without touching the turn loop.

Backends: the `ollama` Python package for the local model (`format=` with the Pydantic schema, `think=False`), and the `anthropic` Python SDK for Claude (structured outputs via `output_config.format`). Both use the same JSON Schema from `StoryBeat.model_json_schema()`. The default Claude model is **Claude Sonnet 5.5** (`claude-sonnet-5-5`), at low effort; the API key comes from the `ANTHROPIC_API_KEY` environment variable.

The Ollama models offered in the UI are a fixed short list sized for the Mac Mini's 48GB of unified memory: `qwen3.6:35b-a3b` (default), `gemma4:26b`, and `llama3.1:8b`. The `gemma4:26b-mlx` build was excluded because it ignores `format=` and returns plain prose.

## Decisions

- **Save semantics:** resumable while in progress; a finished read-only record can also be saved once concluded.
- **Local model choice:** a fixed short list, sized for the Mac Mini's 48GB of memory - not everything pulled locally.
- **Compare mode scope:** always local vs. Claude for the initial version; selecting which Claude model to compare against is a reasonable later addition.
- **UI stack:** FastAPI + Jinja2 + HTMX instead of Gradio, to leave room for streamed narration and tone-based theming.
- **Default Claude model:** Claude Sonnet 5.5, authenticated via `ANTHROPIC_API_KEY`.
- **Setup prompt handling:** shapes tone, genre, and setting rather than becoming part of `established_facts`.

These are now settled; nothing further to confirm before building.
