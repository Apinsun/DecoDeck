"""Unit tests for the benchmark metrics (no LLM involved)."""

from decodeck.benchmark import BenchmarkResult, SampleResult, cohens_kappa, summarize


def test_kappa_perfect_agreement():
    assert cohens_kappa([1, 1, 2, 2, 3, 3], [1, 1, 2, 2, 3, 3]) == 1.0


def test_kappa_total_disagreement():
    assert cohens_kappa([1, 1, 2, 2], [2, 2, 1, 1]) == -1.0


def test_kappa_chance_level():
    assert abs(cohens_kappa([1, 1, 2, 2], [1, 2, 1, 2])) < 1e-9


def test_summarize_perfect():
    result = BenchmarkResult(
        samples=[
            SampleResult("perfect", 3, 3),
            SampleResult("negation", 1, 1),
        ]
    )
    metrics = summarize(result)
    assert metrics["exact"] == 1.0
    assert metrics["kappa"] == 1.0
    assert metrics["errors"] == 0


def test_summarize_counts_errors():
    result = BenchmarkResult(
        samples=[
            SampleResult("perfect", 3, 3),
            SampleResult("vague", 1, error="Timeout"),
        ]
    )
    metrics = summarize(result)
    assert metrics["errors"] == 1
    assert metrics["total"] == 2
    assert metrics["exact"] == 1.0  # errors are excluded from agreement
