"""Validate seed dataset wrapper files.

Seed files are useful working artifacts, but they are not production JSONL
exports. This validator checks their internal consistency without granting them
production-review status.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SeedIssue:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


def load_seed(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("seed dataset must be a JSON object")
    return data


def validate_seed_dataset(data: Mapping[str, Any]) -> list[SeedIssue]:
    issues: list[SeedIssue] = []

    required_top_level = {
        "dataset_name",
        "created_at",
        "purpose",
        "important_caveats",
        "recommended_next_validation_steps",
        "schema_version",
        "sources",
        "tasks",
        "summary_counts",
    }
    _require_keys(data, required_top_level, "$", issues)

    _validate_nonempty_string(data, "dataset_name", "$.dataset_name", issues)
    _validate_nonempty_string(data, "created_at", "$.created_at", issues)
    _validate_nonempty_string(data, "purpose", "$.purpose", issues)
    _validate_string_list(data, "important_caveats", "$.important_caveats", issues)
    _validate_string_list(
        data,
        "recommended_next_validation_steps",
        "$.recommended_next_validation_steps",
        issues,
    )

    sources = data.get("sources")
    source_ids: set[str] = set()
    if not isinstance(sources, list) or not sources:
        issues.append(SeedIssue("$.sources", "must be a non-empty list"))
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                issues.append(SeedIssue(f"$.sources[{index}]", "must be an object"))
                continue
            source_ids.update(_validate_source(source, index, issues))

    tasks = data.get("tasks")
    task_ids: set[str] = set()
    task_paper_ids: list[str] = []
    if not isinstance(tasks, list) or not tasks:
        issues.append(SeedIssue("$.tasks", "must be a non-empty list"))
    else:
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                issues.append(SeedIssue(f"$.tasks[{index}]", "must be an object"))
                continue
            task_id, paper_id = _validate_task(task, index, issues, source_ids)
            if task_id:
                if task_id in task_ids:
                    issues.append(SeedIssue(f"$.tasks[{index}].task_id", "must be unique"))
                task_ids.add(task_id)
            if paper_id:
                task_paper_ids.append(paper_id)

    summary_counts = data.get("summary_counts")
    if isinstance(summary_counts, dict):
        _validate_summary_counts(summary_counts, issues, sources, tasks)
    elif "summary_counts" in data:
        issues.append(SeedIssue("$.summary_counts", "must be an object"))

    if source_ids and task_paper_ids:
        unused_sources = sorted(source_ids.difference(task_paper_ids))
        if unused_sources:
            issues.append(SeedIssue("$.sources", f"sources without tasks: {unused_sources}"))

    return issues


def _validate_source(source: Mapping[str, Any], index: int, issues: list[SeedIssue]) -> set[str]:
    path = f"$.sources[{index}]"
    required = {
        "paper_id",
        "title",
        "authors_short",
        "year",
        "journal",
        "doi",
        "pmcid",
        "url",
        "license",
        "source_status",
        "source_evidence_refs",
        "domain_tags",
    }
    _require_keys(source, required, path, issues)
    for key in ("paper_id", "title", "authors_short", "journal", "url", "license", "source_status"):
        _validate_nonempty_string(source, key, f"{path}.{key}", issues)
    if not isinstance(source.get("year"), int):
        issues.append(SeedIssue(f"{path}.year", "must be an integer"))
    doi = source.get("doi")
    if doi is not None and not isinstance(doi, str):
        issues.append(SeedIssue(f"{path}.doi", "must be null or a string"))
    pmcid = source.get("pmcid")
    if pmcid is not None and not isinstance(pmcid, str):
        issues.append(SeedIssue(f"{path}.pmcid", "must be null or a string"))
    _validate_string_list(source, "source_evidence_refs", f"{path}.source_evidence_refs", issues)
    _validate_string_list(source, "domain_tags", f"{path}.domain_tags", issues)

    paper_id = source.get("paper_id")
    return {paper_id} if isinstance(paper_id, str) and paper_id else set()


def _validate_task(
    task: Mapping[str, Any],
    index: int,
    issues: list[SeedIssue],
    source_ids: set[str],
) -> tuple[str | None, str | None]:
    path = f"$.tasks[{index}]"
    required = {
        "task_id",
        "paper_id",
        "task_type",
        "difficulty",
        "ambiguity_rating",
        "figure_grounding",
        "prompt",
        "answer_format",
        "answer_choices",
        "gold_answer",
        "expert_rationale",
        "failure_taxonomy",
        "why_strong_llms_are_likely_to_fail",
        "validation_status",
    }
    _require_keys(task, required, path, issues)

    for key in (
        "task_id",
        "paper_id",
        "task_type",
        "difficulty",
        "ambiguity_rating",
        "figure_grounding",
        "prompt",
        "answer_format",
        "gold_answer",
        "expert_rationale",
        "why_strong_llms_are_likely_to_fail",
        "validation_status",
    ):
        _validate_nonempty_string(task, key, f"{path}.{key}", issues)

    paper_id = task.get("paper_id")
    if isinstance(paper_id, str) and source_ids and paper_id not in source_ids:
        issues.append(SeedIssue(f"{path}.paper_id", "must reference a source paper_id"))

    answer_choices = task.get("answer_choices")
    if not isinstance(answer_choices, list) or len(answer_choices) < 2:
        issues.append(SeedIssue(f"{path}.answer_choices", "must contain at least two choices"))
    elif not all(isinstance(choice, str) and choice for choice in answer_choices):
        issues.append(SeedIssue(f"{path}.answer_choices", "must contain non-empty strings"))

    _validate_string_list(task, "failure_taxonomy", f"{path}.failure_taxonomy", issues)

    task_id = task.get("task_id")
    return (
        task_id if isinstance(task_id, str) and task_id else None,
        paper_id if isinstance(paper_id, str) and paper_id else None,
    )


def _validate_summary_counts(
    summary_counts: Mapping[str, Any],
    issues: list[SeedIssue],
    sources: Any,
    tasks: Any,
) -> None:
    sources_total = summary_counts.get("sources_total")
    tasks_total = summary_counts.get("tasks_total")
    if isinstance(sources, list) and sources_total != len(sources):
        issues.append(SeedIssue("$.summary_counts.sources_total", "must match len(sources)"))
    if isinstance(tasks, list) and tasks_total != len(tasks):
        issues.append(SeedIssue("$.summary_counts.tasks_total", "must match len(tasks)"))
    if "tasks_per_paper" in summary_counts and isinstance(sources, list) and isinstance(tasks, list):
        tasks_per_paper = summary_counts["tasks_per_paper"]
        if isinstance(tasks_per_paper, int):
            expected = tasks_per_paper * len(sources)
            if expected != len(tasks):
                issues.append(SeedIssue("$.summary_counts.tasks_per_paper", "does not match task/source counts"))
        elif isinstance(tasks_per_paper, dict):
            actual_counts = Counter(task.get("paper_id") for task in tasks if isinstance(task, dict))
            if tasks_per_paper != dict(actual_counts):
                issues.append(SeedIssue("$.summary_counts.tasks_per_paper", "does not match actual per-paper task counts"))
        else:
            issues.append(SeedIssue("$.summary_counts.tasks_per_paper", "must be an integer or object"))


def _require_keys(
    obj: Mapping[str, Any],
    required: set[str],
    path: str,
    issues: list[SeedIssue],
) -> None:
    for key in sorted(required.difference(obj.keys())):
        issues.append(SeedIssue(f"{path}.{key}", "is required"))


def _validate_nonempty_string(
    obj: Mapping[str, Any],
    key: str,
    path: str,
    issues: list[SeedIssue],
) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(SeedIssue(path, "must be a non-empty string"))


def _validate_string_list(
    obj: Mapping[str, Any],
    key: str,
    path: str,
    issues: list[SeedIssue],
) -> None:
    value = obj.get(key)
    if not isinstance(value, list) or not value:
        issues.append(SeedIssue(path, "must be a non-empty list"))
        return
    if not all(isinstance(item, str) and item.strip() for item in value):
        issues.append(SeedIssue(path, "must contain non-empty strings"))


def validate_files(paths: list[Path]) -> tuple[int, list[str]]:
    rendered_issues: list[str] = []
    total_tasks = 0
    for path in paths:
        try:
            data = load_seed(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rendered_issues.append(f"{path}: {exc}")
            continue
        tasks = data.get("tasks")
        if isinstance(tasks, list):
            total_tasks += len(tasks)
        rendered_issues.extend(f"{path}: {issue.render()}" for issue in validate_seed_dataset(data))
    return total_tasks, rendered_issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate BioFigure seed wrapper JSON files.")
    parser.add_argument("paths", nargs="+", type=Path, help="Seed JSON files to validate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    total_tasks, issues = validate_files(args.paths)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"FAILED: {len(issues)} issue(s) across {total_tasks} task(s)", file=sys.stderr)
        return 1
    print(f"OK: {total_tasks} seed task(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
