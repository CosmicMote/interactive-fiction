from __future__ import annotations

import httpx
import ollama
from pydantic import ValidationError

from fiction.backends.base import BackendError
from fiction.schema import StoryBeat


class OllamaBackend:
    def __init__(self, model: str, label: str | None = None, host: str | None = None, num_ctx: int = 8192):
        self.model = model
        self.label = label or model
        self._host = host or "localhost:11434"
        self._client = ollama.Client(host=host)
        self._num_ctx = num_ctx

    def generate_beat(self, system: str, prompt: str) -> StoryBeat:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                format=StoryBeat.model_json_schema(),
                # Keep reasoning out of the JSON for thinking-capable models.
                think=False,
                options={"num_ctx": self._num_ctx, "temperature": 0.8},
            )
        except ollama.ResponseError as e:
            raise BackendError(f"Ollama error from {self.model}: {e.error}") from e
        # The ollama client maps refused connections to ConnectionError, but timeouts
        # (e.g. a wrong IP that never answers) come through as raw httpx errors.
        except (ConnectionError, httpx.TransportError) as e:
            raise BackendError(f"Can't reach Ollama at {self._host}. Is it running and reachable?") from e

        try:
            return StoryBeat.model_validate_json(response.message.content)
        except ValidationError as e:
            raise BackendError(f"{self.model} returned a beat that didn't match the schema.") from e


def installed_models(host: str | None = None) -> set[str] | None:
    """Names of models pulled into Ollama, or None if Ollama can't be reached."""
    try:
        response = ollama.Client(host=host, timeout=3).list()
    except (ConnectionError, httpx.TransportError, ollama.ResponseError):
        return None
    # A name pulled without a tag is stored as ":latest".
    return {m.model if ":" in m.model else f"{m.model}:latest" for m in response.models}
