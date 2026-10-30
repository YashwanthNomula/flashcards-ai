"""Tests for `fai leeches` — threshold, sorting, deck filter, unknown deck."""

import json

import pytest

from flashcards_ai import cli
from flashcards_ai.models import Card, Deck, Store
from flashcards_ai.sm2 import Schedule


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    return Store()


def _decks(store):
    store.save(Deck(name="python", cards=[
        Card("worst", "b", reviews=10, lapses=5,
             schedule=Schedule(easiness=1.3)),
        Card("tie-high", "b", reviews=8, lapses=3,
             schedule=Schedule(easiness=1.8)),
        Card("tie-low", "b", reviews=6, lapses=3,
             schedule=Schedule(easiness=1.5)),
        Card("ok", "b", reviews=10, lapses=2,
             schedule=Schedule(easiness=2.5)),
        Card("new", "b"),  # never reviewed: 0 lapses, never a leech
    ]))
    store.save(Deck(name="vocab", cards=[
        Card("vocab-leech", "b", reviews=4, lapses=4,
             schedule=Schedule(easiness=1.4)),
    ]))


def test_default_threshold_and_sorting(home, capsys):
    _decks(home)
    assert cli.main(["leeches", "--deck", "python"]) == 0
    out = capsys.readouterr().out
    # Default threshold 3: worst (5), then the two 3-lapse cards with the
    # lower easiness first; 2-lapse and new cards are not leeches.
    assert [f for f in ("worst", "tie-low", "tie-high")
            if f in out] == ["worst", "tie-low", "tie-high"]
    assert out.index("worst") < out.index("tie-low") < out.index("tie-high")
    assert "ok" not in out
    assert "new" not in out
    assert "python: 3 leech(es) (of 5 cards)" in out
    assert "5 lapses" in out


def test_threshold_flag(home, capsys):
    _decks(home)
    assert cli.main(["leeches", "--deck", "python", "--threshold", "5"]) == 0
    out = capsys.readouterr().out
    assert "worst" in out
    assert "tie-low" not in out and "tie-high" not in out
    assert "python: 1 leech(es) (of 5 cards)" in out


def test_threshold_below_one_fails_closed(home, capsys):
    _decks(home)
    assert cli.main(["leeches", "--threshold", "0"]) != 0
    assert "Threshold must be at least 1." in capsys.readouterr().err


def test_deck_filter_and_totals(home, capsys):
    _decks(home)
    assert cli.main(["leeches"]) == 0
    out = capsys.readouterr().out
    assert "python: 3 leech(es) (of 5 cards)" in out
    assert "vocab: 1 leech(es) (of 1 cards)" in out
    assert cli.main(["leeches", "--deck", "vocab"]) == 0
    out = capsys.readouterr().out
    assert "vocab-leech" in out
    assert "python:" not in out
    assert "worst" not in out


def test_unknown_deck_fails_closed(home, capsys):
    _decks(home)
    assert cli.main(["leeches", "--deck", "missing"]) != 0
    assert "No deck named 'missing'" in capsys.readouterr().err
    assert cli.main(["leeches", "--deck", "missing", "--json"]) != 0
    assert "No deck named 'missing'" in capsys.readouterr().err


def test_json_output(home, capsys):
    _decks(home)
    assert cli.main(["leeches", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["threshold"] == 3
    assert data["total_leeches"] == 4
    by_name = {d["name"]: d for d in data["decks"]}
    assert [c["front"] for c in by_name["python"]["leech_cards"]] == [
        "worst", "tie-low", "tie-high"]
    worst = by_name["python"]["leech_cards"][0]
    assert worst["lapses"] == 5 and worst["reviews"] == 10
    assert worst["easiness"] == 1.3 and worst["deck"] == "python"
    assert "ok" not in json.dumps(data)


def test_no_leeches(home, capsys):
    home.save(Deck(name="fresh", cards=[
        Card("a", "b", reviews=3, lapses=1),
    ]))
    assert cli.main(["leeches"]) == 0
    out = capsys.readouterr().out
    assert "fresh: 0 leech(es) (of 1 cards)" in out
    assert "No leech cards" in out
    assert "a  (" not in out
