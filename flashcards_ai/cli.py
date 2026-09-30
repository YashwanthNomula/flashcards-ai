"""Command-line interface for flashcards-ai."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import review as review_mod
from . import stats as stats_mod
from .importers import auto_import
from .models import Card, Store
from .sm2 import due_cards

VERSION = "1.0.0"


def _store() -> Store:
    return Store()


def cmd_add(args) -> int:
    store = _store()
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
    review_mod.review(args.deck, _store(), limit=args.limit, shuffle=not args.no_shuffle)
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


def cmd_stats(args) -> int:
    stats_mod.show(_store().load(args.deck), days=args.days)
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
    r.set_defaults(func=cmd_review)

    l = sub.add_parser("list", help="List decks, or cards in a deck")
    l.add_argument("deck", nargs="?")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("stats", help="Retention stats and workload forecast")
    s.add_argument("deck")
    s.add_argument("--days", type=int, default=7)
    s.set_defaults(func=cmd_stats)

    e = sub.add_parser("export", help="Export a deck to TSV")
    e.add_argument("deck")
    e.add_argument("output")
    e.set_defaults(func=cmd_export)

    d = sub.add_parser("delete", help="Delete a deck")
    d.add_argument("deck")
    d.set_defaults(func=cmd_delete)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
