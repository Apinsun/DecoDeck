"""Unit tests for the FSRS scheduling wrapper."""

from datetime import datetime, timedelta, timezone

from decodeck.scheduler import apply_review

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def test_new_card_good_advances_due():
    state = apply_review("c1", "deck", None, 3, NOW)  # Good
    assert state.card_id == "c1"
    assert state.deck_id == "deck"
    assert state.due > NOW


def test_new_card_again_is_due_immediately():
    state = apply_review("c1", "deck", None, 1, NOW)  # Again
    assert state.due <= NOW + timedelta(minutes=1)


def test_easy_moves_to_review_state():
    state = apply_review("c1", "deck", None, 4, NOW)  # Easy
    assert state.state == 2  # Review


def test_review_is_deterministic():
    a = apply_review("c1", "deck", None, 3, NOW)
    b = apply_review("c1", "deck", None, 3, NOW)
    assert a == b


def test_second_review_extends_interval():
    first = apply_review("c1", "deck", None, 4, NOW)  # Easy -> Review, due +8j
    second = apply_review("c1", "deck", first, 3, first.due)  # Good at due date
    assert second.due > first.due
