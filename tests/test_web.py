"""Smoke tests for the web routes (read-only endpoints, no LLM)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from decodeck import web
from decodeck.storage import CardState, init_db, log_review, save_state
from decodeck.web import _next_due_card, app

client = TestClient(app)


def test_home_lists_decks():
    response = client.get("/")
    assert response.status_code == 200
    assert "DecoDeck" in response.text


def test_review_page_renders():
    response = client.get("/deck/python-fundamentals")
    assert response.status_code == 200
    # Either a due card (form) or "nothing to review" is acceptable.
    assert ("Votre réponse" in response.text) or ("Rien à réviser" in response.text)


def test_unknown_deck_redirects_home():
    response = client.get("/deck/nope", follow_redirects=False)
    assert response.status_code == 303


def test_next_due_card_prioritizes_new_over_due(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}, {"id": "b"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    # "a" is due but already seen; "b" is new and comes later in deck order.
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now - timedelta(days=1), now))
    assert _next_due_card(deck, conn, now)["id"] == "b"


def test_next_due_card_returns_due_when_no_new(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}, {"id": "b"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now + timedelta(days=5), now))
    save_state(conn, CardState("b", "deck", 2, 0, 3.0, 5.0, now - timedelta(days=1), now))
    assert _next_due_card(deck, conn, now)["id"] == "b"


def test_next_due_card_returns_none_when_nothing_due(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now + timedelta(days=5), now))
    assert _next_due_card(deck, conn, now) is None


def test_cram_missed_shows_only_missed_card(tmp_path, monkeypatch):
    web._cram_sessions.clear()
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    save_state(
        conn,
        CardState("python-fundamentals-gil", "python-fundamentals", 3, 0, 3.0, 5.0, now, now),
    )
    log_review(conn, "python-fundamentals-gil", 1, 3, now)  # missed (Again)
    conn.close()
    # Open a fresh connection inside the request thread (SQLite is thread-bound).
    monkeypatch.setattr(web, "init_db", lambda: init_db(db_path))

    response = client.get("/deck/python-fundamentals?cram=missed")
    assert response.status_code == 200
    assert "GIL" in response.text
    web._cram_sessions.clear()
