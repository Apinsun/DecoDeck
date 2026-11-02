"""Web UI (FastAPI) for DecoDeck.

Thin frontend over the existing engine: it serves decks, shows the next due
card, and posts answers through the judge + FSRS + SQLite pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from decodeck.config import load_config
from decodeck.judge import judge_card
from decodeck.scheduler import apply_review
from decodeck.storage import init_db, load_state, log_review, save_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DECKS_DIR = BASE_DIR / "decks"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="DecoDeck")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

RATING_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


def _list_decks() -> list[dict]:
    decks = []
    for path in sorted(DECKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        decks.append({"id": data["id"], "title": data["title"], "count": len(data["cards"])})
    return decks


def _load_deck(deck_id: str) -> dict | None:
    for path in DECKS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data["id"] == deck_id:
            return data
    return None


def _next_due_card(deck: dict, conn, now: datetime) -> dict | None:
    """First card of the deck that is new or due."""
    for card in deck["cards"]:
        state = load_state(conn, card["id"])
        if state is None or state.due <= now:
            return card
    return None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"decks": _list_decks()})


@app.get("/deck/{deck_id}", response_class=HTMLResponse)
def review(request: Request, deck_id: str):
    deck = _load_deck(deck_id)
    if deck is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    card = _next_due_card(deck, conn, now)
    return templates.TemplateResponse(request, "review.html", {"deck": deck, "card": card})


@app.post("/deck/{deck_id}/answer", response_class=HTMLResponse)
def answer(
    request: Request,
    deck_id: str,
    card_id: str = Form(...),
    answer: str = Form(...),
):
    deck = _load_deck(deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if deck is None or card is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    answer = answer.strip() or "Je ne sais pas."

    grade = None
    criteria_pairs: list[tuple[str, bool]] = []
    judge_explanation = None
    judge_error = None
    next_due = None

    try:
        verdict = judge_card(
            card["question"],
            card["reference_answer"],
            card["grading_rubric"],
            answer,
            load_config(),
        )
        grade = verdict.grade
        criteria_pairs = list(zip(card["grading_rubric"], verdict.met_criteria))
        judge_explanation = verdict.explanation
    except Exception as exc:  # noqa: BLE001 — surfaced to the user
        judge_error = str(exc)

    if grade is not None:
        state = load_state(conn, card_id)
        new_state = apply_review(card_id, deck["id"], state, grade, now)
        save_state(conn, new_state)
        log_review(conn, card_id, grade, new_state.state, now)
        next_due = new_state.due

    return templates.TemplateResponse(
        request,
        "feedback.html",
        {
            "deck": deck,
            "card": card,
            "answer": answer,
            "grade": grade,
            "grade_name": RATING_NAMES.get(grade),
            "criteria_pairs": criteria_pairs,
            "explanation": card.get("explanation"),
            "judge_explanation": judge_explanation,
            "judge_error": judge_error,
            "next_due": next_due,
        },
    )


def main() -> None:
    """Run the web UI with uvicorn."""
    import uvicorn

    uvicorn.run("decodeck.web:app", host="127.0.0.1", port=8000)
