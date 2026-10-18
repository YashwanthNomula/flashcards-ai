"""Streak tracking and daily reminders.

Every finished (or quit mid-way) review session is appended to a small
private log next to the deck files (``_sessions.json`` in the store home —
underscore-prefixed so it never shows up as a deck). Each record is
``{"date": "YYYY-MM-DD", "deck": name, "reviewed": n}``.

The log is private to this machine: ``sync export`` only serializes card
fronts/backs/tags, so session history never leaves the user's disk.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .sm2 import due_cards

SESSIONS_FILENAME = "_sessions.json"


def sessions_path(store) -> Path:
    return Path(store.home) / SESSIONS_FILENAME


def read_sessions(store) -> list[dict]:
    """All session records, newest last. Tolerant of missing/corrupt files."""
    path = sessions_path(store)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    kept = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            date.fromisoformat(item["date"])
        except (KeyError, ValueError, TypeError):
            continue
        kept.append({
            "date": item["date"],
            "deck": item.get("deck", "?"),
            "reviewed": int(item.get("reviewed", 0) or 0),
        })
    return kept


def log_session(store, deck: str, reviewed: int, day: date | None = None) -> None:
    """Append a session record. Sessions with no graded cards log nothing."""
    reviewed = int(reviewed or 0)
    if reviewed <= 0:
        return
    sessions = read_sessions(store)
    sessions.append({
        "date": (day or date.today()).isoformat(),
        "deck": deck,
        "reviewed": reviewed,
    })
    sessions_path(store).write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def daily_totals(sessions: list[dict], deck: str | None = None) -> dict[str, int]:
    """Reviewed cards per day (ISO date -> count), optionally for one deck."""
    totals: dict[str, int] = {}
    for s in sessions:
        if deck is not None and s["deck"] != deck:
            continue
        n = int(s.get("reviewed", 0) or 0)
        if n <= 0:
            continue
        totals[s["date"]] = totals.get(s["date"], 0) + n
    return totals


def summarize(sessions: list[dict], today: date | None = None,
              deck: str | None = None) -> dict:
    """Streak stats.

    current: consecutive active days (>= 1 reviewed card) ending today or
        yesterday — 0 when the streak has lapsed.
    longest: longest ever run of consecutive active days.
    total_reviews: all graded cards ever (in the filtered scope).
    today: cards reviewed on `today`.
    active_days: distinct days with at least one reviewed card.
    """
    today = today or date.today()
    totals = daily_totals(sessions, deck)
    active = {date.fromisoformat(d) for d, n in totals.items() if n >= 1}

    current = 0
    cursor = today if today in active else today - timedelta(days=1)
    while cursor in active:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    prev = None
    for d in sorted(active):
        run = run + 1 if prev is not None and d == prev + timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d

    return {
        "current": current,
        "longest": longest,
        "total_reviews": sum(totals.values()),
        "today": totals.get(today.isoformat(), 0),
        "active_days": len(active),
    }


def due_now(store, today: date | None = None) -> int:
    """Cards due right now (due date <= today) across all decks."""
    today = today or date.today()
    total = 0
    for name in store.deck_names():
        deck = store.load(name)
        total += len(due_cards(deck.cards, today))
    return total


def _motivation(info: dict) -> str:
    n = info["current"]
    if n == 0:
        return "🌱 No active streak — run `fai review <deck>` today to start one."
    if n == 1:
        return "🔥 Day 1 down — the hardest one. Come back tomorrow."
    if n < 7:
        return f"🔥 {n} days strong — don't break the chain."
    return f"🔥🔥 {n}-day streak — absolute machine. Keep it rolling."


def show(store, deck: str | None = None) -> dict:
    """Print streak report. Returns the summary dict (handy for tests)."""
    info = summarize(read_sessions(store), deck=deck)
    label = f" — '{deck}'" if deck else ""
    print(f"\n🔥 Streak{label}")
    print(f"  current:  {info['current']} day{'s' if info['current'] != 1 else ''}"
          f"   longest: {info['longest']}")
    print(f"  total reviews: {info['total_reviews']}   "
          f"reviewed today: {info['today']}   "
          f"active days: {info['active_days']}")
    print(f"  {_motivation(info)}\n")
    return info


def remind(store) -> dict:
    """One-line daily reminder, non-interactive — safe to run from cron."""
    sessions = read_sessions(store)
    info = summarize(sessions)
    due = due_now(store)
    if info["today"] > 0:
        print(f"✓ Reviewed {info['today']} today — {due} due now. Streak: {info['current']}d 🔥")
    elif info["current"] > 0:
        print(f"⏰ No reviews yet today — {info['current']}-day streak on the line, "
              f"{due} due now. Run `fai review <deck>`!")
    else:
        print(f"⏰ {due} cards due — review today to start a streak. `fai review <deck>`")
    return {"today": info["today"], "current": info["current"], "due": due}
