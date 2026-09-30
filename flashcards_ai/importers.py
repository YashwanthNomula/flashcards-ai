"""Auto-generate cards from notes — no API key, no network, no magic.

Supported formats:

1. **Q:/A: notes** — plain text or Markdown where a question line starts
   with ``Q:`` (or ``Question:``) and the following lines up to the next
   ``A:`` / ``Answer:`` form the answer::

       Q: What does the GIL prevent in CPython?
       A: True parallel execution of Python bytecode threads.
          (IO-bound threads still benefit from threading.)

2. **TSV / CSV** — ``front<TAB>back`` rows, ``#`` lines are comments.

3. **Definition lists** — ``term :: definition`` or ``term — definition``
   lines become front/back pairs. Great for vocabulary.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from .models import Card

_Q_RE = re.compile(r"^\s*(?:Q|Question)\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_A_RE = re.compile(r"^\s*(?:A|Answer)\s*[:\-]\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_DEF_RE = re.compile(r"^(.+?)\s*(?:::|—|–|-{2,})\s*(.+?)\s*$")


def from_qa_notes(text: str, tags: list[str] | None = None) -> list[Card]:
    """Parse Q:/A: style notes into cards."""
    cards: list[Card] = []
    front: str | None = None
    answer_lines: list[str] = []
    in_answer = False

    def flush():
        nonlocal front, answer_lines, in_answer
        if front:
            back = "\n".join(answer_lines).strip()
            if back:
                cards.append(Card(front=front.strip(), back=back, tags=list(tags or [])))
        front, answer_lines, in_answer = None, [], False

    for line in text.splitlines():
        q = _Q_RE.match(line)
        a = _A_RE.match(line)
        if q:
            flush()
            front, in_answer = q.group(1), False
        elif a:
            in_answer = True
            if a.group(1):
                answer_lines.append(a.group(1))
        elif in_answer:
            answer_lines.append(line)
        elif front and line.strip() == "":
            continue
    flush()
    return cards


def from_tsv(text: str, tags: list[str] | None = None) -> list[Card]:
    """Parse front<TAB>back rows (also handles comma CSVs)."""
    cards: list[Card] = []
    sample = "\n".join(l for l in text.splitlines() if l.strip() and not l.startswith("#"))[:512]
    dialect = csv.Sniffer().sniff(sample, delimiters="\t,;|") if sample else csv.excel_tab
    for row in csv.reader(text.splitlines(), dialect):
        if not row or row[0].lstrip().startswith("#"):
            continue
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            cards.append(Card(front=row[0].strip(), back=row[1].strip(), tags=list(tags or [])))
    return cards


def from_definitions(text: str, tags: list[str] | None = None) -> list[Card]:
    """Parse ``term :: definition`` lines into cards."""
    cards: list[Card] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _DEF_RE.match(line)
        if m and m.group(1).strip() and m.group(2).strip():
            cards.append(Card(front=m.group(1).strip(), back=m.group(2).strip(),
                              tags=list(tags or [])))
    return cards


def auto_import(path: str | Path, tags: list[str] | None = None) -> list[Card]:
    """Guess the format from content/extension and generate cards."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".tsv", ".csv"}:
        return from_tsv(text, tags)
    if _Q_RE.search(text):
        return from_qa_notes(text, tags)
    cards = from_definitions(text, tags)
    if cards:
        return cards
    # Last resort: blank-line-separated pairs (front paragraph, back paragraph).
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    pairs = [Card(front=chunks[i], back=chunks[i + 1], tags=list(tags or []))
             for i in range(0, len(chunks) - 1, 2)]
    return pairs
