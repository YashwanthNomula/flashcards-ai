"""Learning stats: retention, workload forecast, streaks."""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date, timedelta

from .models import Deck
from .sm2 import is_due

_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_RESET = "\033[0m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


def retention(deck: Deck) -> float | None:
    """Fraction of reviews recalled (grade >= 3). None if no reviews yet."""
    graded = sum(c.reviews for c in deck.cards)
    if not graded:
        return None
    remembered = graded - sum(c.lapses for c in deck.cards)
    return remembered / graded


def forecast(deck: Deck, days: int = 7, today: date | None = None) -> dict[date, int]:
    """How many cards come due on each of the next `days` days."""
    today = today or date.today()
    counts: Counter = Counter()
    for c in deck.cards:
        if c.schedule.due and c.schedule.due >= today:
            delta = (c.schedule.due - today).days
            if delta < days:
                counts[today + timedelta(days=delta)] += 1
    return {today + timedelta(days=d): counts.get(today + timedelta(days=d), 0)
            for d in range(days)}


def _bar(n: int, width: int = 20) -> str:
    return "█" * min(n, width) + "░" * max(0, width - min(n, width))


def show(deck: Deck, days: int = 7) -> None:
    n = len(deck.cards)
    due = sum(1 for c in deck.cards if is_due(c.schedule))
    new = sum(1 for c in deck.cards if c.reviews == 0)
    print(_c(_BOLD, f"\n📊 {deck.name}"))
    print(f"  cards: {n}   due now: {_c(_GREEN if due else _DIM, str(due))}   new: {new}")
    r = retention(deck)
    if r is not None:
        total_reviews = sum(c.reviews for c in deck.cards)
        print(f"  retention: {r:.0%} over {total_reviews} reviews")
    else:
        print(f"  retention: {_c(_DIM, 'no reviews yet — run `review`!')}")
    print(_c(_BOLD, f"\n  upcoming workload (next {days} days)"))
    fc = forecast(deck, days)
    peak = max(fc.values()) if fc else 0
    for d, count in fc.items():
        width = round(20 * count / peak) if peak else 0
        print(f"  {d.isoformat()}  {_c(_CYAN, _bar(count, width).ljust(20))} {count}")
    print()
