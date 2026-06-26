"""Prompt export for BioResearchAgentBench tasks."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from brab.io import load_jsonl, write_jsonl


SYSTEM_PROMPT = """You are being evaluated as a biology research agent.

Use only the provided artifacts. Do not use outside facts unless the prompt explicitly asks for general critique. Be skeptical: distinguish evidence, inference, speculation, and missing controls. If the source is insufficient, say so. Do not invent panels, datasets, citations, mechanisms, p-values, or controls. Avoid operational wet-lab instructions."""


def task_to_prompt_record(task: Mapping[str, Any]) -> dict[str, Any]:
    user_prompt = "\n".join(
        [
            f"Benchmark: {task['benchmark_name']}",
            f"Task ID: {task['task_id']}",
            f"Module: {task['module']}",
            f"Domain: {task['domain']} / {task['subdomain']}",
            f"Difficulty: {task['difficulty']}",
            "",
            "Source metadata:",
            _render_source_metadata(task.get("source_metadata", [])),
            "",
            "Input artifacts:",
            _render_input_artifacts(task.get("input_artifacts", {})),
            "",
            "Question:",
            str(task["prompt_to_model"]),
            "",
            "Required answer format:",
            str(task["answer_format_required"]),
            "",
            "Answer choices:",
            _render_answer_choices(task.get("answer_choices", [])),
            "",
            "Return JSON with keys: task_id, label, answer, rationale, evidence_used, uncertainty_notes.",
        ]
    )
    return {
        "task_id": task["task_id"],
        "module": task["module"],
        "difficulty": task["difficulty"],
        "ambiguity": task["ambiguity"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "expected_output_schema": {
            "task_id": "string",
            "label": "string",
            "answer": "string",
            "rationale": "string",
            "evidence_used": ["string"],
            "uncertainty_notes": "string",
        },
    }


def export_prompt_pack(tasks_path: Path, out_path: Path) -> int:
    tasks = load_jsonl(tasks_path)
    write_jsonl(out_path, [task_to_prompt_record(task) for task in tasks])
    return len(tasks)


def _render_source_metadata(source_metadata: Any) -> str:
    if not isinstance(source_metadata, list):
        return "- <invalid source metadata>"
    lines: list[str] = []
    for source in source_metadata:
        if not isinstance(source, Mapping):
            continue
        lines.append(
            "- "
            + "; ".join(
                [
                    f"source_id={source.get('source_id', '')}",
                    f"title={source.get('title', '')}",
                    f"year={source.get('year', '')}",
                    f"doi={source.get('doi', '')}",
                    f"url={source.get('url', '')}",
                    f"license={source.get('license', '')}",
                    f"commercial_use_status={source.get('commercial_use_status', '')}",
                    f"validation={source.get('source_validation_status', '')}",
                    f"artifact={source.get('figure_or_dataset_reference', '')}",
                ]
            )
        )
    return "\n".join(lines) if lines else "- <none>"


def _render_input_artifacts(input_artifacts: Any) -> str:
    if not isinstance(input_artifacts, Mapping):
        return "- <invalid input artifacts>"
    lines = []
    for key, value in input_artifacts.items():
        if isinstance(value, str) and value.strip():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) if lines else "- <none>"


def _render_answer_choices(answer_choices: Any) -> str:
    if not isinstance(answer_choices, list) or not answer_choices:
        return "- free response; follow required format"
    return "\n".join(f"- {choice}" for choice in answer_choices)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export BRAB tasks as model prompt JSONL.")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks.jsonl")
    parser.add_argument("--out", type=Path, required=True, help="Prompt pack JSONL output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    total = export_prompt_pack(args.tasks, args.out)
    print(f"Wrote {total} prompts to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
