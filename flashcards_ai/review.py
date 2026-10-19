"""Terminal review session — the heart of flashcards-ai."""

from __future__ import annotations

import random
import re
import sys
from datetime import date

from .models import Card, Store
from .sm2 import due_cards, grade
from . import streaks as streaks_mod

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

_TYPE_HELP = "Type the answer for each blank (or 'q' to quit)"

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_answer(text: str) -> str:
    """Normalize a typed answer for comparison.

    Case-insensitive, surrounding whitespace stripped, internal whitespace
    collapsed, punctuation removed — so ``"  St. Louis "`` matches
    ``"st louis"``. Pure function (no I/O) so tests don't need a TTY.
    """
    return " ".join(_PUNCT_RE.sub("", text.lower()).split())


def grade_cloze_typed(expected: list[str], typed: list[str]) -> bool:
    """True when every typed blank matches its expected answer after
    normalization. Pure function (no I/O) so tests don't need a TTY."""
    return len(expected) == len(typed) and all(
        normalize_answer(e) == normalize_answer(t)
        for e, t in zip(expected, typed)
    )


def _type_grade_card(card: Card) -> int | None:
    """Quiz one cloze card by typing: prompt for each blanked answer.

    Returns 5 when every blank matches, 2 when any is wrong, or None when
    the user quits. The front already shows ``[hint]`` for hinted masks.
    """
    n = len(card.cloze_answers)
    typed = []
    for j in range(1, n + 1):
        label = f"Blank {j}/{n}" if n > 1 else "Type the missing answer"
        print(f"\n{label} {_c(_DIM, '(q to quit)')}")
        raw = _prompt("> ")
        if raw.strip().lower() == "q":
            return None
        typed.append(raw)
    if grade_cloze_typed(card.cloze_answers, typed):
        print(_c(_GREEN, "✓ correct"))
        return 5
    print(_c(_RED, "✗ wrong — ") + f"the answer: {_c(_GREEN, card.back)}")
    return 2


def _self_grade_card(card: Card) -> int | None:
    """Classic flip + self-grade flow. Returns the 1–5 quality, or None
    when the user quits."""
    _prompt(_c(_DIM, "\n[flip] "))
    print(_c(_GREEN, card.back))

    while True:
        raw = _prompt("\n" + _GRADE_HELP + "\n> ").strip().lower()
        if raw in {"q", "quit", "exit"}:
            return None
        if raw in {"1", "2", "3", "4", "5"}:
            return int(raw)
        # Forgiving aliases: e= easy(5), g=good(4), h=hard(3), a=again(1)
        alias = {"e": 5, "g": 4, "h": 3, "a": 1}.get(raw)
        if alias is not None:
            return alias
        print(_c(_RED, "Enter 1–5 (or q to quit)."))


def _is_typeable(card: Card) -> bool:
    """A cloze card whose blanked answers are known can be typed instead of
    self-graded. Older decks (created before answers were stored) and
    non-cloze cards fall back to the classic flow."""
    return "cloze" in {t.lower() for t in card.tags} and bool(card.cloze_answers)


def _remembered_of(stats: dict) -> int:
    """Cards graded 3+ (recalled) in a session stats dict."""
    return stats["hard"] + stats["good"] + stats["easy"]


def review(deck_name: str, store: Store, limit: int = 0, shuffle: bool = True,
           tags: list[str] | None = None, type_mode: bool = False) -> dict:
    """Run an interactive review session. Returns session stats.

    When *tags* is given, only due cards carrying at least one of those
    tags (case-insensitive) take part in the session. When *type_mode* is
    true, cloze cards with known answers are quizzed by typing the blank;
    every other card keeps the classic flip + self-grade flow.
    """
    deck = store.load(deck_name)
    cards = due_cards(deck.cards)
    wanted = {t.lower() for t in (tags or [])}
    if wanted:
        cards = [c for c in cards if wanted & {t.lower() for t in c.tags}]
        if not cards:
            print(f"No due cards tagged {', '.join(sorted(wanted))} in '{deck_name}'.")
            return {"reviewed": 0, "again": 0, "hard": 0, "good": 0, "easy": 0}
    if shuffle:
        random.shuffle(cards)
    if limit:
        cards = cards[:limit]

    total = len(cards)
    tag_note = f"  [tags: {', '.join(sorted(wanted))}]" if wanted else ""
    print(_c(_BOLD, f"\n📚 {deck_name} — {total} card{'s' if total != 1 else ''} due{tag_note}"))
    info = streaks_mod.summarize(streaks_mod.read_sessions(store))
    if info["today"] == 0 and info["current"] > 0:
        print(_c(_YELLOW, f"🔥 {info['current']}-day streak on the line! "
                           "Review today to keep it alive.\n"))
    if type_mode:
        print(_c(_DIM, _TYPE_HELP + " — other cards flip + self-grade as usual.\n"))
    else:
        print(_c(_DIM, "Press Enter to flip. " + _GRADE_HELP + "\n"))

    stats = {"reviewed": 0, "again": 0, "hard": 0, "good": 0, "easy": 0}
    for i, card in enumerate(cards, 1):
        print(_c(_CYAN, f"─── card {i}/{total} ───"))
        print(_c(_BOLD, card.front))

        if type_mode and _is_typeable(card):
            quality = _type_grade_card(card)
        else:
            quality = _self_grade_card(card)
        if quality is None:
            print(_c(_DIM, "Session paused — progress saved."))
            store.save(deck)
            streaks_mod.log_session(store, deck_name, stats["reviewed"],
                                    remembered=_remembered_of(stats))
            return stats

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
    streaks_mod.log_session(store, deck_name, stats["reviewed"],
                            remembered=_remembered_of(stats))
    return stats
