"""Prompt construction, shared verbatim by both backends."""

from __future__ import annotations

from fiction.config import RECENT_EXCHANGES
from fiction.schema import Act, StoryState

SYSTEM_PROMPT = """\
You are co-writing an interactive story with a player, one beat at a time. This is \
collaborative fiction, not a game: there is no inventory, no score, no win condition, \
and you never offer menus of choices.

Each turn you receive the story setup (if any), the established facts so far, the most \
recent exchange or two, pacing guidance, and the player's latest input. The player's \
input is what their character does, says, notices, or attempts. Honor it, then write \
what happens next.

Return one beat:
- narration: the next chunk of prose, in second person and present tense ("you"). \
Usually one to three paragraphs. Vivid and specific. End at a moment that invites the \
player to react, without asking "what do you do?" and without listing options.
- established_facts: the complete, updated list of what is now true in the story. \
Carry forward every fact that still holds, add new ones from this beat, rewrite ones \
that changed, and drop ones that are no longer true. Each fact is one short standalone \
statement (names, places, relationships, objects, wounds, promises, secrets revealed). \
Keep the list under about 30 items by merging minor details. Never contradict an \
established fact in the narration.
- act: where the story now stands - setup, rising, climax, or resolution. Follow the \
pacing guidance; acts only move forward.
- concluded: true only when the pacing guidance says this is the final turn and the \
narration resolves the story. Otherwise false.

The story setup describes the genre, tone, and setting the player wants. Let it shape \
the story, but don't record the setup request itself as a fact."""


def target_act(turn: int, target: int) -> Act:
    """The act a turn should be in, given its position relative to the target length.

    For a short (8-turn) story: turns 1-2 setup, 3-4 rising, 5-7 climax, 8 resolution.
    """
    if turn >= target:
        return "resolution"
    progress = turn / target
    if progress <= 0.25:
        return "setup"
    if progress <= 0.6:
        return "rising"
    return "climax"


def _pacing_section(state: StoryState, target: int) -> str:
    turn = state.next_turn_number
    suggested = target_act(turn, target)
    lines = [
        f"This is turn {turn} of a story targeting about {target} turns.",
        f"Current act: {state.act}. Suggested act for this beat: {suggested}.",
    ]
    if turn >= target:
        lines.append(
            "This is the FINAL turn. Resolve the story now: bring the central thread to a "
            "satisfying close in this beat, rather than continuing it or leaving it on a "
            "cliffhanger. Set act to \"resolution\" and concluded to true."
        )
    elif turn == target - 1:
        lines.append(
            "The story ends next turn. Bring events to their peak so the next beat can resolve them."
        )
    elif suggested == "climax":
        lines.append("Push toward the story's central confrontation or turning point.")
    return "\n".join(lines)


def build_turn_prompt(state: StoryState, player_input: str | None, target: int) -> str:
    """The user message for one turn: compact memory, not the whole transcript."""
    setup = state.config.setup_prompt.strip()
    sections = [
        "<story_setup>\n"
        + (setup or "None given. Invent an original setting, protagonist situation, and tone.")
        + "\n</story_setup>"
    ]

    facts = state.established_facts
    sections.append(
        "<established_facts>\n"
        + ("\n".join(f"- {f}" for f in facts) if facts else "None yet - this is the opening.")
        + "\n</established_facts>"
    )

    recent = state.turns[-RECENT_EXCHANGES:]
    if recent:
        exchanges = []
        for t in recent:
            if t.player_input:
                exchanges.append(f"Player: {t.player_input}")
            exchanges.append(f"Narrator: {t.beat.narration}")
        sections.append("<recent_exchanges>\n" + "\n\n".join(exchanges) + "\n</recent_exchanges>")

    sections.append("<pacing>\n" + _pacing_section(state, target) + "\n</pacing>")

    if player_input is None:
        sections.append(
            "Write the opening beat: establish the setting and the player's situation, "
            "and end on something they can react to."
        )
    else:
        sections.append(f"<player_input>\n{player_input}\n</player_input>")

    return "\n\n".join(sections)
