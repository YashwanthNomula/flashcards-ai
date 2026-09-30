"""Terminal review session — the heart of flashcards-ai."""

from __future__ import annotations

import random
import sys
from datetime import date

from .models import Card, Store
from .sm2 import due_cards, grade

# ANSI colors (disabled automatically when output is not a TTY).
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_RESET = "\033[0m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


def _prompt(text: str) -> str:
    try:
        return input(text)
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0)


_GRADE_HELP = (
    "How well did you recall it?  "
    f"{_c(_GREEN, '5')} perfect · {_c(_GREEN, '4')} ok · "
    f"{_c(_YELLOW, '3')} hard · {_c(_RED, '2')} wrong · "
    f"{_c(_RED, '1')} blanked · {_c(_DIM, 'q')} quit"
)


def review(deck_name: str, store: Store, limit: int = 0, shuffle: bool = True) -> dict:
    """Run an interactive review session. Returns session stats."""
    deck = store.load(deck_name)
    cards = due_cards(deck.cards)
    if shuffle:
        random.shuffle(cards)
    if limit:
        cards = cards[:limit]

    total = len(cards)
    print(_c(_BOLD, f"\n📚 {deck_name} — {total} card{'s' if total != 1 else ''} due"))
    print(_c(_DIM, "Press Enter to flip. " + _GRADE_HELP + "\n"))

    stats = {"reviewed": 0, "again": 0, "hard": 0, "good": 0, "easy": 0}
    for i, card in enumerate(cards, 1):
        print(_c(_CYAN, f"─── card {i}/{total} ───"))
        print(_c(_BOLD, card.front))
        _prompt(_c(_DIM, "\n[flip] "))
        print(_c(_GREEN, card.back))

        while True:
            raw = _prompt("\n" + _GRADE_HELP + "\n> ").strip().lower()
            if raw in {"q", "quit", "exit"}:
                print(_c(_DIM, "Session paused — progress saved."))
                store.save(deck)
                return stats
            if raw in {"1", "2", "3", "4", "5"}:
                quality = int(raw)
                break
            # Forgiving aliases: e= easy(5), g=good(4), h=hard(3), a=again(1)
            alias = {"e": 5, "g": 4, "h": 3, "a": 1}.get(raw)
            if alias is not None:
                quality = alias
                break
            print(_c(_RED, "Enter 1–5 (or q to quit)."))

        card.schedule = grade(card.schedule, quality)
        card.reviews += 1
        if quality < 3:
            card.lapses += 1
            stats["again"] += 1
        elif quality == 3:
            stats["hard"] += 1
        elif quality == 4:
            stats["good"] += 1
        else:
            stats["easy"] += 1
        stats["reviewed"] += 1
        nxt = card.schedule.due or date.today()
        print(_c(_DIM, f"  → next review: {nxt.isoformat()} (in {card.schedule.interval}d)\n"))
        store.save(deck)

    print(_c(_BOLD, _c(_GREEN, f"✓ Session complete: {stats['reviewed']} reviewed, "
                               f"{stats['again']} to repeat.")))
    return stats
