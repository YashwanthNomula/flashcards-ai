"""Tests for the store, deck persistence, and CLI plumbing."""

import json
from datetime import date, timedelta

import pytest

from flashcards_ai import cli
from flashcards_ai.models import Card, Deck, Store
from flashcards_ai.sm2 import Schedule
from flashcards_ai import stats as stats_mod


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    return Store()


def test_round_trip(store):
    deck = Deck(name="demo", cards=[
        Card("f1", "b1", tags=["t"]),
        Card("f2", "b2", schedule=Schedule(easiness=2.1, interval=6, reps=2,
                                          due=date(2026, 9, 30))),
    ])
    store.save(deck)
    loaded = store.load("demo")
    assert loaded.name == "demo"
    assert [c.front for c in loaded.cards] == ["f1", "f2"]
    assert loaded.cards[0].tags == ["t"]
    assert loaded.cards[1].schedule.easiness == pytest.approx(2.1)
    assert loaded.cards[1].schedule.due == date(2026, 9, 30)


def test_unicode_survives(store):
    deck = Deck(name="uni", cards=[Card("日本語", "Japanese 🎌")])
    store.save(deck)
    assert store.load("uni").cards[0].back == "Japanese 🎌"


def test_deck_names_and_delete(store):
    store.save(Deck(name="a"))
    store.save(Deck(name="b"))
    assert store.deck_names() == ["a", "b"]
    assert store.delete("a") and not store.delete("missing")
    assert store.deck_names() == ["b"]


def test_cli_add_import_list_export(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path / "home"))
    notes = tmp_path / "n.md"
    notes.write_text("Q: sky?\nA: blue\n")
    assert cli.main(["import", str(notes), "--deck", "d1"]) == 0
    assert cli.main(["add", "d1", "--front", "f", "--back", "b", "--tag", "x"]) == 0
    assert cli.main(["list", "d1"]) == 0
    out = capsys.readouterr().out
    assert "sky?" in out and "blue" in out
    assert cli.main(["list"]) == 0
    assert "d1: 2 cards" in capsys.readouterr().out
    tsv = tmp_path / "out.tsv"
    assert cli.main(["export", "d1", str(tsv)]) == 0
    assert "sky?\tblue" in tsv.read_text()


def test_cli_add_requires_both_sides(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("builtins.input", lambda _="": "")
    assert cli.main(["add", "d", "--front", "only-front"]) != 0


def test_review_session_grades_and_reschedules(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    store = Store()
    deck = Deck(name="r", cards=[Card("2+2?", "4"), Card("sky?", "blue")])
    store.save(deck)
    inputs = iter(["", "5", "", "2"])  # flip, grade 5; flip, grade 2
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    result = cli.main(["review", "r", "--no-shuffle"])
    assert result == 0
    assert capsys.readouterr().out.count("next review") == 2
    reloaded = store.load("r")
    assert reloaded.cards[0].schedule.interval == 1      # grade 5 -> 1 day
    assert reloaded.cards[1].schedule.interval == 1      # grade 2 -> reset to 1
    assert reloaded.cards[1].lapses == 1


def test_review_quit_saves_progress(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    store = Store()
    store.save(Deck(name="q", cards=[Card("a", "b"), Card("c", "d")]))
    inputs = iter(["", "q"])
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    cli.main(["review", "q", "--no-shuffle"])
    assert store.load("q").cards[0].reviews == 0  # quit before grading


def test_stats_retention_and_forecast():
    today = date(2026, 9, 30)
    cards = [
        Card("a", "b", reviews=10, lapses=2,
             schedule=Schedule(due=today + timedelta(days=3))),
        Card("c", "d", reviews=0, schedule=Schedule(due=today)),
    ]
    deck = Deck(name="s", cards=cards)
    assert stats_mod.retention(deck) == pytest.approx(0.8)
    assert stats_mod.retention(Deck(name="empty")) is None
    fc = stats_mod.forecast(deck, days=5, today=today)
    assert fc[today] == 1 and fc[today + timedelta(days=3)] == 1
    assert sum(fc.values()) == 2
