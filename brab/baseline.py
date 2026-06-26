"""No-network baseline model outputs for smoke-testing the benchmark harness."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from brab.io import load_jsonl, write_jsonl


MODULE_PRIOR_LABELS = {
    "biofigure_claimcheck": "Overclaimed",
    "biodatascience_reprobench": "invalid_analysis_plan",
    "bioimage_artifact_vs_biology": "insufficient_evidence",
    "literature_contradiction_synthesis": "mixed_or_context_dependent",
    "experimental_design_control_critic": "missing_control",
}

UNCERTAIN_LABELS = {
    "biofigure_claimcheck": "Not verifiable from provided evidence",
    "biodatascience_reprobench": "insufficient_evidence",
    "bioimage_artifact_vs_biology": "insufficient_evidence",
    "literature_contradiction_synthesis": "unresolved",
    "experimental_design_control_critic": "insufficient_evidence",
}


def baseline_output(task: Mapping[str, Any], *, strategy: str) -> dict[str, Any]:
    if strategy == "module_prior":
        label = MODULE_PRIOR_LABELS.get(str(task.get("module")), "insufficient_evidence")
    elif strategy == "always_uncertain":
        label = UNCERTAIN_LABELS.get(str(task.get("module")), "insufficient_evidence")
    else:
        raise ValueError(f"unknown baseline strategy: {strategy}")
    return {
        "task_id": task["task_id"],
        "model_name": f"baseline:{strategy}",
        "label": label,
        "answer": label,
        "rationale": "No-network smoke-test baseline. This is not a biology-capable model.",
        "evidence_used": [],
        "uncertainty_notes": "Generated only to verify the benchmark runner.",
        "raw_output": label,
    }


def write_baseline_outputs(tasks_path: Path, out_path: Path, *, strategy: str) -> int:
    tasks = load_jsonl(tasks_path)
    write_jsonl(out_path, [baseline_output(task, strategy=strategy) for task in tasks])
    return len(tasks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create baseline BRAB model outputs for smoke tests.")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks.jsonl")
    parser.add_argument("--out", type=Path, required=True, help="Model outputs JSONL path")
    parser.add_argument("--strategy", choices=["module_prior", "always_uncertain"], default="module_prior")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    total = write_baseline_outputs(args.tasks, args.out, strategy=args.strategy)
    print(f"Wrote {total} {args.strategy} baseline outputs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
