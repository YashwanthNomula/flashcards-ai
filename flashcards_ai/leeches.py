"""Leech cards — the cards you keep forgetting.

A "leech" is a card whose lapse count has reached a threshold (default 3):
every grade below 3 in :mod:`flashcards_ai.review` increments
``card.lapses``, so a leech is a card that has failed repeatedly and is
probably badly worded, too broad, or testing more than one fact — the
classic Anki signal that the card itself needs rewriting, not more
repetition. This is read-only: it reports, it never edits a deck.

Cards are sorted worst first: most lapses, then lowest SM-2 easiness,
then front text (so the order is deterministic when lapses tie).
"""

from __future__ import annotations

import json
import sys

from .models import Store

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

DEFAULT_THRESHOLD = 3

_NOTE = (
    "A leech is a card that has lapsed (been graded below 3) at least "
    "as many times as the threshold. Consider rewriting it: split it "
    "into smaller cards, make the front ask one thing, or add a cue. "
    "More reviews of the same wording rarely fix a leech."
)


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


def collect(store: Store, deck: str | None = None,
            threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Leech cards per deck — the same shape `fai leeches --json` prints.

    Raises ValueError for an unknown deck name or a threshold below 1
    (fail closed) instead of silently reporting an empty list, because
    :meth:`Store.load` returns an empty deck for a missing name and a
    threshold of 0 would flag every card that was ever reviewed.
    """
    if threshold < 1:
        raise ValueError("Threshold must be at least 1.")
    if deck is not None and deck not in store.deck_names():
        raise ValueError(f"No deck named '{deck}'.")
    names = [deck] if deck is not None else store.deck_names()
    decks = []
    for name in names:
        loaded = store.load(name)
        leeches = [c for c in loaded.cards if c.lapses >= threshold]
        leeches.sort(key=lambda c: (-c.lapses, c.schedule.easiness, c.front))
        decks.append({
            "name": name,
            "cards": len(loaded.cards),
            "leeches": len(leeches),
            "leech_cards": [{
                "deck": name,
                "front": c.front,
                "lapses": c.lapses,
                "reviews": c.reviews,
                "easiness": c.schedule.easiness,
                "due": c.schedule.due.isoformat() if c.schedule.due else None,
            } for c in leeches],
        })
    return {
        "threshold": threshold,
        "deck": deck,
        "total_leeches": sum(d["leeches"] for d in decks),
        "decks": decks,
        "note": _NOTE,
    }


def show(store: Store, deck: str | None = None,
         threshold: int = DEFAULT_THRESHOLD, as_json: bool = False) -> dict:
    """Print the leech report. Returns the payload dict (handy for tests)."""
    data = collect(store, deck=deck, threshold=threshold)
    if as_json:
        print(json.dumps(data, indent=2))
        return data
    print(_c(_BOLD, f"\n🪱 Leech cards (≥{threshold} lapses)"))
    if not data["decks"]:
        print("  No decks yet.")
    for d in data["decks"]:
        print(f"  {d['name']}: {d['leeches']} leech(es) (of {d['cards']} cards)")
    if data["total_leeches"]:
        for d in data["decks"]:
            if not d["leeches"]:
                continue
            print(f"\n{d['name']}:")
            for c in d["leech_cards"]:
                print(f"- {c['front']}  ({c['lapses']} lapses, "
                      f"{c['reviews']} reviews, easiness {c['easiness']:.2f})")
    else:
        print("\nNo leech cards — nothing has lapsed that often yet.")
    print(f"\n{_c(_DIM, 'Note: ' + _NOTE)}")
    return data
