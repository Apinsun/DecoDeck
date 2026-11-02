"""Unit tests for the chat context builder (no LLM involved)."""

from decodeck.chat import build_context_message


def test_build_context_message_includes_card_fields():
    card = {
        "question": "Q ?",
        "reference_answer": "R.",
        "explanation": "E.",
        "source_anchor": "f.py:L1",
    }
    text = build_context_message(card)
    assert "Q ?" in text
    assert "R." in text
    assert "E." in text
    assert "f.py:L1" in text


def test_build_context_message_without_optionals():
    card = {"question": "Q ?", "reference_answer": "R."}
    text = build_context_message(card)
    assert "Explication" not in text
    assert "Source" not in text
