"""Web UI (FastAPI) for DecoDeck.

Thin frontend over the existing engine: it serves decks, shows the next due
card, and posts answers through the judge + FSRS + SQLite pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from decodeck.chat import ask_question
from decodeck.config import load_config
from decodeck.judge import cap_grade_after_hint, combine_after_hint, generate_hint, judge_card
from decodeck.scheduler import apply_review
from decodeck.storage import deck_stats, init_db, load_state, log_review, missed_card_ids, save_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DECKS_DIR = BASE_DIR / "decks"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="DecoDeck")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

RATING_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

#: In-memory cram sessions (local, single-user): "<deck_id>:<mode>" -> cards left.
_cram_sessions: dict[str, list[str]] = {}


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
    """Next card to review: never-seen cards first, then due cards (deck order).

    This gives a full pass over the deck before any relearning card reappears,
    even when a failed card becomes due again mid-session.
    """
    for card in deck["cards"]:
        if load_state(conn, card["id"]) is None:
            return card
    for card in deck["cards"]:
        state = load_state(conn, card["id"])
        if state.due <= now:
            return card
    return None


CRAM_MODES = ("all", "missed")


def _cram_key(deck_id: str, mode: str) -> str:
    return f"{deck_id}:{mode}"


def _cram_queue(deck: dict, deck_id: str, mode: str, conn) -> list[str]:
    """Return (and lazily create) the cram pass queue for a deck + mode."""
    key = _cram_key(deck_id, mode)
    queue = _cram_sessions.get(key)
    if queue is None:
        if mode == "missed":
            missed = missed_card_ids(conn, deck_id)
            queue = [card["id"] for card in deck["cards"] if card["id"] in missed]
        else:
            queue = [card["id"] for card in deck["cards"]]
        _cram_sessions[key] = queue
    return queue


def _cram_next_card(deck: dict, deck_id: str, mode: str, conn) -> dict | None:
    queue = _cram_queue(deck, deck_id, mode, conn)
    if not queue:
        return None
    return next(card for card in deck["cards"] if card["id"] == queue[0])


def _cram_pop(deck_id: str, mode: str, card_id: str) -> None:
    """Mark ``card_id`` done in the cram pass; drop the session when empty."""
    key = _cram_key(deck_id, mode)
    queue = _cram_sessions.get(key)
    if not queue:
        return
    try:
        queue.remove(card_id)
    except ValueError:
        pass
    if not queue:
        _cram_sessions.pop(key, None)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"decks": _list_decks()})


@app.get("/deck/{deck_id}", response_class=HTMLResponse)
def review(request: Request, deck_id: str, cram: str = ""):
    deck = _load_deck(deck_id)
    if deck is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    if cram in CRAM_MODES:
        card = _cram_next_card(deck, deck_id, cram, conn)
    else:
        card = _next_due_card(deck, conn, now)

    if card is None:
        counts = deck_stats(conn, deck_id)
        return templates.TemplateResponse(
            request,
            "done.html",
            {
                "deck": deck,
                "counts": counts,
                "total_reviews": sum(counts.values()),
                "missed_count": len(missed_card_ids(conn, deck_id)),
            },
        )
    return templates.TemplateResponse(
        request,
        "review.html",
        {"deck": deck, "card": card, "cram": cram},
    )


@app.post("/deck/{deck_id}/answer", response_class=HTMLResponse)
def answer(
    request: Request,
    deck_id: str,
    card_id: str = Form(...),
    answer: str = Form(...),
    hint_pending: str = Form(""),
    first_answer: str = Form(""),
    cram: str = Form(""),
):
    deck = _load_deck(deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if deck is None or card is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    config = load_config()
    answer = answer.strip() or "Je ne sais pas."
    is_hint_pending = hint_pending == "true"
    judged_answer = combine_after_hint(first_answer, answer) if is_hint_pending else answer

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
            judged_answer,
            config,
        )
        grade = verdict.grade
        criteria_pairs = list(zip(card["grading_rubric"], verdict.met_criteria))
        judge_explanation = verdict.explanation
    except Exception as exc:  # noqa: BLE001 — surfaced to the user
        judge_error = str(exc)

    # Relance socratique sur une première réponse partielle (grade 2).
    if grade == 2 and not is_hint_pending and not judge_error:
        try:
            hint = generate_hint(
                card["question"],
                card["reference_answer"],
                card["grading_rubric"],
                verdict.met_criteria,
                answer,
                config,
            )
            return templates.TemplateResponse(
                request,
                "hint.html",
                {
                    "deck": deck,
                    "card": card,
                    "answer": answer,
                    "cram": cram,
                    "criteria_pairs": criteria_pairs,
                    "hint": hint,
                },
            )
        except Exception:  # noqa: BLE001 — fall back to plain feedback
            pass

    if grade is not None:
        if is_hint_pending:
            grade = cap_grade_after_hint(grade)
        state = load_state(conn, card_id)
        new_state = apply_review(card_id, deck["id"], state, grade, now)
        save_state(conn, new_state)
        log_review(conn, card_id, grade, new_state.state, now)
        next_due = new_state.due
        if cram in CRAM_MODES:
            _cram_pop(deck_id, cram, card_id)

    return templates.TemplateResponse(
        request,
        "feedback.html",
        {
            "deck": deck,
            "card": card,
            "answer": judged_answer,
            "grade": grade,
            "grade_name": RATING_NAMES.get(grade),
            "criteria_pairs": criteria_pairs,
            "explanation": card.get("explanation"),
            "judge_explanation": judge_explanation,
            "judge_error": judge_error,
            "next_due": next_due,
            "hint_used": is_hint_pending,
            "cram_mode": cram if cram in CRAM_MODES and _cram_key(deck_id, cram) in _cram_sessions else "",
        },
    )


@app.get("/deck/{deck_id}/{card_id}/chat", response_class=HTMLResponse)
def chat_page(request: Request, deck_id: str, card_id: str):
    deck = _load_deck(deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if deck is None or card is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"deck": deck, "card": card, "history": [], "history_json": "[]"},
    )


@app.post("/deck/{deck_id}/{card_id}/chat", response_class=HTMLResponse)
def chat_post(
    request: Request,
    deck_id: str,
    card_id: str,
    question: str = Form(...),
    history: str = Form("[]"),
):
    deck = _load_deck(deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if deck is None or card is None:
        return RedirectResponse("/", status_code=303)

    try:
        history_list = json.loads(history)
        if not isinstance(history_list, list):
            history_list = []
    except (json.JSONDecodeError, TypeError):
        history_list = []

    question = question.strip()
    if question:
        answer = ask_question(card, history_list, question, load_config())
        history_list.append({"role": "user", "content": question})
        history_list.append({"role": "assistant", "content": answer})

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "deck": deck,
            "card": card,
            "history": history_list,
            "history_json": json.dumps(history_list),
        },
    )


def main() -> None:
    """Run the web UI with uvicorn."""
    import uvicorn

    uvicorn.run("decodeck.web:app", host="127.0.0.1", port=8000)
