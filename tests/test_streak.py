"""Tests for streak tracking and daily reminders (`fai streak`, `fai remind`)."""

from datetime import date, timedelta

import pytest

from flashcards_ai import cli
from flashcards_ai import streaks
from flashcards_ai.models import Card, Deck, Store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    return Store()


def _log(store, day, deck, reviewed):
    streaks.log_session(store, deck, reviewed, day=day)


def _days_ago(n):
    return date.today() - timedelta(days=n)


def _sessions_for(*pairs):
    """pairs: (days_ago, reviewed, deck) -> list of raw session dicts."""
    return [{"date": (date.today() - timedelta(days=ago)).isoformat(),
             "deck": deck, "reviewed": reviewed}
            for ago, reviewed, deck in pairs]


# ---- streak math ----

def test_empty_log_gives_zeros():
    info = streaks.summarize([])
    assert info == {"current": 0, "longest": 0, "total_reviews": 0,
                    "today": 0, "active_days": 0}


def test_review_today_counts():
    info = streaks.summarize(_sessions_for((0, 5, "d")))
    assert info["current"] == 1
    assert info["longest"] == 1
    assert info["today"] == 5
    assert info["total_reviews"] == 5


def test_streak_ending_yesterday_still_counts():
    info = streaks.summarize(_sessions_for((1, 3, "d"), (2, 2, "d")))
    assert info["current"] == 2
    assert info["today"] == 0


def test_gap_day_resets_current_but_not_longest():
    info = streaks.summarize(_sessions_for((0, 1, "d"), (2, 1, "d"), (3, 1, "d")))
    assert info["current"] == 1          # gap yesterday breaks the run
    assert info["longest"] == 2          # two-day run still remembered
    assert info["active_days"] == 3


def test_longest_beats_current():
    info = streaks.summarize(
        _sessions_for((0, 1, "d"), (5, 1, "d"), (6, 1, "d"), (7, 1, "d")))
    assert info["current"] == 1
    assert info["longest"] == 3


def test_zero_review_days_are_ignored():
    sessions = _sessions_for((0, 4, "d"), (1, 0, "d"))
    info = streaks.summarize(sessions)
    assert info["current"] == 1
    assert info["active_days"] == 1


def test_multiple_sessions_same_day_merge():
    sessions = _sessions_for((0, 2, "a"), (0, 3, "b"), (1, 1, "a"))
    info = streaks.summarize(sessions)
    assert info["today"] == 5
    assert info["current"] == 2
    assert info["total_reviews"] == 6


def test_deck_filter():
    sessions = _sessions_for((0, 5, "vocab"), (0, 5, "python"),
                             (1, 5, "vocab"))
    info = streaks.summarize(sessions, deck="vocab")
    assert info["current"] == 2
    assert info["total_reviews"] == 10
    only_python = streaks.summarize(sessions, deck="python")
    assert only_python["current"] == 1
    assert streaks.summarize(sessions, deck="nope")["current"] == 0


# ---- session log behavior ----

def test_log_session_writes_record(store):
    _log(store, _days_ago(0), "vocab", 7)
    sessions = streaks.read_sessions(store)
    assert sessions == [{"date": date.today().isoformat(),
                         "deck": "vocab", "reviewed": 7, "remembered": None}]


def test_log_session_skips_zero_reviews(store):
    streaks.log_session(store, "vocab", 0)
    assert streaks.read_sessions(store) == []


def test_read_sessions_tolerates_missing_and_corrupt(store):
    assert streaks.read_sessions(store) == []
    (streaks.sessions_path(store)).write_text("not json {{{", encoding="utf-8")
    assert streaks.read_sessions(store) == []


def test_session_log_is_not_a_deck(store):
    _log(store, _days_ago(0), "vocab", 3)
    store.save(Deck(name="vocab", cards=[]))
    assert store.deck_names() == ["vocab"]


def _review(monkeypatch, *argv, grades=("5",)):
    sequence = []
    for g in grades:
        sequence += ["", g]
    inputs = iter(sequence)
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    return cli.main(list(argv))


def test_review_logs_session_and_nudge(store, capsys, monkeypatch):
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store.save(Deck(name="d", cards=[Card("q", "a")]))
    # Yesterday's streak should trigger the nudge at session start.
    _log(store, _days_ago(1), "d", 2)
    assert _review(monkeypatch, "review", "d", "--no-shuffle") == 0
    out = capsys.readouterr().out
    assert "1-day streak on the line" in out
    sessions = streaks.read_sessions(store)
    assert any(s["date"] == date.today().isoformat() and s["reviewed"] == 1
               for s in sessions)


def test_review_quit_midway_logs_partial(store, capsys, monkeypatch):
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store.save(Deck(name="d", cards=[Card("q1", "a1"), Card("q2", "a2")]))
    # Grade one card, then quit on the next.
    sequence = iter(["", "4", "", "q"])
    monkeypatch.setattr("builtins.input", lambda _="": next(sequence))
    assert cli.main(["review", "d", "--no-shuffle"]) == 0
    sessions = streaks.read_sessions(store)
    assert sessions[-1]["reviewed"] == 1


# ---- CLI: streak + remind ----

def test_cli_streak_output(store, capsys):
    _log(store, _days_ago(0), "d", 5)
    _log(store, _days_ago(1), "d", 5)
    _log(store, _days_ago(2), "d", 5)
    assert cli.main(["streak"]) == 0
    out = capsys.readouterr().out
    assert "current:  3 days" in out
    assert "longest: 3" in out
    assert "total reviews: 15" in out
    assert "reviewed today: 5" in out
    assert "🔥" in out


def test_cli_streak_empty(store, capsys):
    assert cli.main(["streak"]) == 0
    out = capsys.readouterr().out
    assert "current:  0 days" in out
    assert "start one" in out


def test_cli_streak_deck_filter(store, capsys):
    _log(store, _days_ago(0), "a", 2)
    _log(store, _days_ago(0), "b", 9)
    assert cli.main(["streak", "--deck", "b"]) == 0
    assert "total reviews: 9" in capsys.readouterr().out


def test_cli_remind_before_review(store, capsys):
    _log(store, _days_ago(1), "d", 3)  # active streak, nothing today
    store.save(Deck(name="d", cards=[Card("q", "a")]))
    assert cli.main(["remind"]) == 0
    out = capsys.readouterr().out
    assert "streak on the line" in out
    assert "1 due" in out


def test_cli_remind_after_review(store, capsys):
    _log(store, _days_ago(0), "d", 3)
    assert cli.main(["remind"]) == 0
    out = capsys.readouterr().out
    assert "Reviewed 3 today" in out


def test_cli_remind_no_history(store, capsys):
    store.save(Deck(name="d", cards=[Card("q", "a")]))
    assert cli.main(["remind"]) == 0
    assert "start a streak" in capsys.readouterr().out


def test_sync_export_does_not_leak_sessions(store, capsys, tmp_path):
    from flashcards_ai import sync as sync_mod
    _log(store, _days_ago(0), "secret-deck", 42)
    store.save(Deck(name="secret-deck", cards=[Card("q", "a", tags=["t"])]))
    out_file = tmp_path / "deck.md"
    assert cli.main(["sync", "export", "secret-deck", str(out_file)]) == 0
    md = out_file.read_text(encoding="utf-8")
    assert "42" not in md
    assert "_sessions" not in md
    assert sync_mod.deck_from_markdown(md, "x").cards[0].front == "q"
