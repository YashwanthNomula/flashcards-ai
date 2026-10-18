"""Tests for interactive cloze masking (fai add --cloze)."""

import pytest

from flashcards_ai.cloze_add import (
    cloze_cards_from_words,
    mask_words,
    numbered_words,
    parse_mask_groups,
    parse_selection,
    tokenize,
)


def test_tokenize_splits_whitespace():
    assert tokenize("The  quick brown") == ["The", "quick", "brown"]
    assert tokenize("") == []


def test_parse_selection_single():
    assert parse_selection("2", 5) == [1]


def test_parse_selection_list_and_range_flat():
    assert parse_selection("1,4", 5) == [0, 3]
    assert parse_selection("1-3", 5) == [0, 1, 2]
    assert parse_selection("1,3-5", 5) == [0, 2, 3, 4]


def test_parse_mask_groups_range_is_one_phrase():
    assert parse_mask_groups("2,4-5", 8) == [[1], [3, 4]]


def test_parse_selection_dedupes_keeps_order():
    assert parse_selection("2,1,2", 5) == [1, 0]


def test_parse_selection_rejects_bad_input():
    with pytest.raises(ValueError):
        parse_selection("", 5)
    with pytest.raises(ValueError):
        parse_selection("abc", 5)
    with pytest.raises(ValueError):
        parse_selection("0", 5)
    with pytest.raises(ValueError):
        parse_selection("6", 5)  # out of range
    with pytest.raises(ValueError):
        parse_selection("3-2", 5)  # reversed range


def test_mask_words_range_is_single_phrase():
    masked = mask_words("The GIL prevents true parallel execution", [[1], [3, 4]])
    assert masked == "The {{c1::GIL}} prevents {{c2::true parallel}} execution"


def test_cloze_cards_from_words_one_card_per_mask():
    cards = cloze_cards_from_words("The GIL prevents true parallel execution",
                                   [[1], [3, 4]])
    assert len(cards) == 2
    # first card masks only "GIL", reveals the phrase as plain text
    assert cards[0].front == "The [...] prevents true parallel execution"
    assert "GIL" in cards[0].back
    assert cards[1].front == "The GIL prevents [...] execution"
    assert "true parallel" in cards[1].back
    assert "cloze" in cards[0].tags


def test_cloze_cards_from_words_custom_tags():
    cards = cloze_cards_from_words("a b c", [[0]], tags=["vocab"])
    assert cards[0].tags == ["vocab", "cloze"]


def test_cloze_cards_from_words_requires_selection():
    with pytest.raises(ValueError):
        cloze_cards_from_words("a b c", [])


def test_numbered_words_format():
    out = numbered_words("a b")
    assert "1: a" in out and "2: b" in out


# ------------------------------------------------------------------ CLI ----

from flashcards_ai import cli  # noqa: E402


class _FakeStore:
    def __init__(self):
        self.decks = {}

    def load(self, name):
        from flashcards_ai.models import Deck
        return self.decks.setdefault(name, Deck(name=name))

    def save(self, deck):
        self.decks[deck.name] = deck


def test_cmd_add_cloze_noninteractive(monkeypatch, capsys):
    store = _FakeStore()
    monkeypatch.setattr(cli, "_store", lambda: store)
    rc = cli.main(["add", "d", "--cloze",
                   "--text", "The GIL prevents true parallel execution",
                   "--mask", "2,4-5"])
    assert rc == 0
    cards = store.decks["d"].cards
    assert len(cards) == 2
    assert cards[0].front == "The [...] prevents true parallel execution"
    assert cards[1].front == "The GIL prevents [...] execution"
    out = capsys.readouterr().out
    assert "2 cloze card(s)" in out


def test_cmd_add_cloze_bad_mask(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_store", _FakeStore)
    rc = cli.main(["add", "d", "--cloze", "--text", "The quick brown fox", "--mask", "9"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "out of range" in err


def test_cmd_add_cloze_interactive(monkeypatch, capsys):
    store = _FakeStore()
    monkeypatch.setattr(cli, "_store", lambda: store)
    monkeypatch.setattr("builtins.input", lambda _="": "3")
    rc = cli.main(["add", "d", "--cloze", "--text", "The quick brown fox"])
    assert rc == 0
    assert len(store.decks["d"].cards) == 1
    assert store.decks["d"].cards[0].front == "The quick [...] fox"


def test_plain_add_still_works(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(cli, "_store", lambda: store)
    rc = cli.main(["add", "d", "--front", "f", "--back", "b"])
    assert rc == 0
    assert store.decks["d"].cards[0].front == "f"
