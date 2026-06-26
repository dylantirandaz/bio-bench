"""Auto-score BRAB model outputs and generate failure artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from brab.io import load_jsonl, write_json, write_jsonl


def normalize_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^[a-d]\s*[\.)-]\s*", "", text)
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    synonyms = {
        "overclaimed_not_supported": "overclaimed",
        "not_verifiable_from_provided_evidence": "not_verifiable_from_provided_evidence",
        "likely_batch_effect_label_leakage": "likely_batch_effect",
    }
    return synonyms.get(text, text)


def output_label(output: Mapping[str, Any]) -> str:
    for key in ("label", "answer", "short_answer", "raw_output"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def score_outputs(tasks_path: Path, outputs_path: Path, out_dir: Path) -> dict[str, Any]:
    tasks = load_jsonl(tasks_path)
    outputs = load_jsonl(outputs_path)
    outputs_by_task = {str(output.get("task_id")): output for output in outputs}

    per_task: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task["task_id"])
        output = outputs_by_task.get(task_id)
        gold_label = normalize_label(task["gold_answer"]["label"])
        raw_model_label = output_label(output or {})
        model_label = normalize_label(raw_model_label)
        label_correct = bool(output) and model_label == gold_label
        per_task.append(
            {
                "task_id": task_id,
                "module": task["module"],
                "difficulty": task["difficulty"],
                "ambiguity": task["ambiguity"],
                "gold_label": task["gold_answer"]["label"],
                "model_label": raw_model_label if output else "",
                "label_correct": label_correct,
                "auto_label_score": 1 if label_correct else 0,
                "requires_expert_grading": bool(task["scoring"].get("requires_expert_grading", True)),
                "failure_taxonomy": task["failure_taxonomy"],
                "model_name": output.get("model_name", "unknown") if output else "missing",
                "known_risks": task["expert_review"].get("known_risks", []),
            }
        )

    summary = build_summary(per_task, total_tasks=len(tasks), output_count=len(outputs))
    report = {
        "summary": summary,
        "per_task": per_task,
        "notes": [
            "Automatic score is label-level only.",
            "Expert grading is still required for rationale, evidence grounding, hallucinations, safety, and partial credit.",
            "Use this score to triage models and select failures for expert review, not as final commercial scoring.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "scores.json", report)
    (out_dir / "failure_report.md").write_text(render_failure_report(report), encoding="utf-8")
    write_jsonl(out_dir / "targeted_training_data.jsonl", targeted_training_examples(tasks, outputs_by_task, per_task))
    return report


def build_summary(per_task: list[Mapping[str, Any]], *, total_tasks: int, output_count: int) -> dict[str, Any]:
    correct = sum(1 for item in per_task if item["label_correct"])
    by_module: dict[str, dict[str, Any]] = {}
    for module, items in _group_by(per_task, "module").items():
        module_correct = sum(1 for item in items if item["label_correct"])
        by_module[module] = {
            "total": len(items),
            "correct": module_correct,
            "accuracy": _rate(module_correct, len(items)),
        }

    by_failure: dict[str, dict[str, Any]] = {}
    totals: Counter[str] = Counter()
    corrects: Counter[str] = Counter()
    for item in per_task:
        for failure in item["failure_taxonomy"]:
            totals[failure] += 1
            if item["label_correct"]:
                corrects[failure] += 1
    for failure, total in sorted(totals.items()):
        by_failure[failure] = {
            "total": total,
            "correct": corrects[failure],
            "accuracy": _rate(corrects[failure], total),
        }

    return {
        "total_tasks": total_tasks,
        "outputs_received": output_count,
        "missing_outputs": total_tasks - output_count,
        "correct": correct,
        "label_accuracy": _rate(correct, total_tasks),
        "below_20_percent": _rate(correct, total_tasks) < 0.20,
        "by_module": by_module,
        "by_failure_taxonomy": by_failure,
    }


def targeted_training_examples(
    tasks: list[Mapping[str, Any]],
    outputs_by_task: Mapping[str, Mapping[str, Any]],
    per_task: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    tasks_by_id = {str(task["task_id"]): task for task in tasks}
    examples: list[dict[str, Any]] = []
    for result in per_task:
        if result["label_correct"]:
            continue
        task = tasks_by_id[result["task_id"]]
        output = outputs_by_task.get(result["task_id"], {})
        examples.append(
            {
                "task_id": task["task_id"],
                "module": task["module"],
                "failure_taxonomy": task["failure_taxonomy"],
                "prompt": task["prompt_to_model"],
                "input_artifacts": task["input_artifacts"],
                "model_answer_to_improve": {
                    "label": output_label(output),
                    "rationale": output.get("rationale", ""),
                    "raw_output": output.get("raw_output", ""),
                },
                "preferred_answer": {
                    "label": task["gold_answer"]["label"],
                    "short_answer": task["gold_answer"]["short_answer"],
                    "rationale": task["gold_answer"]["detailed_rationale"],
                    "evidence_used": task["gold_answer"]["evidence_used"],
                    "uncertainty_notes": task["gold_answer"]["uncertainty_notes"],
                },
                "training_objective": "Teach the model to answer conservatively from provided evidence, name missing controls/confounders, and avoid hallucinated mechanisms.",
            }
        )
    return examples


def render_failure_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# BioResearchAgentBench Failure Report",
        "",
        "Automatic scoring is label-level only; expert grading is required for final scores.",
        "",
        "## Summary",
        "",
        f"- Total tasks: {summary['total_tasks']}",
        f"- Outputs received: {summary['outputs_received']}",
        f"- Missing outputs: {summary['missing_outputs']}",
        f"- Correct labels: {summary['correct']}",
        f"- Label accuracy: {summary['label_accuracy']:.1%}",
        f"- Below 20 percent target: {summary['below_20_percent']}",
        "",
        "## By Module",
        "",
    ]
    for module, stats in summary["by_module"].items():
        lines.append(f"- {module}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.1%})")
    lines.extend(["", "## Hardest Failure Tags", ""])
    failure_rows = sorted(
        summary["by_failure_taxonomy"].items(),
        key=lambda item: (item[1]["accuracy"], -item[1]["total"], item[0]),
    )
    for failure, stats in failure_rows[:20]:
        lines.append(f"- {failure}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.1%})")
    lines.extend(["", "## Failed Tasks", ""])
    for item in report["per_task"]:
        if item["label_correct"]:
            continue
        lines.append(
            f"- {item['task_id']} ({item['module']}): gold={item['gold_label']!r}, model={item['model_label']!r}, tags={', '.join(item['failure_taxonomy'])}"
        )
    lines.append("")
    return "\n".join(lines)


def _group_by(items: list[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item[key])].append(item)
    return dict(grouped)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score BRAB model outputs.")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks.jsonl")
    parser.add_argument("--outputs", type=Path, required=True, help="Model outputs JSONL path")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for scores/report/training data")
    parser.add_argument(
        "--target-max-accuracy",
        type=float,
        help="Optional hardness gate. Exit nonzero if auto label accuracy is greater than or equal to this value.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = score_outputs(args.tasks, args.outputs, args.out_dir)
    accuracy = report["summary"]["label_accuracy"]
    print(f"Auto label accuracy: {accuracy:.1%}")
    print(f"Wrote scores/report/training data to {args.out_dir}")
    if args.target_max_accuracy is not None and accuracy >= args.target_max_accuracy:
        print(
            f"FAILED hardness target: {accuracy:.1%} >= {args.target_max_accuracy:.1%}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
