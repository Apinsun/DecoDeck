"""FSRS scheduling wrapper.

The ``fsrs`` package computes the next state (stability, difficulty, due date)
from the current state and a rating. This module bridges our ``CardState``
(identity + FSRS fields) with the ``fsrs.Card`` object.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler, State

from decodeck.storage import CardState

_scheduler = Scheduler()


def _to_fsrs_card(state: CardState | None) -> Card:
    """Build an fsrs.Card from our stored state (a fresh card if None)."""
    if state is None:
        return Card()
    return Card(
        state=State(state.state),
        step=state.step,
        stability=state.stability,
        difficulty=state.difficulty,
        due=state.due,
        last_review=state.last_review,
    )


def apply_review(
    card_id: str,
    deck_id: str,
    state: CardState | None,
    rating: int,
    now: datetime | None = None,
) -> CardState:
    """Apply a rating (1..4) and return the card's next FSRS state."""
    now = now or datetime.now(timezone.utc)
    card = _to_fsrs_card(state)
    new_card, _review_log = _scheduler.review_card(card, Rating(rating), now)
    return CardState(
        card_id=card_id,
        deck_id=deck_id,
        state=int(new_card.state),
        step=new_card.step or 0,
        stability=new_card.stability,
        difficulty=new_card.difficulty,
        due=new_card.due,
        last_review=new_card.last_review,
    )
