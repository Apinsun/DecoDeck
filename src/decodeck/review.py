"""Interactive review loop (CLI) for DecoDeck."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from decodeck.config import load_config
from decodeck.judge import cap_grade_after_hint, generate_hint, judge_card
from decodeck.scheduler import apply_review
from decodeck.storage import init_db, load_state, log_review, save_state

RATING_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


def _is_due(conn, card_id: str, now: datetime) -> bool:
    state = load_state(conn, card_id)
    if state is None:
        return True  # nouvelle carte
    return state.due <= now


def _manual_grade() -> int:
    while True:
        raw = input("  Note manuelle (1=Again, 2=Hard, 3=Good, 4=Easy) : ").strip()
        if raw in {"1", "2", "3", "4"}:
            return int(raw)
        print("  Entre 1, 2, 3 ou 4.")


def run_review(deck_path: Path, limit: int | None = None) -> int:
    """Run the review loop over the due cards of a deck."""
    deck = yaml.safe_load(deck_path.read_text(encoding="utf-8"))
    config = load_config()
    conn = init_db()
    now = datetime.now(timezone.utc)
    deck_id = deck["id"]

    due = [card for card in deck["cards"] if _is_due(conn, card["id"], now)]
    if limit is not None:
        due = due[:limit]

    if not due:
        print("Aucune carte à réviser pour le moment.")
        return 0

    print(f"{len(due)} carte(s) à réviser.\n")
    reviewed = 0
    for i, card in enumerate(due, 1):
        card_id = card["id"]
        print(f"[{i}/{len(due)}] {card['question']}")
        answer = input("Votre réponse : ").strip()
        if answer.lower() in {"q", "quit", "exit"}:
            break
        if not answer:
            answer = "Je ne sais pas."

        try:
            verdict = judge_card(
                card["question"],
                card["reference_answer"],
                card["grading_rubric"],
                answer,
                config,
            )
            grade = verdict.grade
            print(f"  Note : {RATING_NAMES[grade]} ({grade}) — critères {verdict.met_criteria}")
            print(f"  {verdict.explanation}")

            if grade == 2:
                try:
                    hint = generate_hint(
                        card["question"],
                        card["reference_answer"],
                        card["grading_rubric"],
                        verdict.met_criteria,
                        answer,
                        config,
                    )
                    print(f"  Réponse partielle. Indice : {hint}")
                    second = input("  Nouvelle réponse : ").strip()
                    if second:
                        verdict2 = judge_card(
                            card["question"],
                            card["reference_answer"],
                            card["grading_rubric"],
                            second,
                            config,
                        )
                        grade = cap_grade_after_hint(verdict2.grade)
                        print(
                            f"  Après indice : {RATING_NAMES[grade]} ({grade}) "
                            f"— critères {verdict2.met_criteria}"
                        )
                        print(f"  {verdict2.explanation}")
                except Exception as exc:
                    print(f"  [indice en échec : {exc}]")
        except Exception as exc:
            print(f"  [juge en échec : {exc}]")
            grade = _manual_grade()

        state = load_state(conn, card_id)
        new_state = apply_review(card_id, deck_id, state, grade, now)
        save_state(conn, new_state)
        log_review(conn, card_id, grade, new_state.state, now)

        print(f"  Prochaine révision : {new_state.due:%Y-%m-%d}")
        print(f"  Référence : {card['reference_answer']}")
        if card.get("source_anchor"):
            print(f"  Source : {card['source_anchor']}")
        if card.get("explanation"):
            print(f"  Explication : {card['explanation']}")
        print()
        reviewed += 1

    print(f"{reviewed} carte(s) révisée(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``deck-review <deck.yaml> [--limit N]``."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage : deck-review <deck.yaml> [--limit N]", file=sys.stderr)
        return 2

    deck_path = Path(args[0])
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    return run_review(deck_path, limit)


if __name__ == "__main__":
    raise SystemExit(main())
