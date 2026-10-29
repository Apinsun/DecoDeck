"""Unit tests for the judge's deterministic parts (no LLM involved)."""

import pytest

from decodeck.judge import _format_guidance, _parse_json, grade_from_criteria, parse_verdict


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


def test_parse_verdict_ok():
    met, expl = parse_verdict({"met_criteria": [True, False], "explanation": "ok"}, 2)
    assert met == [True, False]
    assert expl == "ok"


def test_parse_verdict_bool_is_rejected():
    with pytest.raises(ValueError):
        parse_verdict({"met_criteria": True}, 2)


def test_parse_verdict_wrong_length():
    with pytest.raises(ValueError):
        parse_verdict({"met_criteria": [True]}, 2)


def test_format_guidance_mentions_format_and_count():
    guidance = _format_guidance(3, "sortie bidon")
    assert "met_criteria" in guidance
    assert "3 booléens" in guidance
    assert "sortie bidon" in guidance
