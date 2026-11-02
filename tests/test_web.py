"""Smoke tests for the web routes (read-only endpoints, no LLM)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from decodeck import web
from decodeck.storage import CardState, deck_stats, init_db, load_state, log_review, save_state
from decodeck.web import _build_queue, app

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


def test_build_queue_prioritizes_new_over_due(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}, {"id": "b"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    # "a" is due but already seen; "b" is new and comes later in deck order.
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now - timedelta(days=1), now))
    assert _build_queue(deck, "deck", "normal", conn, now) == ["b", "a"]


def test_build_queue_returns_due_when_no_new(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}, {"id": "b"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now + timedelta(days=5), now))
    save_state(conn, CardState("b", "deck", 2, 0, 3.0, 5.0, now - timedelta(days=1), now))
    assert _build_queue(deck, "deck", "normal", conn, now) == ["b"]


def test_build_queue_empty_when_nothing_due(tmp_path):
    conn = init_db(tmp_path / "test.db")
    deck = {"cards": [{"id": "a"}]}
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    save_state(conn, CardState("a", "deck", 2, 0, 3.0, 5.0, now + timedelta(days=5), now))
    assert _build_queue(deck, "deck", "normal", conn, now) == []


def test_cram_missed_shows_only_missed_card(tmp_path, monkeypatch):
    web._sessions.clear()
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
    web._sessions.clear()


def test_hint_page_hides_unmet_criterion_text():
    html = web.templates.env.get_template("hint.html").render(
        deck={"id": "d", "title": "D"},
        card={"id": "c", "question": "Q ?"},
        answer="réponse partielle",
        criteria_pairs=[("critère raté secret", False), ("critère validé", True)],
        missed_count=1,
        hint="un indice",
        cram="",
    )
    assert "critère raté secret" not in html
    assert "critère validé" in html
    assert "1 critère(s) encore manquant(s)" in html


def test_session_next_tracks_progress(tmp_path):
    web._sessions.clear()
    conn = init_db(tmp_path / "test.db")
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    deck = {"cards": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    card, position, total = web._session_next(deck, "d", "normal", conn, now)
    assert card["id"] == "a"
    assert (position, total) == (1, 3)
    web._session_pop("d", "normal", "a")
    card, position, total = web._session_next(deck, "d", "normal", conn, now)
    assert card["id"] == "b"
    assert (position, total) == (2, 3)
    web._sessions.clear()


def test_dont_know_skips_judge_and_grades_again(tmp_path, monkeypatch):
    web._sessions.clear()
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    conn.close()
    monkeypatch.setattr(web, "init_db", lambda: init_db(db_path))

    response = client.post(
        "/deck/python-fundamentals/answer",
        data={"card_id": "python-fundamentals-gil", "answer": "", "dont_know": "true", "cram": ""},
    )
    assert response.status_code == 200
    assert "Again" in response.text
    web._sessions.clear()


def test_reset_page_renders():
    response = client.get("/deck/python-fundamentals/reset")
    assert response.status_code == 200
    assert "Réinitialiser" in response.text


def test_reset_post_clears_deck(tmp_path, monkeypatch):
    web._sessions.clear()
    db_path = tmp_path / "test.db"
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    conn = init_db(db_path)
    save_state(
        conn,
        CardState("python-fundamentals-gil", "python-fundamentals", 2, 0, 3.0, 5.0, now, now),
    )
    log_review(conn, "python-fundamentals-gil", 3, 2, now)
    conn.close()
    monkeypatch.setattr(web, "init_db", lambda: init_db(db_path))

    response = client.post("/deck/python-fundamentals/reset", follow_redirects=False)
    assert response.status_code == 303

    check = init_db(db_path)
    assert load_state(check, "python-fundamentals-gil") is None
    assert deck_stats(check, "python-fundamentals") == {1: 0, 2: 0, 3: 0, 4: 0}
    check.close()
    web._sessions.clear()
