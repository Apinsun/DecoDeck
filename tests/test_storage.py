"""Unit tests for the SQLite storage layer."""

from datetime import datetime, timedelta, timezone

from decodeck.storage import (
    CardState,
    deck_stats,
    due_card_ids,
    init_db,
    load_state,
    log_review,
    missed_card_ids,
    save_state,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def test_roundtrip(tmp_path):
    conn = init_db(tmp_path / "test.db")
    state = CardState("c1", "deck", 1, 0, 2.3, 5.0, NOW, None)
    save_state(conn, state)
    assert load_state(conn, "c1") == state


def test_missing_card_returns_none(tmp_path):
    conn = init_db(tmp_path / "test.db")
    assert load_state(conn, "nope") is None


def test_due_card_ids(tmp_path):
    conn = init_db(tmp_path / "test.db")
    past = CardState("due", "deck", 2, 0, 3.0, 5.0, NOW - timedelta(days=1), NOW)
    future = CardState("later", "deck", 2, 0, 3.0, 5.0, NOW + timedelta(days=5), NOW)
    other_deck = CardState("other", "otherdeck", 2, 0, 3.0, 5.0, NOW - timedelta(days=1), NOW)
    save_state(conn, past)
    save_state(conn, future)
    save_state(conn, other_deck)
    assert due_card_ids(conn, "deck", NOW) == {"due"}


def test_save_state_updates_existing(tmp_path):
    conn = init_db(tmp_path / "test.db")
    state = CardState("c1", "deck", 1, 0, 2.3, 5.0, NOW, None)
    save_state(conn, state)
    updated = CardState("c1", "deck", 2, 1, 4.0, 6.0, NOW + timedelta(days=3), NOW)
    save_state(conn, updated)
    assert load_state(conn, "c1") == updated


def test_deck_stats_counts_ratings(tmp_path):
    conn = init_db(tmp_path / "test.db")
    save_state(conn, CardState("c1", "deck", 2, 0, 3.0, 5.0, NOW, NOW))
    save_state(conn, CardState("c2", "deck", 2, 0, 3.0, 5.0, NOW, NOW))
    save_state(conn, CardState("c3", "otherdeck", 2, 0, 3.0, 5.0, NOW, NOW))
    log_review(conn, "c1", 3, 2, NOW)
    log_review(conn, "c2", 1, 1, NOW)
    log_review(conn, "c2", 2, 1, NOW)
    log_review(conn, "c3", 4, 2, NOW)  # other deck, excluded
    assert deck_stats(conn, "deck") == {1: 1, 2: 1, 3: 1, 4: 0}


def test_missed_card_ids_uses_last_review(tmp_path):
    conn = init_db(tmp_path / "test.db")
    save_state(conn, CardState("c1", "deck", 3, 0, 3.0, 5.0, NOW, NOW))
    save_state(conn, CardState("c2", "deck", 1, 0, 3.0, 5.0, NOW, NOW))
    save_state(conn, CardState("c3", "deck", 2, 0, 3.0, 5.0, NOW, NOW))
    log_review(conn, "c1", 1, 3, NOW)  # missed (Again)
    log_review(conn, "c2", 2, 1, NOW)  # missed (Hard)
    log_review(conn, "c3", 3, 2, NOW)  # ok (Good)
    assert missed_card_ids(conn, "deck") == {"c1", "c2"}
    # A later Good review clears the miss.
    log_review(conn, "c1", 3, 2, NOW + timedelta(minutes=1))
    assert missed_card_ids(conn, "deck") == {"c2"}
