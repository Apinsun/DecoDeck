"""Unit tests for the judge's deterministic parts (no LLM involved)."""

from decodeck.judge import _parse_json, grade_from_criteria


def test_grade_no_criteria_met_is_again():
    assert grade_from_criteria([]) == 1
    assert grade_from_criteria([False, False]) == 1


def test_grade_partial_is_hard():
    assert grade_from_criteria([True, False]) == 2
    assert grade_from_criteria([True, False, False]) == 2


def test_grade_all_met_is_good():
    assert grade_from_criteria([True, True]) == 3
    assert grade_from_criteria([True, True, True]) == 3


def test_parse_json_plain():
    assert _parse_json('{"met_criteria": [true, false]}') == {"met_criteria": [True, False]}


def test_parse_json_wrapped_in_prose():
    text = 'Voici mon évaluation : {"met_criteria": [true], "explanation": "ok"} fin.'
    assert _parse_json(text)["met_criteria"] == [True]
