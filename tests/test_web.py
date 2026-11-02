"""Smoke tests for the web routes (read-only endpoints, no LLM)."""

from fastapi.testclient import TestClient

from decodeck.web import app

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
