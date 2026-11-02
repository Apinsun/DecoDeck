"""Conversational Q&A about a card, for clarifying a point during review.

Unlike the judge, the chat deliberately runs with thinking enabled (no
``reasoning_effort="none"``), trading latency for answer quality.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from decodeck.config import Config

SYSTEM_PROMPT = """\
Tu es un tuteur pédagogue qui aide à comprendre une notion de révision.
Réponds de façon claire et structurée, avec un petit exemple si pertinent.
Reste factuel : ne fabrique pas d'informations.
"""


def build_context_message(card: dict[str, Any]) -> str:
    """Card content injected as context for every chat turn."""
    parts = [
        f"Question de la carte : {card['question']}",
        f"Réponse de référence : {card['reference_answer']}",
    ]
    if card.get("explanation"):
        parts.append(f"Explication : {card['explanation']}")
    if card.get("source_anchor"):
        parts.append(f"Source : {card['source_anchor']}")
    return "\n\n".join(parts)


def ask_question(
    card: dict[str, Any],
    history: list[dict[str, str]],
    question: str,
    config: Config,
) -> str:
    """Answer ``question`` with the card context and conversation history."""
    client = OpenAI(
        base_url=config.model.base_url,
        api_key=config.model.api_key or "ollama",
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_context_message(card)},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=config.model.model,
        messages=messages,
        temperature=0.3,
        max_tokens=2000,  # thinking tokens count against this budget
    )
    return (response.choices[0].message.content or "").strip()
