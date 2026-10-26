"""Tests for `fai due` — due vs not-yet-due, per-deck counts, filter, unknown deck."""

import json
from datetime import date, timedelta

import pytest

from flashcards_ai import cli
from flashcards_ai.models import Card, Deck, Store
from flashcards_ai.sm2 import Schedule


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    return Store()


def _deck_with_due_dates(store):
    today = date.today()
    store.save(Deck(name="python", cards=[
        Card("new-card", "b"),  # never reviewed: due is None -> due
        Card("due-yesterday", "b",
             schedule=Schedule(due=today - timedelta(days=1))),
        Card("due-today", "b", schedule=Schedule(due=today)),
        Card("due-tomorrow", "b",
             schedule=Schedule(due=today + timedelta(days=1))),
    ]))
    store.save(Deck(name="vocab", cards=[
        Card("vocab-due", "b", schedule=Schedule(due=today)),
        Card("vocab-future", "b",
             schedule=Schedule(due=today + timedelta(days=5))),
    ]))
    return today


def test_due_vs_not_yet_due_and_new_cards_first(home, capsys):
    _deck_with_due_dates(home)
    assert cli.main(["due", "--deck", "python"]) == 0
    out = capsys.readouterr().out
    # Due: new card, yesterday, today — in that order (None sorts first).
    assert [f for f in ("new-card", "due-yesterday", "due-today")
            if f in out] == ["new-card", "due-yesterday", "due-today"]
    assert out.index("new-card") < out.index("due-yesterday") < out.index("due-today")
    # Not yet due: tomorrow's card must not appear.
    assert "due-tomorrow" not in out
    # New-card semantics documented in the output.
    assert "new-card  (due new)" in out
    assert "New cards (never reviewed, no due date) count as due" in out


def test_per_deck_counts(home, capsys):
    _deck_with_due_dates(home)
    assert cli.main(["due"]) == 0
    out = capsys.readouterr().out
    assert "python: 3 due (of 4 cards)" in out
    assert "vocab: 1 due (of 2 cards)" in out


def test_deck_filter(home, capsys):
    _deck_with_due_dates(home)
    assert cli.main(["due", "--deck", "vocab"]) == 0
    out = capsys.readouterr().out
    assert "vocab: 1 due (of 2 cards)" in out
    assert "python:" not in out
    assert "vocab-due" in out
    assert "new-card" not in out


def test_unknown_deck_fails_closed(home, capsys):
    _deck_with_due_dates(home)
    assert cli.main(["due", "--deck", "missing"]) != 0
    assert "No deck named 'missing'" in capsys.readouterr().err
    # Same failure in JSON mode: no payload, no silent empty report.
    assert cli.main(["due", "--deck", "missing", "--json"]) != 0
    assert "No deck named 'missing'" in capsys.readouterr().err


def test_json_output(home, capsys):
    _deck_with_due_dates(home)
    assert cli.main(["due", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["date"] == date.today().isoformat()
    assert data["total_due"] == 4
    by_name = {d["name"]: d for d in data["decks"]}
    assert by_name["python"]["due"] == 3
    assert by_name["vocab"]["due"] == 1
    python_cards = by_name["python"]["due_cards"]
    assert [c["front"] for c in python_cards] == [
        "new-card", "due-yesterday", "due-today"]
    assert python_cards[0] == {
        "deck": "python", "front": "new-card", "due": None, "new": True}
    assert all(c["deck"] == "python" for c in python_cards)
    assert "due-tomorrow" not in json.dumps(data)


def test_no_cards_due(home, capsys):
    today = date.today()
    home.save(Deck(name="future", cards=[
        Card("later", "b",
             schedule=Schedule(due=today + timedelta(days=3))),
    ]))
    assert cli.main(["due"]) == 0
    out = capsys.readouterr().out
    assert "future: 0 due (of 1 cards)" in out
    assert "No cards due today." in out
    assert "later" not in out
