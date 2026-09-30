"""Tests for the SM-2 scheduler."""

from datetime import date, timedelta

import pytest

from flashcards_ai.sm2 import Schedule, due_cards, grade, is_due
from flashcards_ai.models import Card


def test_first_pass_intervals():
    today = date(2026, 9, 30)
    s = grade(Schedule(), 5, today)
    assert (s.reps, s.interval, s.due) == (1, 1, today + timedelta(days=1))
    s = grade(s, 4, today)
    assert (s.reps, s.interval) == (2, 6)
    s = grade(s, 5, today)
    assert s.reps == 3 and s.interval == round(6 * s.easiness)


def test_failure_resets_chain_but_keeps_floor():
    today = date(2026, 9, 30)
    s = Schedule(easiness=1.4, interval=30, reps=5)
    s = grade(s, 1, today)
    assert s.reps == 0 and s.interval == 1
    assert s.easiness >= 1.3


def test_easiness_moves_with_quality():
    base = Schedule()
    assert grade(base, 5).easiness > grade(base, 3).easiness > grade(base, 0).easiness


def test_invalid_quality_rejected():
    with pytest.raises(ValueError):
        grade(Schedule(), 6)
    with pytest.raises(ValueError):
        grade(Schedule(), -1)


def test_due_logic():
    today = date(2026, 9, 30)
    new = Card("f", "b")                      # never reviewed -> due
    future = Card("f", "b", schedule=Schedule(due=today + timedelta(days=5)))
    past = Card("f", "b", schedule=Schedule(due=today - timedelta(days=1)))
    assert is_due(new.schedule, today)
    assert not is_due(future.schedule, today)
    assert is_due(past.schedule, today)
    due = due_cards([future, new, past], today)
    assert [c.id for c in due] == [new.id, past.id]  # oldest-due first
