"""Cards due for review today — the read-only counterpart to `fai review`.

This reuses the existing SM-2 due rule from :mod:`flashcards_ai.sm2`
exactly, so `fai due` and `fai review` never disagree about what is due:

* a card is due when its SM-2 due date is today or earlier, **or**
* it has never been reviewed, i.e. it has no due date yet
  (``schedule.due is None``).

So there is no "never due" bucket in this app: unreviewed (new) cards
count as due, are listed first within their deck (``due_cards`` sorts a
missing due date before every real date), and are shown as ``new`` in
text output / ``due: null`` with ``"new": true`` in JSON. Cards whose
due date is in the future are not listed.
"""

from __future__ import annotations

import json
import sys
from datetime import date

from .models import Store
from .sm2 import due_cards

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_NOTE = (
    "New cards (never reviewed, no due date) count as due, as in "
    "`fai review`, and are listed first as 'new'. "
    "Cards due in the future are not listed."
)


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if sys.stdout.isatty() else text


def collect(store: Store, deck: str | None = None,
            today: date | None = None) -> dict:
    """Due cards per deck — the same shape `fai due --json` prints.

    Raises ValueError for an unknown deck name (fail closed) instead of
    silently reporting an empty deck, because :meth:`Store.load` returns
    an empty deck for a missing name.
    """
    today = today or date.today()
    if deck is not None and deck not in store.deck_names():
        raise ValueError(f"No deck named '{deck}'.")
    names = [deck] if deck is not None else store.deck_names()
    decks = []
    for name in names:
        loaded = store.load(name)
        due = due_cards(loaded.cards, today=today)
        decks.append({
            "name": name,
            "cards": len(loaded.cards),
            "due": len(due),
            "due_cards": [{
                "deck": name,
                "front": c.front,
                "due": c.schedule.due.isoformat() if c.schedule.due else None,
                "new": c.schedule.due is None,
            } for c in due],
        })
    return {
        "date": today.isoformat(),
        "deck": deck,
        "total_due": sum(d["due"] for d in decks),
        "decks": decks,
        "note": _NOTE,
    }


def show(store: Store, deck: str | None = None, as_json: bool = False,
         today: date | None = None) -> dict:
    """Print the due report. Returns the payload dict (handy for tests)."""
    data = collect(store, deck=deck, today=today)
    if as_json:
        print(json.dumps(data, indent=2))
        return data
    print(_c(_BOLD, f"\n📚 Due today ({data['date']})"))
    if not data["decks"]:
        print("  No decks yet.")
    for d in data["decks"]:
        print(f"  {d['name']}: {d['due']} due (of {d['cards']} cards)")
    if data["total_due"]:
        for d in data["decks"]:
            if not d["due"]:
                continue
            print(f"\n{d['name']}:")
            for c in d["due_cards"]:
                due = "new" if c["new"] else c["due"]
                print(f"- {c['front']}  (due {due})")
    else:
        print("\nNo cards due today.")
    print(f"\n{_c(_DIM, 'Note: ' + _NOTE)}")
    return data
