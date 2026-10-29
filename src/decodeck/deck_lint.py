"""Deck validation for DecoDeck.

The rules implemented here match `docs/data-model.md`. ``validate_deck`` is the
reusable core: the review engine will call it before loading a deck, and the
CLI is just a thin wrapper around it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: Card fields that must be present.
REQUIRED_FIELDS = ("id", "question", "reference_answer", "grading_rubric")
#: Card fields that may be present.
OPTIONAL_FIELDS = ("source_anchor",)

#: Deck/card identifiers: lowercase words separated by single hyphens.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: Code anchor: "path:Lstart-end" or "path:Lstart".
ANCHOR_RE = re.compile(r"^(?P<path>.+):L(?P<start>\d+)(?:-(?P<end>\d+))?$")

MIN_RUBRIC = 2
MAX_RUBRIC = 3


@dataclass(frozen=True)
class Issue:
    """A single validation problem, with its severity and location."""

    severity: str  # "error" | "warning"
    location: str  # dot path, e.g. "cards[2].grading_rubric" ("" = whole file)
    message: str


def validate_deck(data: Any, base_dir: Path | None = None) -> list[Issue]:
    """Validate a parsed deck (dict) and return the list of issues.

    ``base_dir`` is used to resolve ``source_anchor`` file paths; it defaults
    to the current working directory.
    """
    issues: list[Issue] = []
    base_dir = base_dir or Path.cwd()

    if not isinstance(data, dict):
        return [Issue("error", "", "le fichier doit contenir un mapping YAML")]

    for field in ("id", "title", "cards"):
        if field not in data:
            issues.append(Issue("error", field, f"champ obligatoire manquant : {field}"))

    deck_id = data.get("id")
    if deck_id is None or not isinstance(deck_id, str) or not deck_id:
        issues.append(Issue("error", "id", "doit être une chaîne non vide"))
    elif not SLUG_RE.fullmatch(deck_id):
        issues.append(
            Issue("error", "id", f"format invalide ({deck_id!r}), attendu [a-z0-9-]+")
        )

    title = data.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        issues.append(Issue("error", "title", "doit être une chaîne non vide"))

    cards = data.get("cards")
    if cards is None:
        return issues  # missing field already reported

    if not isinstance(cards, list):
        issues.append(Issue("error", "cards", "doit être une liste"))
        return issues

    if not cards:
        issues.append(Issue("warning", "cards", "le deck ne contient aucune carte"))

    seen: dict[str, int] = {}
    for index, card in enumerate(cards):
        location = f"cards[{index}]"
        if not isinstance(card, dict):
            issues.append(Issue("error", location, "chaque carte doit être un mapping"))
            continue
        _validate_card(card, location, base_dir, issues)

        card_id = card.get("id")
        if isinstance(card_id, str) and card_id:
            if card_id in seen:
                issues.append(
                    Issue(
                        "error",
                        f"{location}.id",
                        f"id dupliqué ({card_id!r}), déjà vu à cards[{seen[card_id]}]",
                    )
                )
            else:
                seen[card_id] = index

    return issues


def _validate_card(
    card: dict[str, Any], location: str, base_dir: Path, issues: list[Issue]
) -> None:
    for field in REQUIRED_FIELDS:
        if field not in card:
            issues.append(
                Issue("error", f"{location}.{field}", f"champ obligatoire manquant : {field}")
            )

    card_id = card.get("id")
    if card_id is not None:
        if not isinstance(card_id, str) or not card_id:
            issues.append(Issue("error", f"{location}.id", "doit être une chaîne non vide"))
        elif not SLUG_RE.fullmatch(card_id):
            issues.append(Issue("error", f"{location}.id", f"format invalide ({card_id!r})"))

    for field in ("question", "reference_answer"):
        value = card.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            issues.append(Issue("error", f"{location}.{field}", "doit être une chaîne non vide"))

    rubric = card.get("grading_rubric")
    if rubric is not None:
        if not isinstance(rubric, list):
            issues.append(Issue("error", f"{location}.grading_rubric", "doit être une liste"))
        else:
            if not MIN_RUBRIC <= len(rubric) <= MAX_RUBRIC:
                issues.append(
                    Issue(
                        "error",
                        f"{location}.grading_rubric",
                        f"doit contenir {MIN_RUBRIC} à {MAX_RUBRIC} critères "
                        f"(actuellement {len(rubric)})",
                    )
                )
            for j, criterion in enumerate(rubric):
                if not isinstance(criterion, str) or not criterion.strip():
                    issues.append(
                        Issue(
                            "error",
                            f"{location}.grading_rubric[{j}]",
                            "chaque critère doit être une chaîne non vide",
                        )
                    )

    anchor = card.get("source_anchor")
    if anchor is not None:
        if not isinstance(anchor, str) or not anchor.strip():
            issues.append(Issue("error", f"{location}.source_anchor", "doit être une chaîne non vide"))
        else:
            _check_anchor(anchor, f"{location}.source_anchor", base_dir, issues)


def _check_anchor(anchor: str, location: str, base_dir: Path, issues: list[Issue]) -> None:
    match = ANCHOR_RE.match(anchor)
    if not match:
        # URL, section reference, etc. — not verifiable from here.
        issues.append(
            Issue("warning", location, f"source_anchor non vérifiable : {anchor!r}")
        )
        return

    start = int(match.group("start"))
    end = int(match.group("end")) if match.group("end") else start
    if end < start:
        issues.append(Issue("error", location, f"ligne de fin ({end}) < ligne de début ({start})"))
        return

    path = (base_dir / match.group("path")).resolve()
    if not path.is_file():
        issues.append(Issue("error", location, f"fichier introuvable : {match.group('path')}"))


def lint_file(path: Path, base_dir: Path | None = None) -> list[Issue]:
    """Read and validate a deck file, returning its issues."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Issue("error", "", f"impossible de lire le fichier : {exc}")]

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [Issue("error", "", f"YAML invalide : {exc}")]

    return validate_deck(data, base_dir=base_dir)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``deck-lint <fichier.yaml>...``.

    Exit code: 0 = no errors, 1 = at least one error, 2 = usage error.
    """
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage : deck-lint <fichier.yaml>...", file=sys.stderr)
        return 2

    had_error = False
    for raw in args:
        path = Path(raw)
        issues = lint_file(path)
        if not issues:
            print(f"{path} : OK")
            continue
        for issue in issues:
            where = f"{issue.location}: " if issue.location else ""
            print(f"{path} [{issue.severity}] {where}{issue.message}")
        if any(i.severity == "error" for i in issues):
            had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
