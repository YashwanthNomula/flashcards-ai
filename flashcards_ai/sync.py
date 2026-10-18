"""Shareable Markdown format for decks: ``flashcards-ai sync``.

A deck exported with :func:`deck_to_markdown` is a plain Markdown file any
human can read, edit, and hand to someone else — no JSON, no tooling needed.
Importing it back (:func:`deck_from_markdown`) round-trips every card's
front, back, and tags. Only card *contents* are shared; SM-2 review history
stays private to your machine.

The format looks like this::

    # flashcards-ai deck: python

    > Exported 2026-10-01 from flashcards-ai 1.2.0. Share this file with
    > anyone — they can import it with `flashcards-ai sync import file.md
    > --deck <name>`. Only card contents are shared; review history is not.

    <!-- card -->
    ## Front
    What does the GIL prevent in CPython?
    ## Back
    True parallel execution of Python bytecode across threads.
    <!-- tags: python, concurrency -->

Card text that happens to look like a structural line (``## Back``, the
``<!-- card -->`` delimiter, …) is escaped with a leading backslash on export
and unescaped on import — and so is any line that already starts with a
backslash, so even adversarial cards round-trip cleanly.
"""

from __future__ import annotations

import re
from datetime import date

from .models import Card, Deck

_CARD_RE = re.compile(r"(?m)^\s*<!--\s*card\s*-->\s*$")
_FRONT_RE = re.compile(r"^\s*##\s+Front\s*$")
_BACK_RE = re.compile(r"^\s*##\s+Back\s*$")
_TAGS_RE = re.compile(r"^\s*<!--\s*tags\s*:\s*(.*?)\s*-->\s*$")


def _is_structural(line: str) -> bool:
    """True if a content line would be mistaken for a format marker."""
    return bool(_CARD_RE.match(line) or _FRONT_RE.match(line)
                or _BACK_RE.match(line) or _TAGS_RE.match(line))


def _escape(text: str) -> str:
    # Escape structural lines so they can't be mistaken for format markers.
    # Backslash-led lines are escaped too: otherwise `\## Back` in card text
    # would be indistinguishable from an escaped `## Back` on import.
    return "\n".join(f"\\{line}" if _is_structural(line) or line.startswith("\\")
                     else line
                     for line in text.splitlines())


def _unescape(text: str) -> str:
    return "\n".join(line[1:] if line.startswith("\\") else line
                     for line in text.splitlines())


def deck_to_markdown(deck: Deck, version: str = "1.3.0") -> str:
    """Render a deck as shareable Markdown."""
    lines = [
        f"# flashcards-ai deck: {deck.name}",
        "",
        f"> Exported {date.today().isoformat()} from flashcards-ai {version}.",
        "> Share this file with anyone — they can import it with",
        "> `flashcards-ai sync import <file> --deck <name>`.",
        "> Only card contents are shared; review history stays private.",
        "",
    ]
    for card in deck.cards:
        lines.append("<!-- card -->")
        lines.append("## Front")
        lines.append(_escape(card.front).rstrip())
        lines.append("## Back")
        lines.append(_escape(card.back).rstrip())
        if card.tags:
            lines.append(f"<!-- tags: {', '.join(card.tags)} -->")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def deck_from_markdown(text: str, name: str) -> Deck:
    """Parse a shareable-Markdown file back into a deck.

    Malformed card blocks (missing ``## Back``, empty sides, …) are skipped
    rather than failing the whole import.
    """
    deck = Deck(name=name)
    for block in _CARD_RE.split(text):
        card = _parse_block(block)
        if card is not None:
            deck.cards.append(card)
    return deck


def _parse_block(block: str) -> Card | None:
    lines = block.splitlines()
    try:
        front_idx = next(i for i, l in enumerate(lines) if _FRONT_RE.match(l))
        back_idx = next(i for i, l in enumerate(lines)
                        if i > front_idx and _BACK_RE.match(l))
    except StopIteration:
        return None
    tail = lines[back_idx + 1:]
    end = next((i for i, l in enumerate(tail) if _TAGS_RE.match(l)), len(tail))
    tags_line = tail[end] if end < len(tail) else ""
    tags = [t.strip() for t in _TAGS_RE.match(tags_line).group(1).split(",")
            if t.strip()] if _TAGS_RE.match(tags_line) else []
    front = _unescape("\n".join(lines[front_idx + 1: back_idx]).strip("\n"))
    back = _unescape("\n".join(tail[:end]).strip("\n"))
    if not front.strip() or not back.strip():
        return None
    return Card(front=front, back=back, tags=tags)
