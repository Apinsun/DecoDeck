"""Tests for deck validation."""

from decodeck.deck_lint import validate_deck


def make_card(**overrides):
    card = {
        "id": "deck-card-1",
        "question": "Qu'est-ce qu'un test ?",
        "reference_answer": "Une vérification automatisée.",
        "grading_rubric": ["critère 1", "critère 2"],
    }
    card.update(overrides)
    return card


def make_deck(cards=None):
    return {"id": "deck", "title": "Deck", "cards": cards or [make_card()]}


def test_valid_deck_has_no_issues():
    assert validate_deck(make_deck()) == []


def test_missing_cards_field():
    issues = validate_deck({"id": "deck", "title": "Deck"})
    assert any(i.severity == "error" and i.location == "cards" for i in issues)


def test_duplicate_card_id():
    issues = validate_deck(make_deck([make_card(), make_card()]))
    assert any("dupliqué" in i.message for i in issues)


def test_rubric_out_of_range():
    for n in (1, 4):
        deck = make_deck([make_card(grading_rubric=[f"c{i}" for i in range(n)])])
        issues = validate_deck(deck)
        assert any("critères" in i.message for i in issues)


def test_invalid_slug():
    issues = validate_deck(make_deck([make_card(id="Not Valid!")]))
    assert any("format invalide" in i.message for i in issues)


def test_missing_anchor_file(tmp_path):
    card = make_card(source_anchor="nope.py:L10-20")
    issues = validate_deck(make_deck([card]), base_dir=tmp_path)
    assert any("fichier introuvable" in i.message for i in issues)


def test_existing_anchor_file(tmp_path):
    (tmp_path / "real.py").write_text("x = 1\n" * 30)
    card = make_card(source_anchor="real.py:L10-20")
    issues = validate_deck(make_deck([card]), base_dir=tmp_path)
    assert not any("fichier introuvable" in i.message for i in issues)


def test_url_anchor_is_a_warning(tmp_path):
    card = make_card(source_anchor="https://docs.python.org/3/glossary.html")
    issues = validate_deck(make_deck([card]), base_dir=tmp_path)
    assert any(i.severity == "warning" and "non vérifiable" in i.message for i in issues)
