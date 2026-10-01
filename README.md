# flashcards-ai 🃏

**Turn your notes into flashcards, then actually remember them** — a zero-dependency
CLI with the SM-2 spaced-repetition algorithm (the same scheduler family Anki uses).

Paste study notes in, get a deck out. Review daily in your terminal. Cards you
struggle with come back tomorrow; cards you nail disappear for weeks.

No accounts, no API keys, no network. Your decks live in `~/.flashcards-ai/`.

## The 60-second demo

```console
$ flashcards-ai import examples/sample_notes.md --deck python
Imported 6 cards into 'python' from examples/sample_notes.md.

$ flashcards-ai import examples/vocab.tsv --deck vocab
Imported 5 cards into 'vocab' from examples/vocab.tsv.

$ flashcards-ai list
python: 7 cards, 7 due
vocab: 5 cards, 5 due

$ flashcards-ai review python --no-shuffle

📚 python — 7 cards due
Press Enter to flip. How well did you recall it?  5 perfect · 4 ok · 3 hard · 2 wrong · 1 blanked · q quit

─── card 1/7 ───
What does the GIL prevent in CPython?

[flip] True parallel execution of Python bytecode across threads.
   I/O-bound code still benefits from threading because the GIL
   is released during blocking I/O.

How well did you recall it?  5 perfect · 4 ok · 3 hard · 2 wrong · 1 blanked · q quit
> 5
  → next review: 2026-10-01 (in 1d)

─── card 2/7 ───
What is the difference between `==` and `is`?
[...]

✓ Session complete: 7 reviewed, 1 to repeat.

$ flashcards-ai stats python

📊 python
  cards: 7   due now: 0   new: 0
  retention: 86% over 7 reviews

  upcoming workload (next 7 days)
  2026-09-30                       0
  2026-10-01  ███████░░░░░░░░░░░░░ 7
  2026-10-02                       0
  ...
```

*(Transcript above is real output, lightly trimmed — review excerpt shows cards 1–2 of 7.)*

## Auto-generating cards from notes

`flashcards-ai import <file> --deck <name>` detects the format automatically:

| Format | Example | Good for |
|---|---|---|
| `Q:` / `A:` notes (`.md`, `.txt`) | `Q: What is the GIL?` → `A: ...` (multi-line answers OK) | Study notes, lecture dumps |
| TSV / CSV | `front<TAB>back` (`#` comments ignored) | Spreadsheets, exports |
| Definition lists | `serendipity :: happy discovery by chance` | Vocabulary |
| Cloze deletion | `The GIL prevents {{true parallel execution}} of bytecode.` | Fill-in-the-blank recall |

Wrap any answer in `{{...}}` and the importer masks it as `[...]` on the front;
the back reveals the full line. Cloze cards get a `cloze` tag automatically.

Anything else falls back to blank-line-separated front/back paragraph pairs.

## Commands

```
flashcards-ai add <deck> [--front ... --back ...]   # add one card
flashcards-ai import <file> --deck <deck> [--tag t]  # auto-generate cards
flashcards-ai review <deck> [--limit N]             # interactive SM-2 session
flashcards-ai list [deck]                           # decks, or cards in a deck
flashcards-ai stats <deck> [--days N]               # retention + workload forecast
flashcards-ai export <deck> <file.tsv>              # backup / share
flashcards-ai delete <deck>                         # remove a deck
```

During review you can grade with `1–5`, or the fast aliases `a` (again), `h` (hard),
`g` (good), `e` (easy) — and `q` quits anytime with progress saved.

Grades follow SM-2: 5 perfect → interval × easiness, 3 = hard but recalled,
<3 = wrong → the card restarts and returns tomorrow. Easiness never drops below 1.3.

## Install

```console
pip install .
# then:
flashcards-ai --help
```

Requires Python ≥ 3.9. **Zero runtime dependencies** — the test suite is the only
dev dependency (`pip install -e . pytest && pytest` → 22 tests).

Set `FLASHCARDS_HOME` to keep decks somewhere other than `~/.flashcards-ai/`.

## Layout

```
flashcards_ai/
  sm2.py        # the SM-2 scheduling algorithm
  models.py     # Card / Deck / JSON store
  importers.py  # notes → cards (Q/A, TSV/CSV, definitions, cloze)
  review.py     # interactive terminal session
  stats.py      # retention + 7-day workload forecast
  cli.py        # argparse entry point (`flashcards-ai`, alias `fai`)
tests/          # 22 tests: scheduler math, importers, store, CLI, review flow
examples/       # sample_notes.md, vocab.tsv, cloze_notes.md — import these to try it
```

## License

MIT — see [LICENSE](LICENSE).
