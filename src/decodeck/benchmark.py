"""Benchmark runner: measure a judge model's agreement with human labels.

Consumes a benchmark dataset (`benchmarks/judge_dataset.yaml`) and reports how
well a model's grades agree with the expected labels, overall and per answer
kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from decodeck.config import Config, load_config
from decodeck.judge import grade_from_criteria, judge_card


def load_dataset(path: Path) -> dict[str, Any]:
    """Load a benchmark dataset from YAML."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class SampleResult:
    kind: str
    expected: int
    obtained: int | None = None
    error: str | None = None


@dataclass
class BenchmarkResult:
    samples: list[SampleResult] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for s in self.samples if s.error is not None)


def run_benchmark(
    dataset: dict[str, Any], config: Config, verbose: bool = True
) -> BenchmarkResult:
    """Run the judge over every sample of the dataset."""
    cards = {c["id"]: c for c in dataset["cards"]}
    result = BenchmarkResult()

    for i, sample in enumerate(dataset["samples"]):
        card = cards[sample["card_id"]]
        expected = grade_from_criteria([bool(x) for x in sample["expected_met"]])

        try:
            verdict = judge_card(
                card["question"],
                card["reference_answer"],
                card["grading_rubric"],
                sample["answer"],
                config,
            )
            obtained = verdict.grade
            result.samples.append(SampleResult(sample["kind"], expected, obtained))
            if verbose:
                print(f"  [{i:2d}] {sample['kind']:<12} attendu={expected} obtenu={obtained}", flush=True)
        except Exception as exc:  # noqa: BLE001 — report the failure and continue
            result.samples.append(
                SampleResult(sample["kind"], expected, error=f"{type(exc).__name__}: {exc}")
            )
            if verbose:
                print(f"  [{i:2d}] {sample['kind']:<12} ERREUR {exc}", flush=True)

    return result


def cohens_kappa(a: list[int], b: list[int]) -> float:
    """Unweighted Cohen's kappa between two sequences of ratings."""
    categories = sorted(set(a) | set(b))
    if not categories:
        return 1.0

    index = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    matrix = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        matrix[index[x]][index[y]] += 1

    n = len(a)
    po = sum(matrix[i][i] for i in range(k)) / n
    row = [sum(matrix[i]) for i in range(k)]
    col = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k)) / (n * n)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def summarize(result: BenchmarkResult) -> dict[str, Any]:
    """Compute agreement metrics over a benchmark result (pure function)."""
    ok = [s for s in result.samples if s.error is None]
    n = len(ok)
    if n == 0:
        return {
            "total": len(result.samples),
            "errors": result.errors,
            "exact": 0.0,
            "kappa": 0.0,
            "by_kind": {},
        }

    exact = sum(1 for s in ok if s.obtained == s.expected) / n
    kappa = cohens_kappa([s.expected for s in ok], [s.obtained for s in ok])

    by_kind: dict[str, float] = {}
    for kind in sorted({s.kind for s in ok}):
        sub = [s for s in ok if s.kind == kind]
        by_kind[kind] = sum(1 for s in sub if s.obtained == s.expected) / len(sub)

    return {
        "total": len(result.samples),
        "errors": result.errors,
        "exact": exact,
        "kappa": kappa,
        "by_kind": by_kind,
    }


def report(result: BenchmarkResult) -> str:
    """Format a human-readable report."""
    m = summarize(result)
    lines = [
        f"échantillons : {m['total']} (erreurs : {m['errors']})",
        f"exact match   : {m['exact']:.1%}",
        f"Cohen's kappa : {m['kappa']:.3f}",
        "par catégorie :",
    ]
    for kind, acc in m["by_kind"].items():
        lines.append(f"  {kind:<12} {acc:.0%}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``deck-benchmark <dataset.yaml>``."""
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage : deck-benchmark <dataset.yaml>", file=sys.stderr)
        return 2

    dataset = load_dataset(Path(args[0]))
    config = load_config()
    print(f"modèle : {config.model.model} ({config.model.base_url})", flush=True)

    result = run_benchmark(dataset, config)
    print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
