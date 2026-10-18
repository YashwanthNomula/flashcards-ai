"""Tests for per-tag review sessions (`fai review --tag`)."""

import pytest

from flashcards_ai import cli
from flashcards_ai.models import Card, Deck, Store


@pytest.fixture()
def deck_store(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    store.save(Deck(name="tags", cards=[
        Card("py-q", "py-a", tags=["python"]),
        Card("sql-q", "sql-a", tags=["SQL"]),          # mixed-case tag
        Card("both-q", "both-a", tags=["python", "sql"]),
        Card("plain-q", "plain-a"),                    # no tags
    ]))
    return store


def _review(monkeypatch, *argv, grades=("5", "5", "5", "5")):
    """Drive a CLI review session through the given grades; return the exit code."""
    sequence = []
    for g in grades:
        sequence += ["", g]  # flip, then grade
    inputs = iter(sequence)
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    return cli.main(list(argv))


def test_review_single_tag_only_reviews_matching_cards(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--tag", "python", "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "card 1/2" in out and "card 2/2" in out
    assert "py-q" in out and "both-q" in out
    assert "sql-q" not in out and "plain-q" not in out


def test_review_tag_matching_is_case_insensitive(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--tag", "sql", "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "sql-q" in out and "both-q" in out
    assert "py-q" not in out and "plain-q" not in out


def test_review_multiple_tags(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--tag", "python", "--tag", "sql",
                   "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "card 1/3" in out
    assert "plain-q" not in out


def test_review_comma_separated_tags(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--tag", "python,sql",
                   "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "card 1/3" in out
    assert "plain-q" not in out


def test_review_no_matching_tags_reports_and_reviews_nothing(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--tag", "rust", "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "No due cards tagged rust in 'tags'." in out
    assert "Session complete" not in out
    assert deck_store.load("tags").cards[0].reviews == 0  # nothing graded


def test_review_without_tag_unchanged(deck_store, capsys, monkeypatch):
    assert _review(monkeypatch, "review", "tags", "--no-shuffle") == 0
    assert "card 1/4" in capsys.readouterr().out
