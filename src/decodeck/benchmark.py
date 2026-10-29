"""Benchmark runner: measure a judge model's agreement with human labels.

Consumes a benchmark dataset (`benchmarks/judge_dataset.yaml`) and reports how
well a model's grades agree with the expected labels, overall and per answer
kind.
"""

from __future__ import annotations

import statistics
import time
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
    latency_seconds: float | None = None


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
            start = time.perf_counter()
            verdict = judge_card(
                card["question"],
                card["reference_answer"],
                card["grading_rubric"],
                sample["answer"],
                config,
            )
            latency = time.perf_counter() - start
            obtained = verdict.grade
            result.samples.append(
                SampleResult(sample["kind"], expected, obtained, latency_seconds=latency)
            )
            if verbose:
                print(
                    f"  [{i:2d}] {sample['kind']:<12} attendu={expected} "
                    f"obtenu={obtained} ({latency:.1f}s)",
                    flush=True,
                )
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

    latencies = [s.latency_seconds for s in ok if s.latency_seconds is not None]
    latency_stats: dict[str, float] = {}
    if latencies:
        latency_stats["avg"] = sum(latencies) / len(latencies)
        latency_stats["median"] = statistics.median(latencies)
        latency_stats["p90"] = (
            statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else max(latencies)
        )

    return {
        "total": len(result.samples),
        "errors": result.errors,
        "exact": exact,
        "kappa": kappa,
        "by_kind": by_kind,
        "latency": latency_stats,
    }


def report(result: BenchmarkResult) -> str:
    """Format a human-readable report."""
    m = summarize(result)
    lines = [
        f"échantillons : {m['total']} (erreurs : {m['errors']})",
        f"exact match   : {m['exact']:.1%}",
        f"Cohen's kappa : {m['kappa']:.3f}",
    ]
    if m["latency"]:
        lat = m["latency"]
        lines.append(
            f"latence       : moyenne {lat['avg']:.1f}s · médiane {lat['median']:.1f}s · p90 {lat['p90']:.1f}s"
        )
    lines.append("par catégorie :")
    for kind, acc in m["by_kind"].items():
        lines.append(f"  {kind:<12} {acc:.0%}")
    return "\n".join(lines)


def run_configs(
    dataset: dict[str, Any],
    configs: dict[str, Config],
    verbose: bool = True,
) -> dict[str, BenchmarkResult]:
    """Run the benchmark for several named configs."""
    results: dict[str, BenchmarkResult] = {}
    for name, config in configs.items():
        print(f"\n=== {name} ===", flush=True)
        results[name] = run_benchmark(dataset, config, verbose=verbose)
        print(report(results[name]))
    return results


def plot_results(named_metrics: dict[str, dict[str, Any]], out_path: Path) -> None:
    """Bar charts: exact match, kappa, and average latency per run."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(named_metrics)
    exact = [named_metrics[n]["exact"] * 100 for n in names]
    kappa = [named_metrics[n]["kappa"] for n in names]
    avg_lat = [named_metrics[n]["latency"].get("avg", 0.0) for n in names]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].bar(names, exact)
    axes[0].set_ylim(0, 100)
    axes[0].set_title("Exact match (%)")
    axes[1].bar(names, kappa)
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Cohen's kappa")
    axes[2].bar(names, avg_lat)
    axes[2].set_title("Latence moyenne (s)")
    for ax in axes:
        ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_per_kind(named_metrics: dict[str, dict[str, Any]], out_path: Path) -> None:
    """Grouped bar chart of per-kind accuracy."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    kinds = sorted({k for m in named_metrics.values() for k in m["by_kind"]})
    names = list(named_metrics)
    x = range(len(kinds))
    width = 0.8 / len(names)

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, name in enumerate(names):
        vals = [named_metrics[name]["by_kind"].get(k, 0.0) * 100 for k in kinds]
        ax.bar([xi + i * width for xi in x], vals, width, label=name)
    ax.set_xticks([xi + width * (len(names) - 1) / 2 for xi in x])
    ax.set_xticklabels(kinds)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Précision (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


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
