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

For Anki-style cards, number the masks — `{{c1::...}}`, `{{c2::...}}` generate
one card *per number* (card 1 masks only the `c1` blanks, card 2 only the `c2`
blanks, ...). An optional `{{c1::answer::hint}}` form shows `[hint]` on that
card's front.

Anything else falls back to blank-line-separated front/back paragraph pairs.

### Cloze mode in `fai add`

`flashcards-ai add <deck> --cloze` turns one sentence into several
fill-in-the-blank cards — pick which words to blank and each one becomes
its own numbered-cloze card (the front masks only that word, in full
context):

```console
$ flashcards-ai add python --cloze --text "The GIL prevents true parallel execution of bytecode"
Pick words to mask:
   1: The
   2: GIL
   3: prevents
   4: true
   5: parallel
   6: execution
   7: of
   8: bytecode
Mask which words? (e.g. 2, 1,4, 1-3): 2,4-5
- The [...] prevents true parallel execution of bytecode
- The GIL prevents [...] of bytecode
Added 2 cloze card(s) to 'python'.
```

Pass `--mask` for non-interactive use (`--mask 2`, `--mask 1,4`,
`--mask 1-3`).

## Commands

```
flashcards-ai add <deck> [--front ... --back ...]   # add one card
flashcards-ai add <deck> --cloze [--text ...] [--mask 1,4]  # blank out words → cloze cards
flashcards-ai import <file> --deck <deck> [--tag t]  # auto-generate cards
flashcards-ai review <deck> [--limit N] [--tag t ...] [--type]  # interactive SM-2 session
flashcards-ai streak [--deck <deck>]                 # review streaks + totals
flashcards-ai remind                                 # one-line daily reminder (cron-safe)
flashcards-ai list [deck]                           # decks, or cards in a deck
flashcards-ai stats <deck> [--days N]               # retention + workload forecast
flashcards-ai analytics [--deck <deck>] [--days N] [--json]  # retention curves + forgetting-curve estimates
flashcards-ai leeches [--deck <deck>] [--threshold N] [--json]  # cards you keep forgetting
flashcards-ai export <deck> <file.tsv>              # backup / share
flashcards-ai delete <deck>                         # remove a deck
flashcards-ai sync export <deck> <file.md>          # shareable Markdown
flashcards-ai sync import <file.md> --deck <deck>   # import a shared deck
```

### Sharing decks with `sync`

`export` writes TSV; `sync export` writes **shareable Markdown** — a file any
human can read and edit, and anyone with flashcards-ai can import:

```console
$ flashcards-ai sync export python > python-deck.md
Exported 7 cards from 'python' to python-deck.md.

$ flashcards-ai sync import python-deck.md --deck python --tag shared
Imported 7 cards into 'python' from python-deck.md.
```

Importing *appends* (merge, never overwrite), and only card contents travel —
your SM-2 review history stays private to your machine.

During review you can grade with `1–5`, or the fast aliases `a` (again), `h` (hard),
`g` (good), `e` (easy) — and `q` quits anytime with progress saved.

### Typing mode for cloze cards

`flashcards-ai review <deck> --type` quizzes cloze cards by making you *type*
the blanked answer instead of self-grading — no peeking, no mercy:

```console
$ flashcards-ai review capitals --type --no-shuffle

─── card 1/2 ───
The capital of France is [country].

Type the missing answer (q to quit)
> paris
✓ correct

─── card 2/2 ───
The GIL prevents [...] of bytecode in CPython.

Type the missing answer (q to quit)
> thread safety
✗ wrong — the answer: The GIL prevents true parallel execution of bytecode in CPython.
```

Comparison is forgiving: case-insensitive, extra whitespace collapsed,
punctuation ignored (`St. Louis` matches `st louis`). A correct answer
counts as a perfect recall (5); a wrong one counts as wrong (2) and the card
restarts. Cards with several blanks on one card ask for each blank in turn;
all of them must match.

Hints still show — a `{{c1::Paris::country}}` mask prints `[country]` on the
front. Non-cloze cards are untouched: they flip and self-grade as usual.

Decks created before v1.5.0 don't carry stored answers, so their cloze cards
fall back to flip + self-grade in typing mode. Re-import or re-add a deck
(`import` / `add --cloze` record answers automatically) to unlock typing.

## Streaks and daily reminders

Every review session is logged privately on your machine
(`~/.flashcards-ai/_sessions.json` — never synced or exported):

```console
$ fai streak
🔥 Streak
  current:  6 days   longest: 11
  total reviews: 214   reviewed today: 12   active days: 31
  🔥 6 days strong — don't break the chain.

$ fai remind
⏰ No reviews yet today — 6-day streak on the line, 9 due now. Run `fai review <deck>`!
```

When you start a review with an active streak at risk, the session opens with
a `🔥 N-day streak on the line!` nudge. `fai remind` is non-interactive, so it
works from cron for a morning ping.

## Review analytics

`fai analytics [--deck <deck>] [--days N] [--json]` turns your session log
into learning analytics:

- **Retention curve** — recall rate per day over the last 14 days (recall =
  cards graded 3+; logged since v1.6.0, so older days show `n/a` instead of
  guessed numbers)
- **Forgetting curve** — measured recall vs SM-2's expected retention
  (`0.9^(t/interval)`), bucketed by days since last review and shown per deck
- **Basics** — session/review totals, current streak, per-deck retention

Sessions log `recalled` counts from v1.6.0 on — the curve fills in as you
review.

## Leech cards

`fai leeches [--deck <deck>] [--threshold N] [--json]` lists the cards
you keep failing — every grade below 3 counts as a lapse, and a card
with at least 3 lapses (the default threshold) is a leech, listed worst
first (most lapses, then lowest easiness). A leech usually means the
card itself needs rewriting — split it, ask one thing per front, or add
a cue — rather than more reviews of the same wording. Read-only: it
never edits a deck.

Grades follow SM-2: 5 perfect → interval × easiness, 3 = hard but recalled,
<3 = wrong → the card restarts and returns tomorrow. Easiness never drops below 1.3.

Review only part of a deck with `--tag` (repeatable, or comma-separated;
matching is case-insensitive):

```console
$ flashcards-ai review python --tag decorators,closures
$ flashcards-ai review vocab --tag nouns --tag verbs
```

If no due cards carry the tag(s), the session reports that and stops.

## Install

```console
pip install .
# then:
flashcards-ai --help
```

Requires Python ≥ 3.9. **Zero runtime dependencies** — the test suite is the only
dev dependency (`pip install -e . pytest && pytest` → 95 tests).

Set `FLASHCARDS_HOME` to keep decks somewhere other than `~/.flashcards-ai/`.

## Layout

```
flashcards_ai/
  sm2.py        # the SM-2 scheduling algorithm
  models.py     # Card / Deck / JSON store
  importers.py  # notes → cards (Q/A, TSV/CSV, definitions, cloze)
  review.py     # interactive terminal session
  stats.py      # retention + 7-day workload forecast
  leeches.py    # cards lapsed ≥ threshold, worst first (read-only report)
  streaks.py    # session log, streak math, streak/remind reports
  cli.py        # argparse entry point (`flashcards-ai`, alias `fai`)
tests/          # 95 tests: scheduler math, importers, store, CLI, review flow, sync, streaks, cloze typing
examples/       # sample_notes.md, vocab.tsv, cloze_notes.md — import these to try it
```

## License

MIT — see [LICENSE](LICENSE).
