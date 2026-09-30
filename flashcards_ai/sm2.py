"""SM-2 spaced repetition algorithm (SuperMemo 2).

The classic algorithm behind Anki's default scheduler. Given a card's
current scheduling state and a recall grade 0-5, it returns the new
easiness factor, interval (days), and repetition count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Schedule:
    easiness: float = 2.5   # EF, how "easy" the card is (min 1.3)
    interval: int = 0       # days until next review
    reps: int = 0           # consecutive successful recalls
    due: date | None = None # next review date


def grade(schedule: Schedule, quality: int, today: date | None = None) -> Schedule:
    """Apply an SM-2 review grade (0-5) and return the new schedule.

    Grades: 5 perfect, 4 correct w/ hesitation, 3 correct w/ difficulty,
    2 wrong but answer looked familiar, 1 wrong, 0 total blackout.
    """
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")
    today = today or date.today()

    new = Schedule(
        easiness=schedule.easiness,
        interval=schedule.interval,
        reps=schedule.reps,
    )

    if quality < 3:
        # Failed recall: restart the repetition chain, keep easiness floor.
        new.reps = 0
        new.interval = 1
    else:
        new.reps += 1
        if new.reps == 1:
            new.interval = 1
        elif new.reps == 2:
            new.interval = 6
        else:
            new.interval = round(new.interval * new.easiness)

    # Update easiness factor (applies on every review, pass or fail).
    new.easiness = max(
        1.3,
        new.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
    )
    new.due = today + timedelta(days=new.interval)
    return new


def is_due(schedule: Schedule, today: date | None = None) -> bool:
    today = today or date.today()
    return schedule.due is None or schedule.due <= today


def due_cards(cards, today: date | None = None):
    """Return the cards due for review today, oldest-due first."""
    today = today or date.today()
    due = [c for c in cards if is_due(c.schedule, today)]
    due.sort(key=lambda c: c.schedule.due or date.min)
    return due
