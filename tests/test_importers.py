"""Tests for the card auto-generators."""

from flashcards_ai.importers import (
    auto_import,
    from_cloze,
    from_definitions,
    from_qa_notes,
    from_tsv,
)


def test_qa_notes_basic():
    text = """Q: What is the GIL?
A: The Global Interpreter Lock.
It prevents parallel bytecode execution.

Q: What is a decorator?
A: Syntax sugar for wrapping a function.
"""
    cards = from_qa_notes(text)
    assert len(cards) == 2
    assert cards[0].front == "What is the GIL?"
    assert "Global Interpreter Lock" in cards[0].back
    assert "parallel bytecode" in cards[0].back  # multi-line answer kept
    assert cards[1].front == "What is a decorator?"


def test_qa_notes_question_variant_and_tags():
    cards = from_qa_notes("Question - capital of France?\nAnswer: Paris", tags=["geo"])
    assert len(cards) == 1
    assert cards[0].tags == ["geo"]


def test_qa_notes_skips_empty_answers():
    assert from_qa_notes("Q: orphan with no answer\n") == []


def test_tsv_and_comments():
    text = "# comment\nfoo\tbar\nbaz\tqux\n"
    cards = from_tsv(text)
    assert [(c.front, c.back) for c in cards] == [("foo", "bar"), ("baz", "qux")]


def test_definitions():
    text = "serendipity :: finding something good without looking for it\n# skip\n"
    cards = from_definitions(text)
    assert len(cards) == 1
    assert cards[0].front == "serendipity"


def test_cloze_basic():
    text = "The GIL prevents {{true parallel execution}} of bytecode.\nplain line\n"
    cards = from_cloze(text)
    assert len(cards) == 1  # lines without {{...}} are skipped
    assert cards[0].front == "The GIL prevents [...] of bytecode."
    assert cards[0].back == "The GIL prevents true parallel execution of bytecode."
    assert cards[0].tags == ["cloze"]


def test_cloze_skips_comments():
    text = "# Header showing {{the syntax}} — not a card\nReal card: {{yes}}.\n"
    cards = from_cloze(text)
    assert len(cards) == 1
    assert cards[0].front == "Real card: [...]."


def test_cloze_multiple_blanks_and_tags():
    text = "`{{==}}` is by value, `{{is}}` is by identity.\n"
    cards = from_cloze(text, tags=["python", "cloze"])
    assert len(cards) == 1
    assert cards[0].front == "`[...]` is by value, `[...]` is by identity."
    assert cards[0].back == "`==` is by value, `is` is by identity."
    assert cards[0].tags == ["python", "cloze"]  # no duplicate 'cloze'


def test_auto_import_dispatch(tmp_path):
    md = tmp_path / "notes.md"
    md.write_text("Q: 2+2?\nA: 4\n")
    assert len(auto_import(md)) == 1
    tsv = tmp_path / "deck.tsv"
    tsv.write_text("a\tb\n")
    assert len(auto_import(tsv)) == 1
    defs = tmp_path / "vocab.txt"
    defs.write_text("hola :: hello\n")
    assert len(auto_import(defs)) == 1
    cloze = tmp_path / "cloze.md"
    cloze.write_text("Water boils at {{100°C}} at sea level.\n")
    cloze_cards = auto_import(cloze)
    assert len(cloze_cards) == 1
    assert cloze_cards[0].tags == ["cloze"]
    pairs = tmp_path / "pairs.txt"
    pairs.write_text("front one\n\nback one\n")
    assert len(auto_import(pairs)) == 1
