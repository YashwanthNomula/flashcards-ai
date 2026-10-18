"""Interactive cloze-card creation for ``fai add --cloze``.

The user types (or passes) a sentence, picks which words to blank out, and
each pick becomes a numbered cloze mask (``{{c1::...}}``). Single numbers
mask one word; a range like ``4-5`` masks the whole contiguous phrase, so
concepts made of several words stay one blank. The numbered-mask machinery
in ``importers`` then generates one card per mask: that card's front hides
only its own mask and reveals the others as plain text, so each card
quizzes exactly one word or phrase in full context.
"""

from __future__ import annotations

import re

from .importers import from_cloze

_RANGE_RE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


def tokenize(line: str) -> list[str]:
    """Split a sentence into maskable words (whitespace-delimited)."""
    return line.split()


def parse_mask_groups(sel: str, n_words: int) -> list[list[int]]:
    """Parse a mask selection like ``2``, ``1,4`` or ``1,3-5`` into mask groups.

    Each comma-separated token is one mask: a single number masks one word
    (0-based index in a singleton list), a range ``a-b`` masks the whole
    contiguous phrase ``a..b``. Numbers are 1-based (matching the numbered
    list shown to the user); ranges are inclusive. Raises ``ValueError``
    with a helpful message on any malformed or out-of-range token.
    """
    if not sel or not sel.strip():
        raise ValueError("selection is empty — pick at least one word number")
    groups: list[list[int]] = []
    for token in sel.split(","):
        m = _RANGE_RE.match(token)
        if not m:
            raise ValueError(f"cannot parse {token!r} — use numbers like 2, 1,4 or 1-3")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1 or end > n_words or start > end:
            raise ValueError(
                f"{token.strip()!r} is out of range — words are numbered 1..{n_words}"
            )
        groups.append(list(range(start - 1, end)))
    return groups


def parse_selection(sel: str, n_words: int) -> list[int]:
    """Flat 0-based indices for a selection (de-duplicated, first-pick order)."""
    flat: list[int] = []
    for group in parse_mask_groups(sel, n_words):
        flat.extend(group)
    return list(dict.fromkeys(flat))


def mask_words(line: str, groups: list[list[int]]) -> str:
    """Wrap each mask group in a numbered cloze mask (phrase for ranges)."""
    words = tokenize(line)
    for k, group in enumerate(groups, start=1):
        phrase = " ".join(words[i] for i in group)
        words[group[0]] = f"{{{{c{k}::{phrase}}}}}"
        for i in group[1:]:
            words[i] = ""  # folded into the phrase at group[0]
    return " ".join(w for w in words if w)


def cloze_cards_from_words(line: str, groups: list[list[int]],
                            tags: list[str] | None = None):
    """Build fill-in-the-blank cards for the chosen words/phrases of ``line``.

    One card per mask group; each card's front masks only that group.
    """
    if not groups:
        raise ValueError("no words selected to mask")
    return from_cloze(mask_words(line, groups), tags=tags)


def numbered_words(line: str) -> str:
    """Render the sentence as a numbered word list for the interactive prompt."""
    return "\n".join(f"  {i:>2}: {w}" for i, w in enumerate(tokenize(line), start=1))
