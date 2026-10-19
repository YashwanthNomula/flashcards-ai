"""Review analytics: retention curves and forgetting-curve estimates.

The session log only records aggregate counts per session — ``reviewed``
always, ``remembered`` (cards graded >= 3) since v1.6.0 — never per-card
grades. So retention is computed *per day*, not per card. The forgetting
curve is an *estimate* derived from current card state: SM-2 sets
``due = last_review + interval``, so ``days_since_review = today - (due -
interval)``, and each card's measured recall rate is
``(reviews - lapses) / reviews``.

Sessions logged before v1.6.0 carry no recall counts; those days show
``n/a`` in the retention curve rather than guessed numbers.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta

from . import streaks as streaks_mod
from .models import Deck

_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RESET = "\033[0m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


# Buckets of days since last review for the forgetting-curve estimate.
_BUCKETS = [(0, 2), (3, 6), (7, 13), (14, 29), (30, None)]


def retention_curve(sessions: list[dict], deck: str | None = None,
                    days: int = 14, today: date | None = None) -> list[dict]:
    """Daily retention over the last `days` days.

    Returns one entry per day with at least one logged session in scope:
    ``{"date", "reviewed", "remembered", "retention"}``. ``retention`` is
    None on days whose sessions predate recall logging (v1.6.0), rather
    than a made-up number.
    """
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    per_day: dict[date, dict] = {}
    for s in sessions:
        if deck is not None and s["deck"] != deck:
            continue
        d = date.fromisoformat(s["date"])
        if d < start or d > today:
            continue
        entry = per_day.setdefault(d, {"reviewed": 0, "remembered": 0, "recall_data": False})
        entry["reviewed"] += int(s.get("reviewed", 0) or 0)
        remembered = s.get("remembered")
        if remembered is not None:
            entry["remembered"] += int(remembered)
            entry["recall_data"] = True
    curve = []
    for d in sorted(per_day):
        entry = per_day[d]
        retention = None
        if entry["recall_data"] and entry["reviewed"] > 0:
            retention = entry["remembered"] / entry["reviewed"]
        curve.append({
            "date": d.isoformat(),
            "reviewed": entry["reviewed"],
            "remembered": entry["remembered"] if entry["recall_data"] else None,
            "retention": retention,
        })
    return curve


def forgetting_curve(deck: Deck, today: date | None = None) -> list[dict]:
    """Forgetting-curve estimate per days-since-review bucket.

    Per bucket: card count, measured recall rate (averaged per-card
    ``(reviews - lapses) / reviews``), and the SM-2 expected retention
    ``0.9 ** (t / interval)`` — SM-2 schedules reviews assuming ~90% recall
    at the due date, and exponential decay is the standard forgetting-curve
    model. Cards never reviewed (or with no due date) can't be placed on
    the curve and are skipped.
    """
    today = today or date.today()
    buckets: dict[tuple[int, int | None], list[float]] = {b: [] for b in _BUCKETS}
    expected: dict[tuple[int, int | None], list[float]] = {b: [] for b in _BUCKETS}
    for card in deck.cards:
        if card.reviews <= 0 or card.schedule.due is None:
            continue
        last_review = card.schedule.due - timedelta(days=card.schedule.interval)
        days_since = (today - last_review).days
        if days_since < 0:
            continue  # due date edited by hand; can't place honestly
        bucket = next(b for b in _BUCKETS
                      if b[0] <= days_since and (b[1] is None or days_since <= b[1]))
        measured = max(0.0, (card.reviews - card.lapses) / card.reviews)
        buckets[bucket].append(measured)
        interval = max(1, card.schedule.interval)
        expected[bucket].append(0.9 ** (days_since / interval))
    curve = []
    for lo, hi in _BUCKETS:
        measured = buckets[(lo, hi)]
        exp = expected[(lo, hi)]
        label = f"{lo}–{hi}d" if hi is not None else f"{lo}d+"
        curve.append({
            "bucket": label,
            "cards": len(measured),
            "measured": sum(measured) / len(measured) if measured else None,
            "sm2_expected": sum(exp) / len(exp) if exp else None,
        })
    return curve


def overall(store, deck: str | None = None) -> dict:
    """Headline stats: streaks, session totals, current deck retention."""
    sessions = streaks_mod.read_sessions(store)
    if deck is not None:
        sessions = [s for s in sessions if s["deck"] == deck]
    streak = streaks_mod.summarize(sessions, deck=None)  # already filtered above
    deck_names = [deck] if deck else store.deck_names()
    deck_retention = {}
    for name in deck_names:
        d = store.load(name)
        total = sum(c.reviews for c in d.cards)
        if total:
            deck_retention[name] = (total - sum(c.lapses for c in d.cards)) / total
    return {
        "sessions": len(sessions),
        "total_reviews": sum(int(s.get("reviewed", 0) or 0) for s in sessions),
        "streak": streak,
        "deck_retention": deck_retention,
    }


def analyze(store, deck: str | None = None, days: int = 14,
            today: date | None = None) -> dict:
    """Full analytics payload — the same shape `fai analytics --json` prints."""
    today = today or date.today()
    sessions = streaks_mod.read_sessions(store)
    names = [deck] if deck else store.deck_names()
    return {
        "deck": deck,
        "days": days,
        "generated": today.isoformat(),
        "overall": overall(store, deck=deck),
        "retention_curve": retention_curve(sessions, deck=deck, days=days, today=today),
        "forgetting_curve": {name: forgetting_curve(store.load(name), today=today)
                             for name in names},
        "note": ("Days whose sessions predate v1.6.0 recall logging show n/a "
                 "retention. The forgetting curve is an estimate from current "
                 "card state (SM-2 schedule + review/lapse counts), not per-review "
                 "grade history."),
    }


def _bar(rate: float, width: int = 16) -> str:
    filled = round(width * rate)
    return "█" * filled + "░" * (width - filled)


def show(store, deck: str | None = None, days: int = 14, as_json: bool = False,
         today: date | None = None) -> dict:
    """Print the analytics report. Returns the payload dict (handy for tests)."""
    data = analyze(store, deck=deck, days=days, today=today)
    if as_json:
        print(json.dumps(data, indent=2))
        return data
    label = f" — '{deck}'" if deck else ""
    print(_c(_BOLD, f"\n📈 Analytics{label} (last {days} days)"))
    ov = data["overall"]
    streak = ov["streak"]
    print(f"  sessions: {ov['sessions']}   reviews: {ov['total_reviews']}   "
          f"current streak: {streak['current']}d (longest {streak['longest']}d)")
    for name, r in ov["deck_retention"].items():
        print(f"  retention '{name}': {_c(_GREEN if r >= 0.8 else _YELLOW, f'{r:.0%}')}")

    print(_c(_BOLD, "\n  retention curve — recall rate per day"))
    curve = data["retention_curve"]
    if not curve:
        print(f"  {_c(_DIM, 'no session data yet — run `fai review <deck>` first')}")
    for point in curve:
        if point["retention"] is None:
            print(f"  {point['date']}  {_c(_DIM, 'n/a')}  "
                  f"({point['reviewed']} reviews, pre-v1.6.0 log)")
        else:
            print(f"  {point['date']}  {_c(_CYAN, _bar(point['retention']))}  "
                  f"{point['retention']:.0%}  ({point['reviewed']} reviews)")

    print(_c(_BOLD, "\n  forgetting curve — measured recall vs SM-2 expected"))
    any_cards = False
    for name, buckets in data["forgetting_curve"].items():
        rows = [b for b in buckets if b["cards"]]
        if not rows:
            continue
        any_cards = True
        print(f"  {_c(_DIM, name)}")
        for b in rows:
            exp = f"{b['sm2_expected']:.0%}" if b["sm2_expected"] is not None else "n/a"
            print(f"    {b['bucket']:>6}  {_c(_CYAN, _bar(b['measured']))}  "
                  f"{b['measured']:.0%}  (SM-2 ≈ {exp})  {b['cards']} cards")
    if not any_cards:
        print(f"  {_c(_DIM, 'no reviewed cards to estimate from yet')}")
    print(f"  {_c(_DIM, data['note'])}\n")
    return data
