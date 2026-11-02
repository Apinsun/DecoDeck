"""Web UI (FastAPI) for DecoDeck.

Thin frontend over the existing engine: it serves decks, shows the next due
card, and posts answers through the judge + FSRS + SQLite pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
from decodeck.storage import deck_stats, init_db, load_state, log_review, missed_card_ids, reset_deck, save_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DECKS_DIR = BASE_DIR / "decks"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="DecoDeck")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

RATING_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


@dataclass
class ReviewSession:
    queue: list[str]  # card ids left in this pass
    total: int        # queue length when the pass started


#: In-memory review sessions (local, single-user): "<deck_id>:<mode>" -> session.
_sessions: dict[str, ReviewSession] = {}


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


CRAM_MODES = ("all", "missed")


def _session_key(deck_id: str, mode: str) -> str:
    return f"{deck_id}:{mode}"


def _build_queue(deck: dict, deck_id: str, mode: str, conn, now: datetime) -> list[str]:
    """Card ids to review this pass, in order.

    Normal: never-seen cards first, then due cards (deck order) — a full pass
    over the deck before any relearning card reappears.
    """
    if mode == "all":
        return [card["id"] for card in deck["cards"]]
    if mode == "missed":
        missed = missed_card_ids(conn, deck_id)
        return [card["id"] for card in deck["cards"] if card["id"] in missed]
    new = [card["id"] for card in deck["cards"] if load_state(conn, card["id"]) is None]
    due = [
        card["id"]
        for card in deck["cards"]
        if (state := load_state(conn, card["id"])) is not None and state.due <= now
    ]
    return new + due


def _get_session(deck: dict, deck_id: str, mode: str, conn, now: datetime) -> ReviewSession:
    key = _session_key(deck_id, mode)
    session = _sessions.get(key)
    if session is None or not session.queue:
        queue = _build_queue(deck, deck_id, mode, conn, now)
        session = ReviewSession(queue=queue, total=len(queue))
        if queue:
            _sessions[key] = session
    return session


def _session_next(
    deck: dict, deck_id: str, mode: str, conn, now: datetime
) -> tuple[dict | None, int, int]:
    """Next card and its progress (position, total); (None, 0, 0) when done."""
    session = _get_session(deck, deck_id, mode, conn, now)
    if not session.queue:
        return None, 0, 0
    card_id = session.queue[0]
    card = next(c for c in deck["cards"] if c["id"] == card_id)
    position = session.total - len(session.queue) + 1
    return card, position, session.total


def _session_pop(deck_id: str, mode: str, card_id: str) -> None:
    """Mark ``card_id`` done in the current pass; drop the session when empty."""
    session = _sessions.get(_session_key(deck_id, mode))
    if not session:
        return
    try:
        session.queue.remove(card_id)
    except ValueError:
        pass
    if not session.queue:
        _sessions.pop(_session_key(deck_id, mode), None)


def _session_active(deck_id: str, mode: str) -> bool:
    session = _sessions.get(_session_key(deck_id, mode))
    return bool(session and session.queue)


def _clear_deck_sessions(deck_id: str) -> None:
    """Drop all in-memory review sessions for a deck."""
    prefix = f"{deck_id}:"
    for key in [k for k in _sessions if k.startswith(prefix)]:
        _sessions.pop(key, None)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"decks": _list_decks()})


@app.get("/deck/{deck_id}/reset", response_class=HTMLResponse)
def reset_deck_page(request: Request, deck_id: str):
    deck = _load_deck(deck_id)
    if deck is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "reset.html", {"deck": deck})


@app.post("/deck/{deck_id}/reset", response_class=HTMLResponse)
def reset_deck_action(deck_id: str):
    deck = _load_deck(deck_id)
    if deck is None:
        return RedirectResponse("/", status_code=303)
    conn = init_db()
    reset_deck(conn, deck_id)
    _clear_deck_sessions(deck_id)
    return RedirectResponse("/", status_code=303)


@app.get("/deck/{deck_id}", response_class=HTMLResponse)
def review(request: Request, deck_id: str, cram: str = ""):
    deck = _load_deck(deck_id)
    if deck is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    mode = cram if cram in CRAM_MODES else "normal"
    card, position, total = _session_next(deck, deck_id, mode, conn, now)

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
        {"deck": deck, "card": card, "cram": cram, "position": position, "total": total},
    )


@app.post("/deck/{deck_id}/answer", response_class=HTMLResponse)
def answer(
    request: Request,
    deck_id: str,
    card_id: str = Form(...),
    answer: str = Form(""),
    hint_pending: str = Form(""),
    first_answer: str = Form(""),
    cram: str = Form(""),
    dont_know: str = Form(""),
):
    deck = _load_deck(deck_id)
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if deck is None or card is None:
        return RedirectResponse("/", status_code=303)

    conn = init_db()
    now = datetime.now(timezone.utc)
    config = load_config()
    mode = cram if cram in CRAM_MODES else "normal"
    answer = answer.strip() or "Je ne sais pas."
    is_hint_pending = hint_pending == "true"
    is_dont_know = dont_know == "true"

    grade = None
    criteria_pairs: list[tuple[str, bool]] = []
    judge_explanation = None
    judge_error = None
    next_due = None

    if is_dont_know:
        # Explicit give-up: no LLM call, straight to Again.
        grade = 1
        judged_answer = "Je ne sais pas."
        criteria_pairs = [(criterion, False) for criterion in card["grading_rubric"]]
    else:
        judged_answer = combine_after_hint(first_answer, answer) if is_hint_pending else answer
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
                        "missed_count": len(verdict.met_criteria) - sum(verdict.met_criteria),
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
        _session_pop(deck_id, mode, card_id)

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
            "cram_mode": cram if cram in CRAM_MODES and _session_active(deck_id, cram) else "",
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
