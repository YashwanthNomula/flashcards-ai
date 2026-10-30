"""Command-line interface for flashcards-ai."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import review as review_mod
from . import analytics as analytics_mod
from . import due as due_mod
from . import leeches as leeches_mod
from . import stats as stats_mod
from . import streaks as streaks_mod
from . import sync as sync_mod
from . import cloze_add as cloze_add_mod
from .importers import auto_import
from .models import Card, Store
from .sm2 import due_cards

VERSION = "1.6.0"


def _store() -> Store:
    return Store()


def cmd_add(args) -> int:
    store = _store()
    if args.cloze:
        return cmd_add_cloze(store, args)
    deck = store.load(args.deck)
    front = args.front or input("Front: ").strip()
    back = args.back or input("Back: ").strip()
    if not front or not back:
        print("Both front and back are required.", file=sys.stderr)
        return 1
    deck.cards.append(Card(front=front, back=back, tags=args.tag or []))
    store.save(deck)
    print(f"Added to '{args.deck}' ({len(deck.cards)} cards).")
    return 0


def cmd_add_cloze(store: Store, args) -> int:
    """Interactive cloze mode: pick which words of a sentence to blank out."""
    line = args.text or input("Sentence: ").strip()
    words = cloze_add_mod.tokenize(line)
    if not words:
        print("No words given.", file=sys.stderr)
        return 1
    if args.mask:
        selection = args.mask
    else:
        print("Pick words to mask:")
        print(cloze_add_mod.numbered_words(line))
        try:
            selection = input("Mask which words? (e.g. 2, 1,4, 1-3): ")
        except EOFError:
            print("Mask selection is required (use --mask in non-interactive mode).",
                  file=sys.stderr)
            return 1
    try:
        groups = cloze_add_mod.parse_mask_groups(selection, len(words))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    cards = cloze_add_mod.cloze_cards_from_words(line, groups, tags=args.tag or [])
    deck = store.load(args.deck)
    deck.cards.extend(cards)
    store.save(deck)
    for c in cards:
        print(f"- {c.front}")
    print(f"Added {len(cards)} cloze card(s) to '{args.deck}'.")
    return 0


def cmd_import(args) -> int:
    store = _store()
    cards = auto_import(args.file, tags=args.tag or [])
    if not cards:
        print(f"No cards found in {args.file}.", file=sys.stderr)
        return 1
    deck = store.load(args.deck)
    deck.cards.extend(cards)
    store.save(deck)
    print(f"Imported {len(cards)} cards into '{args.deck}' from {args.file}.")
    return 0


def cmd_review(args) -> int:
    tags = [t.strip() for value in (args.tag or []) for t in value.split(",") if t.strip()]
    review_mod.review(args.deck, _store(), limit=args.limit, shuffle=not args.no_shuffle,
                      tags=tags, type_mode=args.type)
    return 0


def cmd_streak(args) -> int:
    streaks_mod.show(_store(), deck=args.deck)
    return 0


def cmd_remind(args) -> int:
    streaks_mod.remind(_store())
    return 0


def cmd_list(args) -> int:
    store = _store()
    if args.deck:
        deck = store.load(args.deck)
        if not deck.cards:
            print(f"No cards in '{args.deck}'.")
            return 0
        for c in deck.cards:
            due = c.schedule.due.isoformat() if c.schedule.due else "new"
            tags = f"  [{', '.join(c.tags)}]" if c.tags else ""
            print(f"- {c.front}  →  {c.back}  (due {due}){tags}")
        return 0
    names = store.deck_names()
    if not names:
        print("No decks yet. Try: flashcards-ai import examples/sample_notes.md --deck demo")
        return 0
    for name in names:
        deck = store.load(name)
        due = len(due_cards(deck.cards))
        print(f"{name}: {len(deck.cards)} cards, {due} due")
    return 0


def cmd_due(args) -> int:
    try:
        due_mod.show(_store(), deck=args.deck, as_json=args.as_json)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_leeches(args) -> int:
    try:
        leeches_mod.show(_store(), deck=args.deck, threshold=args.threshold,
                         as_json=args.as_json)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_stats(args) -> int:
    stats_mod.show(_store().load(args.deck), days=args.days)
    return 0


def cmd_analytics(args) -> int:
    analytics_mod.show(_store(), deck=args.deck, days=args.days,
                       as_json=args.as_json)
    return 0


def cmd_export(args) -> int:
    deck = _store().load(args.deck)
    out = Path(args.output)
    out.write_text("\n".join(f"{c.front}\t{c.back}" for c in deck.cards) + "\n",
                   encoding="utf-8")
    print(f"Exported {len(deck.cards)} cards to {out}.")
    return 0


def cmd_delete(args) -> int:
    if _store().delete(args.deck):
        print(f"Deleted deck '{args.deck}'.")
        return 0
    print(f"No deck named '{args.deck}'.", file=sys.stderr)
    return 1


def cmd_sync_export(args) -> int:
    deck = _store().load(args.deck)
    if not deck.cards:
        print(f"No cards in '{args.deck}'.", file=sys.stderr)
        return 1
    out = Path(args.output)
    out.write_text(sync_mod.deck_to_markdown(deck, version=VERSION),
                   encoding="utf-8")
    print(f"Exported {len(deck.cards)} cards from '{args.deck}' to {out}.")
    return 0


def cmd_sync_import(args) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1
    deck = sync_mod.deck_from_markdown(path.read_text(encoding="utf-8"),
                                       name=args.deck)
    if not deck.cards:
        print(f"No flashcards-ai cards found in {path}.", file=sys.stderr)
        return 1
    for card in deck.cards:
        card.tags = list(dict.fromkeys(card.tags + (args.tag or [])))
    target = _store().load(args.deck)
    target.cards.extend(deck.cards)
    _store().save(target)
    print(f"Imported {len(deck.cards)} cards into '{args.deck}' from {path}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flashcards-ai",
        description="SM-2 spaced-repetition flashcards in your terminal. "
                    "Auto-generate decks from notes, then review daily.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Add one card to a deck")
    a.add_argument("deck")
    a.add_argument("--front")
    a.add_argument("--back")
    a.add_argument("--tag", action="append", default=[])
    a.add_argument("--cloze", action="store_true",
                   help="Cloze mode: blank out chosen words of a sentence "
                        "(each masked word becomes its own fill-in-the-blank card)")
    a.add_argument("--text", help="Sentence to mask in cloze mode (else prompted)")
    a.add_argument("--mask", help="Words to mask in cloze mode (e.g. '2', '1,4', '1-3'; else prompted)")
    a.set_defaults(func=cmd_add)

    i = sub.add_parser("import", help="Auto-generate cards from notes/TSV/CSV")
    i.add_argument("file", help="Notes file (.md, .txt, .tsv, .csv)")
    i.add_argument("--deck", required=True)
    i.add_argument("--tag", action="append", default=[])
    i.set_defaults(func=cmd_import)

    r = sub.add_parser("review", help="Review due cards (interactive)")
    r.add_argument("deck")
    r.add_argument("--limit", type=int, default=0, help="Max cards this session (0 = all due)")
    r.add_argument("--no-shuffle", action="store_true")
    r.add_argument("--tag", action="append", default=[],
                   help="Only review cards with this tag (repeatable; commas OK)")
    r.add_argument("--type", action="store_true",
                   help="Typing mode: type the answer for cloze cards instead of "
                        "self-grading (non-cloze cards flip + self-grade as usual)")
    r.set_defaults(func=cmd_review)

    l = sub.add_parser("list", help="List decks, or cards in a deck")
    l.add_argument("deck", nargs="?")
    l.set_defaults(func=cmd_list)

    du = sub.add_parser("due", help="List cards due for review today")
    du.add_argument("--deck", help="Only list due cards from this deck")
    du.add_argument("--json", dest="as_json", action="store_true",
                    help="Machine-readable output")
    du.set_defaults(func=cmd_due)

    le = sub.add_parser("leeches", help="Cards you keep forgetting (lapse count)")
    le.add_argument("--deck", help="Only list leeches from this deck")
    le.add_argument("--threshold", type=int, default=leeches_mod.DEFAULT_THRESHOLD,
                    help="Minimum lapses to count as a leech (default 3)")
    le.add_argument("--json", dest="as_json", action="store_true",
                    help="Machine-readable output")
    le.set_defaults(func=cmd_leeches)

    s = sub.add_parser("stats", help="Retention stats and workload forecast")
    s.add_argument("deck")
    s.add_argument("--days", type=int, default=7)
    s.set_defaults(func=cmd_stats)

    n = sub.add_parser("analytics",
                       help="Retention curves and forgetting-curve estimates")
    n.add_argument("--deck", help="Only include this deck's sessions and cards")
    n.add_argument("--days", type=int, default=14,
                   help="Days of session history for the retention curve")
    n.add_argument("--json", dest="as_json", action="store_true",
                   help="Machine-readable output")
    n.set_defaults(func=cmd_analytics)

    k = sub.add_parser("streak", help="Review streaks from the session log")
    k.add_argument("--deck", help="Only count sessions for this deck")
    k.set_defaults(func=cmd_streak)

    m = sub.add_parser("remind", help="One-line daily review reminder (cron-safe)")
    m.set_defaults(func=cmd_remind)

    e = sub.add_parser("export", help="Export a deck to TSV")
    e.add_argument("deck")
    e.add_argument("output")
    e.set_defaults(func=cmd_export)

    d = sub.add_parser("delete", help="Delete a deck")
    d.add_argument("deck")
    d.set_defaults(func=cmd_delete)

    s = sub.add_parser("sync", help="Share decks as Markdown (export/import)")
    ssub = s.add_subparsers(dest="sync_command", required=True)
    se = ssub.add_parser("export", help="Export a deck to shareable Markdown")
    se.add_argument("deck")
    se.add_argument("output", help="Markdown file to write")
    se.set_defaults(func=cmd_sync_export)
    si = ssub.add_parser("import", help="Import a shared Markdown deck")
    si.add_argument("file", help="Markdown file exported with 'sync export'")
    si.add_argument("--deck", required=True, help="Deck to import into")
    si.add_argument("--tag", action="append", default=[])
    si.set_defaults(func=cmd_sync_import)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
