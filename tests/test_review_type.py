"""Tests for `fai review --type` (cloze typing mode)."""

import pytest

from flashcards_ai import cli
from flashcards_ai import review as review_mod
from flashcards_ai.importers import from_cloze
from flashcards_ai.models import Card, Deck, Store


@pytest.fixture()
def typed_store(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    cards = from_cloze("The capital of France is {{Paris}}.")
    cards += from_cloze("The GIL prevents {{c1::true parallel execution}} of bytecode.")
    cards.append(Card("plain-q", "plain-a"))  # non-cloze card
    store.save(Deck(name="mixed", cards=cards))
    return store


def _review_typed(monkeypatch, *argv, answers=()):
    """Drive a review session through the given typed answers; return exit code."""
    inputs = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    return cli.main(list(argv))


# --- answer storage at import time ---------------------------------------


def test_importer_stores_plain_cloze_answers():
    cards = from_cloze("The capital of France is {{Paris}}.")
    assert cards[0].cloze_answers == ["Paris"]


def test_importer_stores_numbered_cloze_answers_per_card():
    cards = from_cloze("{{c1::Paris}} is the capital of {{c2::France}}.")
    c1 = next(c for c in cards if "[...] is the capital of France" in c.front)
    c2 = next(c for c in cards if "Paris is the capital of [...]" in c.front)
    assert c1.cloze_answers == ["Paris"]
    assert c2.cloze_answers == ["France"]


def test_importer_answer_excludes_hint():
    cards = from_cloze("The capital of France is {{c1::Paris::country}}.")
    assert cards[0].cloze_answers == ["Paris"]  # hint must not leak into the answer


def test_card_roundtrip_preserves_cloze_answers(tmp_path):
    store = Store(home=tmp_path)
    store.save(Deck(name="d", cards=from_cloze("A {{b}} c.")))
    assert store.load("d").cards[0].cloze_answers == ["b"]


def test_old_cards_without_answers_default_to_empty():
    card = Card.from_dict({"front": "f", "back": "b", "tags": ["cloze"]})
    assert card.cloze_answers == []
    assert not review_mod._is_typeable(card)


# --- normalization / grading (pure, no TTY) ------------------------------


def test_normalize_answer():
    assert review_mod.normalize_answer("  St.  Louis! ") == "st louis"
    assert review_mod.normalize_answer("PARIS") == "paris"


def test_grade_cloze_typed():
    assert review_mod.grade_cloze_typed(["Paris"], ["paris"])
    assert review_mod.grade_cloze_typed(["St. Louis"], ["  st   louis!"])
    assert not review_mod.grade_cloze_typed(["Paris"], ["London"])
    assert not review_mod.grade_cloze_typed(["a", "b"], ["a"])  # arity must match
    assert review_mod.grade_cloze_typed(["red", "blue"], ["RED", "blue "])


# --- typed sessions --------------------------------------------------------


def test_exact_match_counts_as_perfect(typed_store, capsys, monkeypatch):
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "1", answers=("Paris",)) == 0
    out = capsys.readouterr().out
    assert "✓ correct" in out
    card = typed_store.load("mixed").cards[0]
    assert card.reviews == 1 and card.lapses == 0


def test_normalized_match_accepted(typed_store, capsys, monkeypatch):
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "1", answers=("  PARIS. ",)) == 0
    assert "✓ correct" in capsys.readouterr().out


def test_wrong_answer_graded_incorrect_and_revealed(typed_store, capsys, monkeypatch):
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "1", answers=("London",)) == 0
    out = capsys.readouterr().out
    assert "✗ wrong" in out
    assert "The capital of France is Paris." in out  # answer revealed
    card = typed_store.load("mixed").cards[0]
    assert card.reviews == 1 and card.lapses == 1


def test_numbered_cloze_quizzes_only_its_own_number(typed_store, capsys, monkeypatch):
    # card 2 is the c1 card; "true parallel execution" is its only blank
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "1", "--tag", "cloze",
                         answers=("Paris", "true parallel execution")) == 0
    assert "✓ correct" in capsys.readouterr().out


def test_hint_displayed_on_front_in_type_mode(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    store.save(Deck(name="hints", cards=from_cloze("{{c1::Paris::country}} is nice.")))
    assert _review_typed(monkeypatch, "review", "hints", "--type",
                         answers=("Paris",)) == 0
    assert "[country]" in capsys.readouterr().out


def test_multiple_blanks_prompted_in_turn(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    store.save(Deck(name="multi", cards=from_cloze("{{c1::red}} and {{c1::blue}}.")))
    assert _review_typed(monkeypatch, "review", "multi", "--type",
                         answers=("red", "blue")) == 0
    out = capsys.readouterr().out
    assert "Blank 1/2" in out and "Blank 2/2" in out and "✓ correct" in out


def test_any_wrong_blank_fails_the_card(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    store.save(Deck(name="multi", cards=from_cloze("{{c1::red}} and {{c1::blue}}.")))
    assert _review_typed(monkeypatch, "review", "multi", "--type",
                         answers=("red", "green")) == 0
    assert "✗ wrong" in capsys.readouterr().out
    assert store.load("multi").cards[0].lapses == 1


def test_non_cloze_cards_keep_self_grading(typed_store, capsys, monkeypatch):
    # cloze card typed, plain card flipped + self-graded
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "3",
                         answers=("Paris", "true parallel execution", "", "4")) == 0
    out = capsys.readouterr().out
    assert out.count("✓ correct") == 2  # only the two cloze cards were typed
    assert "Session complete: 3 reviewed" in out
    cards = typed_store.load("mixed").cards
    assert all(c.reviews == 1 for c in cards)  # plain card self-graded too


def test_old_cloze_card_without_answers_falls_back_to_self_grade(tmp_path, monkeypatch,
                                                                  capsys):
    monkeypatch.setenv("FLASHCARDS_HOME", str(tmp_path))
    monkeypatch.setattr("flashcards_ai.review.random.shuffle", lambda x: None)
    store = Store()
    # simulate a pre-v1.5.0 card: cloze tag but no stored answers
    store.save(Deck(name="old", cards=[Card("The [...] of France", "The Paris of France",
                                           tags=["cloze"])]))
    assert _review_typed(monkeypatch, "review", "old", "--type",
                         answers=("", "5")) == 0
    out = capsys.readouterr().out
    assert "✓ correct" not in out and "✗ wrong" not in out  # no typed flow
    assert "Session complete: 1 reviewed" in out
    assert store.load("old").cards[0].reviews == 1


def test_quit_in_type_mode_saves_progress(typed_store, capsys, monkeypatch):
    assert _review_typed(monkeypatch, "review", "mixed", "--type", "--no-shuffle",
                         "--limit", "3", answers=("Paris", "q")) == 0
    out = capsys.readouterr().out
    assert "Session paused" in out
    assert typed_store.load("mixed").cards[0].reviews == 1  # first card kept
    assert typed_store.load("mixed").cards[1].reviews == 0  # second never graded


def test_type_flag_off_keeps_classic_flow(typed_store, capsys, monkeypatch):
    inputs = iter(["", "5"])
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    assert cli.main(["review", "mixed", "--no-shuffle", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert "Press Enter to flip" in out
    assert "Type the missing answer" not in out
