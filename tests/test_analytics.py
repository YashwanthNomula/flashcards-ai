"""Tests for `fai analytics` — retention curves, forgetting-curve estimates."""

import json
from datetime import date, timedelta

from flashcards_ai import cli
from flashcards_ai import analytics as analytics_mod
from flashcards_ai import streaks as streaks_mod
from flashcards_ai.models import Card, Deck, Store
from flashcards_ai.sm2 import Schedule

TODAY = date(2026, 10, 18)


def _store_at(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    return Store()


def _session(store, deck, reviewed, remembered=None, days_ago=0):
    streaks_mod.log_session(store, deck, reviewed,
                            day=TODAY - timedelta(days=days_ago),
                            remembered=remembered)


# --- session logging carries recall counts ---------------------------------


def test_log_session_records_remembered(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    streaks_mod.log_session(store, "geo", 10, remembered=7)
    (record,) = streaks_mod.read_sessions(store)
    assert record["reviewed"] == 10
    assert record["remembered"] == 7


def test_legacy_sessions_without_remembered_parse_as_none(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    streaks_mod.log_session(store, "geo", 10)  # no recall count, like pre-v1.6.0
    (record,) = streaks_mod.read_sessions(store)
    assert record["remembered"] is None


def test_review_session_logs_remembered_count(tmp_path, monkeypatch, capsys):
    store = _store_at(tmp_path, monkeypatch)
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store.save(Deck(name="geo", cards=[Card("a", "b"), Card("c", "d")]))
    inputs = iter(["", "5", "", "2"])  # flip, grade 5; flip, grade 2
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    assert cli.main(["review", "geo", "--no-shuffle"]) == 0
    (record,) = streaks_mod.read_sessions(store)
    assert record["reviewed"] == 2
    assert record["remembered"] == 1  # only the 5 counts as recalled


def test_quit_session_logs_remembered_for_graded_cards(tmp_path, monkeypatch, capsys):
    store = _store_at(tmp_path, monkeypatch)
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store.save(Deck(name="geo", cards=[Card("a", "b"), Card("c", "d")]))
    inputs = iter(["", "4", "", "q"])  # grade first card 4, quit on second
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    assert cli.main(["review", "geo", "--no-shuffle"]) == 0
    (record,) = streaks_mod.read_sessions(store)
    assert record["reviewed"] == 1 and record["remembered"] == 1


# --- retention curve -------------------------------------------------------


def test_retention_curve_daily_aggregation(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 10, remembered=8, days_ago=2)
    _session(store, "geo", 6, remembered=3, days_ago=2)  # same day aggregates
    _session(store, "geo", 4, remembered=4, days_ago=1)
    curve = analytics_mod.retention_curve(
        streaks_mod.read_sessions(store), deck="geo", days=7, today=TODAY)
    assert [p["date"] for p in curve] == [
        (TODAY - timedelta(days=2)).isoformat(),
        (TODAY - timedelta(days=1)).isoformat(),
    ]
    assert curve[0]["reviewed"] == 16
    assert curve[0]["retention"] == 11 / 16
    assert curve[1]["retention"] == 1.0


def test_retention_curve_legacy_sessions_show_n_a(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 5, days_ago=1)  # legacy: no recall data
    (point,) = analytics_mod.retention_curve(
        streaks_mod.read_sessions(store), days=7, today=TODAY)
    assert point["retention"] is None
    assert point["remembered"] is None
    assert point["reviewed"] == 5


def test_retention_curve_filters_by_deck(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 10, remembered=8, days_ago=1)
    _session(store, "spanish", 10, remembered=2, days_ago=1)
    curve = analytics_mod.retention_curve(
        streaks_mod.read_sessions(store), deck="spanish", days=7, today=TODAY)
    assert [p["retention"] for p in curve] == [0.2]


def test_retention_curve_ignores_days_outside_window(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 10, remembered=10, days_ago=30)
    assert analytics_mod.retention_curve(
        streaks_mod.read_sessions(store), days=14, today=TODAY) == []


# --- forgetting curve ------------------------------------------------------


def _card(days_since: int, interval: int, reviews: int, lapses: int) -> Card:
    last = TODAY - timedelta(days=days_since)
    due = last + timedelta(days=interval)
    return Card("f", "b", reviews=reviews, lapses=lapses,
                schedule=Schedule(interval=interval, reps=3, due=due))


def test_forgetting_curve_buckets_days_since_review():
    deck = Deck(name="geo", cards=[
        _card(1, 10, 10, 1),    # 0–2d bucket, 90% measured
        _card(5, 10, 8, 4),     # 3–6d bucket, 50% measured
        _card(20, 20, 6, 6),    # 14–29d bucket, 0% measured
    ])
    curve = {b["bucket"]: b for b in analytics_mod.forgetting_curve(deck, today=TODAY)}
    assert curve["0–2d"]["cards"] == 1 and curve["0–2d"]["measured"] == 0.9
    assert curve["3–6d"]["cards"] == 1 and curve["3–6d"]["measured"] == 0.5
    assert curve["14–29d"]["cards"] == 1 and curve["14–29d"]["measured"] == 0.0
    assert curve["7–13d"]["cards"] == 0 and curve["7–13d"]["measured"] is None


def test_forgetting_curve_sm2_expected_assumes_90_percent_at_due():
    # at exactly the due date, SM-2 expectation should be 0.9
    deck = Deck(name="geo", cards=[_card(10, 10, 10, 2)])
    curve = {b["bucket"]: b for b in analytics_mod.forgetting_curve(deck, today=TODAY)}
    assert curve["7–13d"]["sm2_expected"] == 0.9


def test_forgetting_curve_skips_new_and_unscheduled_cards():
    deck = Deck(name="geo", cards=[
        Card("new", "b"),  # never reviewed
        _card(1, 10, 5, 0),
    ])
    total = sum(b["cards"] for b in analytics_mod.forgetting_curve(deck, today=TODAY))
    assert total == 1


def test_forgetting_curve_per_deck_not_mixed(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    store.save(Deck(name="geo", cards=[_card(1, 10, 10, 1)]))
    store.save(Deck(name="spanish", cards=[_card(1, 10, 10, 5)]))
    data = analytics_mod.analyze(store, today=TODAY)
    geo = {b["bucket"]: b for b in data["forgetting_curve"]["geo"]}
    spa = {b["bucket"]: b for b in data["forgetting_curve"]["spanish"]}
    assert geo["0–2d"]["measured"] == 0.9
    assert spa["0–2d"]["measured"] == 0.5


# --- report / CLI ----------------------------------------------------------


def test_analytics_empty_store_is_not_an_error(tmp_path, monkeypatch, capsys):
    store = _store_at(tmp_path, monkeypatch)
    data = analytics_mod.show(store, today=TODAY)
    out = capsys.readouterr().out
    assert "Analytics" in out and "no session data yet" in out
    assert data["retention_curve"] == []


def test_analytics_json_output_is_valid_json(tmp_path, monkeypatch, capsys):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 10, remembered=8, days_ago=1)
    store.save(Deck(name="geo", cards=[_card(1, 10, 10, 1)]))
    assert cli.main(["analytics", "--deck", "geo", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["deck"] == "geo"
    assert data["overall"]["total_reviews"] == 10
    assert data["retention_curve"][0]["retention"] == 0.8
    assert "geo" in data["forgetting_curve"]


def test_analytics_text_report_includes_legacy_n_a_note(tmp_path, monkeypatch, capsys):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 5, days_ago=1)  # legacy log
    assert cli.main(["analytics", "--days", "7"]) == 0
    out = capsys.readouterr().out
    assert "retention curve" in out
    assert "forgetting curve" in out
    assert "n/a" in out


def test_analytics_deck_filter_limits_overall_stats(tmp_path, monkeypatch):
    store = _store_at(tmp_path, monkeypatch)
    _session(store, "geo", 10, remembered=8, days_ago=1)
    _session(store, "spanish", 4, remembered=1, days_ago=1)
    data = analytics_mod.analyze(store, deck="spanish", today=TODAY)
    assert data["overall"]["total_reviews"] == 4
    assert data["retention_curve"][0]["retention"] == 0.25
