"""FastAPI + Jinja2 + HTMX front end. A thin layer over engine/storage."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from fiction import config, engine, storage
from fiction.backends import Backend, BackendError, make_backends
from fiction.schema import StoryConfig, StoryState

HERE = Path(__file__).parent


@dataclass
class Pending:
    """Compare-mode candidates awaiting the player's pick."""

    player_input: str | None
    candidates: list[engine.Candidate]


@dataclass
class Session:
    state: StoryState
    backends: list[Backend]
    pending: Pending | None = None
    error: str | None = None
    draft: str = ""


def paragraphs(text: str) -> Markup:
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return Markup("".join(f"<p>{escape(p)}</p>" for p in parts))


def create_app(saves_dir: Path | None = None, backend_factory=make_backends) -> FastAPI:
    saves_dir = saves_dir or config.SAVES_DIR
    app = FastAPI(title="Interactive Fiction")
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["paragraphs"] = paragraphs
    sessions: dict[str, Session] = {}

    def get_session(sid: str) -> Session:
        if sid not in sessions:
            raise HTTPException(404, "That story isn't open. Load it from a save.")
        return sessions[sid]

    def story_context(sid: str | None, session: Session | None, story: StoryState, readonly: bool) -> dict:
        return {
            "sid": sid,
            "story": story,
            "session": session,
            "readonly": readonly,
            "target": engine.target_turns(story),
            "compare": story.config.compare,
            "model_labels": [config.MODELS[m].label if m in config.MODELS else m for m in story.config.models],
        }

    def render_area(request: Request, sid: str, session: Session) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "_story_area.html", story_context(sid, session, session.state, readonly=False)
        )

    def render_index(request: Request, error: str | None = None, status_code: int = 200) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "saves": storage.list_saves(saves_dir),
                "local_models": [m for m in config.MODELS.values() if m.provider == "ollama"],
                "claude_models": [m for m in config.MODELS.values() if m.provider == "claude"],
                "claude_available": config.claude_available(),
                "default_a": config.DEFAULT_OLLAMA_MODEL,
                "default_b": config.DEFAULT_CLAUDE_MODEL,
                "targets": config.TARGET_TURNS,
                "error": error,
            },
            status_code=status_code,
        )

    def open_session(state: StoryState) -> str:
        backends = backend_factory(state.config)  # may raise BackendError
        sid = uuid.uuid4().hex
        sessions[sid] = Session(state=state, backends=backends)
        return sid

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render_index(request)

    @app.post("/stories")
    def create_story(
        request: Request,
        setup_prompt: Annotated[str, Form()] = "",
        length: Annotated[str, Form()] = "medium",
        mode: Annotated[str, Form()] = "single",
        model_a: Annotated[str, Form()] = config.DEFAULT_OLLAMA_MODEL,
        model_b: Annotated[str, Form()] = config.DEFAULT_CLAUDE_MODEL,
    ):
        if length not in config.TARGET_TURNS or mode not in ("single", "compare"):
            raise HTTPException(400, "Invalid story options.")
        models = [model_a, model_b] if mode == "compare" else [model_a]
        if any(m not in config.MODELS for m in models):
            raise HTTPException(400, "Unknown model.")
        story = StoryState(
            config=StoryConfig(setup_prompt=setup_prompt.strip(), length=length, models=models)
        )
        try:
            sid = open_session(story)
        except BackendError as e:
            return render_index(request, error=str(e), status_code=400)
        return RedirectResponse(f"/s/{sid}", status_code=303)

    @app.get("/s/{sid}", response_class=HTMLResponse)
    def story_page(request: Request, sid: str):
        session = get_session(sid)
        return templates.TemplateResponse(
            request, "story.html", story_context(sid, session, session.state, readonly=False)
        )

    @app.post("/s/{sid}/turn", response_class=HTMLResponse)
    def take_turn(request: Request, sid: str, player_input: Annotated[str, Form()] = ""):
        session = get_session(sid)
        session.error = None
        text: str | None = player_input.strip() or None
        if session.state.turns and text is None:
            session.error = "Write something for your character to do or say."
            return render_area(request, sid, session)
        if session.state.concluded:
            return render_area(request, sid, session)

        candidates = engine.propose(session.state, text, session.backends)
        if len(candidates) == 1:
            (candidate,) = candidates
            if candidate.beat is None:
                session.error = candidate.error
                session.draft = text or ""
            else:
                session.state = engine.commit(session.state, text, candidate)
                session.draft = ""
        else:
            session.pending = Pending(player_input=text, candidates=candidates)
            session.draft = text or ""
            if all(c.beat is None for c in candidates):
                session.error = "Neither backend produced a beat."
        return render_area(request, sid, session)

    @app.post("/s/{sid}/choose", response_class=HTMLResponse)
    def choose(request: Request, sid: str, index: Annotated[int, Form()]):
        session = get_session(sid)
        pending = session.pending
        if pending is None or not 0 <= index < len(pending.candidates):
            raise HTTPException(400, "Nothing to choose.")
        candidate = pending.candidates[index]
        if candidate.beat is None:
            raise HTTPException(400, "That candidate failed.")
        # Only the picked beat carries forward; the other is discarded entirely.
        session.state = engine.commit(session.state, pending.player_input, candidate)
        session.pending = None
        session.error = None
        session.draft = ""
        return render_area(request, sid, session)

    @app.post("/s/{sid}/discard", response_class=HTMLResponse)
    def discard(request: Request, sid: str):
        """Throw away compare candidates and go back to the input box."""
        session = get_session(sid)
        session.pending = None
        session.error = None
        return render_area(request, sid, session)

    @app.post("/s/{sid}/save", response_class=HTMLResponse)
    def save_story(sid: str, name: Annotated[str, Form()] = ""):
        session = get_session(sid)
        path = storage.save(session.state, saves_dir, name or None)
        kind = "Finished record saved" if session.state.concluded else "Saved"
        return HTMLResponse(f'<span class="ok">{kind}: {escape(path.name)}</span>')

    @app.post("/saves/{filename}/open")
    def open_save(request: Request, filename: str):
        try:
            record = storage.load(saves_dir, filename)
        except storage.SaveNotFoundError:
            raise HTTPException(404, "Save not found.")
        if record.status == "concluded":
            return RedirectResponse(f"/saves/{filename}", status_code=303)
        try:
            sid = open_session(record.story)
        except BackendError as e:
            return render_index(request, error=str(e), status_code=400)
        return RedirectResponse(f"/s/{sid}", status_code=303)

    @app.get("/saves/{filename}", response_class=HTMLResponse)
    def view_save(request: Request, filename: str):
        try:
            record = storage.load(saves_dir, filename)
        except storage.SaveNotFoundError:
            raise HTTPException(404, "Save not found.")
        context = story_context(None, None, record.story, readonly=True)
        context["save"] = record
        return templates.TemplateResponse(request, "story.html", context)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("fiction.web.app:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
