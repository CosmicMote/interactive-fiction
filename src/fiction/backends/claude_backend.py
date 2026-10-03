from __future__ import annotations

import os

import anthropic
from pydantic import ValidationError

from fiction.backends.base import BackendError
from fiction.config import DEFAULT_CLAUDE_MODEL
from fiction.schema import StoryBeat

# fallbacks="default" re-runs some refusal categories on another model server-side.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeBackend:
    def __init__(self, model: str = DEFAULT_CLAUDE_MODEL, effort: str = "low", max_tokens: int = 8000):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise BackendError("ANTHROPIC_API_KEY is not set, so the Claude backend is unavailable.")
        self.model = model
        self.label = f"Claude · {model}"
        self._effort = effort
        self._max_tokens = max_tokens
        self._client = anthropic.Anthropic()

    def generate_beat(self, system: str, prompt: str) -> StoryBeat:
        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "effort": self._effort,
                    "format": {"type": "json_schema", "schema": StoryBeat.model_json_schema()},
                },
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as e:
            raise BackendError("Claude rejected the API key (ANTHROPIC_API_KEY).") from e
        except anthropic.RateLimitError as e:
            raise BackendError("Claude rate limit hit. Wait a moment and try again.") from e
        except anthropic.APIStatusError as e:
            raise BackendError(f"Claude API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise BackendError("Can't reach the Claude API. Check your connection.") from e

        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            detail = f" ({category})" if category else ""
            raise BackendError(f"Claude declined to write this beat{detail}. Try steering differently.")
        if response.stop_reason == "max_tokens":
            raise BackendError("Claude ran out of output tokens before finishing the beat.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise BackendError("Claude returned no beat.")
        try:
            return StoryBeat.model_validate_json(text)
        except ValidationError as e:
            raise BackendError("Claude returned a beat that didn't match the schema.") from e
