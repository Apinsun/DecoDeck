"""SQLite persistence for review state (FSRS card fields) and review history."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path("local_state.db")


@dataclass
class CardState:
    card_id: str
    deck_id: str
    state: int  # FSRS state: 1=Learning, 2=Review, 3=Relearning
    step: int
    stability: float | None
    difficulty: float | None
    due: datetime
    last_review: datetime | None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def init_db(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and create if needed) the state database."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY,
            deck_id TEXT NOT NULL,
            state INTEGER NOT NULL,
            step INTEGER NOT NULL DEFAULT 0,
            stability REAL,
            difficulty REAL,
            due TEXT NOT NULL,
            last_review TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            rating INTEGER NOT NULL,
            state_after INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def load_state(conn: sqlite3.Connection, card_id: str) -> CardState | None:
    """Return the stored FSRS state for a card, or None if it's new."""
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        return None
    keys = ("card_id", "deck_id", "state", "step", "stability", "difficulty", "due", "last_review")
    data = dict(zip(keys, row))
    return CardState(
        card_id=data["card_id"],
        deck_id=data["deck_id"],
        state=data["state"],
        step=data["step"],
        stability=data["stability"],
        difficulty=data["difficulty"],
        due=_parse_dt(data["due"]),
        last_review=_parse_dt(data["last_review"]),
    )


def save_state(conn: sqlite3.Connection, state: CardState) -> None:
    """Insert or update a card's FSRS state."""
    conn.execute(
        """
        INSERT INTO cards (card_id, deck_id, state, step, stability, difficulty, due, last_review)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id) DO UPDATE SET
            deck_id = excluded.deck_id,
            state = excluded.state,
            step = excluded.step,
            stability = excluded.stability,
            difficulty = excluded.difficulty,
            due = excluded.due,
            last_review = excluded.last_review
        """,
        (
            state.card_id,
            state.deck_id,
            state.state,
            state.step,
            state.stability,
            state.difficulty,
            _iso(state.due),
            _iso(state.last_review),
        ),
    )
    conn.commit()


def log_review(
    conn: sqlite3.Connection,
    card_id: str,
    rating: int,
    state_after: int,
    reviewed_at: datetime,
) -> None:
    """Append a row to the review history."""
    conn.execute(
        "INSERT INTO reviews (card_id, reviewed_at, rating, state_after) VALUES (?, ?, ?, ?)",
        (card_id, _iso(reviewed_at), rating, state_after),
    )
    conn.commit()


def due_card_ids(conn: sqlite3.Connection, deck_id: str, now: datetime) -> set[str]:
    """IDs of stored cards in a deck that are due (due <= now)."""
    rows = conn.execute("SELECT card_id, due FROM cards WHERE deck_id = ?", (deck_id,)).fetchall()
    return {card_id for card_id, due in rows if _parse_dt(due) <= now}
