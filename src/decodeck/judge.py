"""LLM-as-a-judge: grade a user answer against a card's grading rubric.

The model only returns which rubric criteria are met; the FSRS grade is derived
deterministically from that, so grading stays auditable (a requirement for the
calibration benchmark).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from decodeck.config import Config

SYSTEM_PROMPT = """\
Tu es un évaluateur impartial de réponses à des flashcards.

On te donne : la question, la réponse de référence, une grille de critères,
et la réponse de l'utilisateur.

Pour chaque critère de la grille, détermine si la réponse de l'utilisateur le
satisfait. Un critère est satisfait si l'idée est présente, même reformulée —
il n'est PAS nécessaire d'utiliser les mots exacts. Sois strict : une idée
absente, vague ou fausse ne valide pas le critère.

Réponds UNIQUEMENT en JSON, avec ce format exact :
{"met_criteria": [true, false, ...], "explanation": "..."}

- met_criteria : un booléen par critère, dans l'ordre de la grille.
- explanation : une phrase courte justifiant l'évaluation.
"""


@dataclass(frozen=True)
class Verdict:
    met_criteria: list[bool]
    explanation: str
    grade: int  # FSRS rating: 1=Again, 2=Hard, 3=Good, 4=Easy


def grade_from_criteria(met: list[bool]) -> int:
    """Map rubric results to an FSRS rating.

    - no criterion met -> Again (1)
    - at least one met -> Hard (2)
    - all criteria met -> Good (3)

    Easy (4) is intentionally not emitted yet.
    """
    if not any(met):
        return 1
    if all(met):
        return 3
    return 2


def _parse_json(text: str) -> dict:
    """Parse model output leniently (models often wrap JSON in prose)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"réponse non-JSON du modèle : {text!r}")
        return json.loads(match.group(0))


def parse_verdict(data: dict, n_criteria: int) -> tuple[list[bool], str]:
    """Validate and extract a model verdict from parsed JSON."""
    raw = data.get("met_criteria")
    if not isinstance(raw, list):
        raise ValueError(f"met_criteria inattendu (attendu une liste, reçu {raw!r})")
    if len(raw) != n_criteria:
        raise ValueError(f"met_criteria a {len(raw)} éléments, attendu {n_criteria}")
    return [bool(x) for x in raw], str(data.get("explanation", ""))


MAX_RETRIES = 2  # nombre de nouvelles tentatives après le premier essai


def _format_guidance(n_criteria: int, bad_output: str) -> str:
    """Instruction renvoyée au modèle après une sortie malformée."""
    return (
        "Ta réponse précédente ne respecte pas le format demandé.\n\n"
        f"Réponse reçue : {bad_output}\n\n"
        "Corrige-la : réponds UNIQUEMENT avec un objet JSON valide, sans texte "
        "autour, au format exact {\"met_criteria\": [true, false, ...], "
        "\"explanation\": \"...\"}. met_criteria doit être une LISTE de "
        f"{n_criteria} booléens (un par critère, dans l'ordre)."
    )


def judge_card(
    question: str,
    reference_answer: str,
    rubric: list[str],
    user_answer: str,
    config: Config,
    max_retries: int = MAX_RETRIES,
) -> Verdict:
    """Grade ``user_answer`` against ``rubric`` and return a verdict."""
    client = OpenAI(
        base_url=config.model.base_url,
        api_key=config.model.api_key or "ollama",
    )

    user_prompt = (
        f"Question : {question}\n\n"
        f"Réponse de référence : {reference_answer}\n\n"
        f"Grille de critères :\n"
        + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(rubric))
        + f"\n\nRéponse de l'utilisateur : {user_answer}\n"
    )

    kwargs: dict[str, Any] = {}
    if config.model.thinking is False:
        kwargs["reasoning_effort"] = "none"  # désactive le "thinking" (Ollama /v1)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for _attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=config.model.model,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = response.choices[0].message.content or ""
        try:
            data = _parse_json(raw)
            met, explanation = parse_verdict(data, len(rubric))
            return Verdict(
                met_criteria=met,
                explanation=explanation,
                grade=grade_from_criteria(met),
            )
        except ValueError as exc:  # JSON invalide ou forme inattendue
            last_error = exc
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {"role": "user", "content": _format_guidance(len(rubric), raw)}
            )

    raise ValueError(f"juge en échec après {max_retries + 1} tentatives : {last_error}")
