"""Tests for flashcards-ai sync: shareable Markdown export/import."""

import pytest

from flashcards_ai import cli
from flashcards_ai import sync as sync_mod
from flashcards_ai.models import Card, Deck, Store


@pytest.fixture()
def deck():
    return Deck(name="python", cards=[
        Card("What does the GIL prevent?",
             "True parallel execution of Python bytecode across threads.",
             tags=["python", "concurrency"]),
        Card("2+2?", "4\n(four, obviously)", tags=[]),
        Card("日本語 means?", "Japanese 🎌", tags=["vocab"]),
    ])


def test_round_trip(deck):
    md = sync_mod.deck_to_markdown(deck)
    back = sync_mod.deck_from_markdown(md, name="python2")
    assert [(c.front, c.back, c.tags) for c in back.cards] == \
           [(c.front, c.back, c.tags) for c in deck.cards]


def test_markdown_is_human_readable(deck):
    md = sync_mod.deck_to_markdown(deck)
    assert "# flashcards-ai deck: python" in md
    assert "## Front" in md and "## Back" in md
    assert "What does the GIL prevent?" in md
    assert "<!-- tags: python, concurrency -->" in md


def test_structural_lookalikes_are_escaped():
    deck = Deck(name="evil", cards=[
        Card("## Back\n\\## Back", "<!-- card -->\n<!-- tags: nope -->",
             tags=["x"]),
    ])
    back = sync_mod.deck_from_markdown(sync_mod.deck_to_markdown(deck), name="e")
    assert len(back.cards) == 1
    assert back.cards[0].front == deck.cards[0].front
    assert back.cards[0].back == deck.cards[0].back
    assert back.cards[0].tags == ["x"]


def test_malformed_blocks_are_skipped():
    text = ("# some notes\n\n<!-- card -->\n## Front\nonly front\n\n"
            "<!-- card -->\n## Front\nf\n## Back\nb\n<!-- tags: t1, t2 -->\n")
    deck = sync_mod.deck_from_markdown(text, name="n")
    assert [(c.front, c.back, c.tags) for c in deck.cards] == [("f", "b", ["t1", "t2"])]


def test_non_sync_markdown_imports_nothing():
    deck = sync_mod.deck_from_markdown("# just notes\n\nhello world\n", name="n")
    assert deck.cards == []


def test_cli_sync_export_import_round_trip(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path / "home"))
    assert cli.main(["add", "d", "--front", "sky?", "--back", "blue",
                     "--tag", "nature"]) == 0
    out = tmp_path / "d.md"
    assert cli.main(["sync", "export", "d", str(out)]) == 0
    assert "Exported 1 cards" in capsys.readouterr().out
    assert cli.main(["sync", "import", str(out), "--deck", "d2",
                     "--tag", "shared"]) == 0
    assert "Imported 1 cards into 'd2'" in capsys.readouterr().out
    store = Store()
    imported = store.load("d2").cards[0]
    assert (imported.front, imported.back) == ("sky?", "blue")
    assert imported.tags == ["nature", "shared"]
    # Importing twice appends (merge, not overwrite).
    assert cli.main(["sync", "import", str(out), "--deck", "d2"]) == 0
    assert len(store.load("d2").cards) == 2


def test_cli_sync_export_empty_deck_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    assert cli.main(["sync", "export", "ghost", str(tmp_path / "g.md")]) == 1


def test_cli_sync_import_bad_file_fails(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    notes = tmp_path / "n.md"
    notes.write_text("# plain notes, no cards\n")
    assert cli.main(["sync", "import", str(notes), "--deck", "d"]) == 1
    assert "No flashcards-ai cards" in capsys.readouterr().err
