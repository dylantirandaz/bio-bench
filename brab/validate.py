"""Validation for BioResearchAgentBench task packs."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from brab.io import load_json, load_jsonl
from brab.schema import (
    AMBIGUITIES,
    BENCHMARK_NAME,
    COMMERCIAL_USE_STATUSES,
    DIFFICULTIES,
    MODULES,
    REQUIRED_EXPERT_REVIEW_KEYS,
    REQUIRED_GOLD_KEYS,
    REQUIRED_INPUT_ARTIFACT_KEYS,
    REQUIRED_SCORING_KEYS,
    REQUIRED_SOURCE_METADATA_KEYS,
    REQUIRED_TASK_KEYS,
    SAFETY_LEVELS,
    SOURCE_VALIDATION_STATUSES,
    TASK_ID_RE,
)


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


def validate_task(record: Mapping[str, Any], *, path: str = "$") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    _require_keys(record, REQUIRED_TASK_KEYS, path, issues)

    if record.get("benchmark_name") != BENCHMARK_NAME:
        issues.append(ValidationIssue(f"{path}.benchmark_name", f"must be {BENCHMARK_NAME!r}"))

    task_id = record.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        issues.append(ValidationIssue(f"{path}.task_id", "must match BRAB-[FIG|DATA|IMG|LIT|CTRL]-000"))

    module = record.get("module")
    if module not in MODULES:
        issues.append(ValidationIssue(f"{path}.module", f"must be one of {sorted(MODULES)}"))
    elif isinstance(task_id, str) and not task_id.startswith(MODULES[module]):
        issues.append(ValidationIssue(f"{path}.task_id", f"must use prefix {MODULES[module]} for module {module}"))

    _validate_nonempty_string(record, "task_type", f"{path}.task_type", issues)
    _validate_nonempty_string(record, "domain", f"{path}.domain", issues)
    _validate_nonempty_string(record, "subdomain", f"{path}.subdomain", issues)
    _validate_enum(record.get("difficulty"), DIFFICULTIES, f"{path}.difficulty", issues)
    _validate_enum(record.get("ambiguity"), AMBIGUITIES, f"{path}.ambiguity", issues)
    _validate_enum(record.get("safety_level"), SAFETY_LEVELS, f"{path}.safety_level", issues)

    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or not all(isinstance(item, str) and item for item in source_ids):
        issues.append(ValidationIssue(f"{path}.source_ids", "must be a non-empty list of strings"))

    source_metadata = record.get("source_metadata")
    if not isinstance(source_metadata, list) or not source_metadata:
        issues.append(ValidationIssue(f"{path}.source_metadata", "must be a non-empty list"))
    else:
        metadata_ids: list[str] = []
        for index, metadata in enumerate(source_metadata):
            if not isinstance(metadata, dict):
                issues.append(ValidationIssue(f"{path}.source_metadata[{index}]", "must be an object"))
                continue
            metadata_ids.append(str(metadata.get("source_id", "")))
            _validate_source_metadata(metadata, f"{path}.source_metadata[{index}]", issues)
        if isinstance(source_ids, list) and sorted(source_ids) != sorted(metadata_ids):
            issues.append(ValidationIssue(f"{path}.source_metadata", "source_metadata IDs must match source_ids"))

    input_artifacts = record.get("input_artifacts")
    if isinstance(input_artifacts, Mapping):
        _require_keys(input_artifacts, REQUIRED_INPUT_ARTIFACT_KEYS, f"{path}.input_artifacts", issues)
    else:
        issues.append(ValidationIssue(f"{path}.input_artifacts", "must be an object"))

    _validate_nonempty_string(record, "prompt_to_model", f"{path}.prompt_to_model", issues)
    _validate_nonempty_string(record, "answer_format_required", f"{path}.answer_format_required", issues)
    if not isinstance(record.get("answer_choices"), list):
        issues.append(ValidationIssue(f"{path}.answer_choices", "must be a list"))

    gold = record.get("gold_answer")
    if isinstance(gold, Mapping):
        _validate_gold(gold, f"{path}.gold_answer", issues)
    else:
        issues.append(ValidationIssue(f"{path}.gold_answer", "must be an object"))

    scoring = record.get("scoring")
    if isinstance(scoring, Mapping):
        _validate_scoring(scoring, f"{path}.scoring", issues)
    else:
        issues.append(ValidationIssue(f"{path}.scoring", "must be an object"))

    _validate_string_list(record, "failure_taxonomy", f"{path}.failure_taxonomy", issues)
    _validate_string_list(record, "why_strong_llms_fail", f"{path}.why_strong_llms_fail", issues)
    _validate_string_list(record, "adversarial_features", f"{path}.adversarial_features", issues)

    expert_review = record.get("expert_review")
    if isinstance(expert_review, Mapping):
        _validate_expert_review(expert_review, f"{path}.expert_review", issues)
    else:
        issues.append(ValidationIssue(f"{path}.expert_review", "must be an object"))

    return issues


def validate_task_pack(
    tasks_path: Path,
    *,
    sources_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> tuple[int, list[str]]:
    rendered: list[str] = []
    try:
        tasks = load_jsonl(tasks_path)
    except ValueError as exc:
        return 0, [str(exc)]

    task_ids: set[str] = set()
    for index, task in enumerate(tasks, 1):
        task_id = task.get("task_id")
        if isinstance(task_id, str):
            if task_id in task_ids:
                rendered.append(f"{tasks_path}:{index}: $.task_id: duplicate task_id {task_id}")
            task_ids.add(task_id)
        for issue in validate_task(task, path="$"):
            rendered.append(f"{tasks_path}:{index}: {issue.render()}")

    if sources_path is not None:
        rendered.extend(_validate_sources_file(tasks, sources_path))
    if taxonomy_path is not None:
        rendered.extend(_validate_taxonomy_file(tasks, taxonomy_path))

    return len(tasks), rendered


def _validate_source_metadata(metadata: Mapping[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    _require_keys(metadata, REQUIRED_SOURCE_METADATA_KEYS, path, issues)
    for key in ("source_id", "title", "authors", "journal", "year", "license", "date_accessed", "figure_or_dataset_reference"):
        _validate_nonempty_string(metadata, key, f"{path}.{key}", issues)
    for key in ("doi", "pmid", "pmcid", "url"):
        if key in metadata and not isinstance(metadata.get(key), str):
            issues.append(ValidationIssue(f"{path}.{key}", "must be a string"))
    _validate_enum(metadata.get("commercial_use_status"), COMMERCIAL_USE_STATUSES, f"{path}.commercial_use_status", issues)
    _validate_enum(metadata.get("source_validation_status"), SOURCE_VALIDATION_STATUSES, f"{path}.source_validation_status", issues)


def _validate_gold(gold: Mapping[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    _require_keys(gold, REQUIRED_GOLD_KEYS, path, issues)
    for key in ("short_answer", "label", "detailed_rationale", "strongest_defensible_conclusion", "what_cannot_be_concluded", "uncertainty_notes"):
        _validate_nonempty_string(gold, key, f"{path}.{key}", issues)
    for key in ("evidence_used", "why_other_answers_are_wrong", "missing_controls_or_limitations", "alternative_explanations"):
        _validate_string_list(gold, key, f"{path}.{key}", issues, allow_empty=True)


def _validate_scoring(scoring: Mapping[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    _require_keys(scoring, REQUIRED_SCORING_KEYS, path, issues)
    _validate_nonempty_string(scoring, "primary_metric", f"{path}.primary_metric", issues)
    if not isinstance(scoring.get("automatic_checks_possible"), bool):
        issues.append(ValidationIssue(f"{path}.automatic_checks_possible", "must be a boolean"))
    if not isinstance(scoring.get("requires_expert_grading"), bool):
        issues.append(ValidationIssue(f"{path}.requires_expert_grading", "must be a boolean"))

    rubric = scoring.get("rubric")
    if not isinstance(rubric, list) or not rubric:
        issues.append(ValidationIssue(f"{path}.rubric", "must be a non-empty list"))
        return
    for index, criterion in enumerate(rubric):
        cpath = f"{path}.rubric[{index}]"
        if not isinstance(criterion, Mapping):
            issues.append(ValidationIssue(cpath, "must be an object"))
            continue
        _require_keys(criterion, {"criterion", "points", "description"}, cpath, issues)
        _validate_nonempty_string(criterion, "criterion", f"{cpath}.criterion", issues)
        _validate_nonempty_string(criterion, "description", f"{cpath}.description", issues)
        points = criterion.get("points")
        if not isinstance(points, int) or points <= 0:
            issues.append(ValidationIssue(f"{cpath}.points", "must be a positive integer"))


def _validate_expert_review(expert_review: Mapping[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    _require_keys(expert_review, REQUIRED_EXPERT_REVIEW_KEYS, path, issues)
    _validate_nonempty_string(expert_review, "created_by", f"{path}.created_by", issues)
    if not isinstance(expert_review.get("needs_expert_review"), bool):
        issues.append(ValidationIssue(f"{path}.needs_expert_review", "must be a boolean"))
    reviewers = expert_review.get("minimum_reviewers_required")
    if not isinstance(reviewers, int) or reviewers < 1:
        issues.append(ValidationIssue(f"{path}.minimum_reviewers_required", "must be a positive integer"))
    _validate_nonempty_string(expert_review, "review_priority", f"{path}.review_priority", issues)
    if not isinstance(expert_review.get("known_risks"), list):
        issues.append(ValidationIssue(f"{path}.known_risks", "must be a list"))


def _validate_sources_file(tasks: list[Mapping[str, Any]], sources_path: Path) -> list[str]:
    rendered: list[str] = []
    try:
        sources = load_json(sources_path)
    except (OSError, ValueError) as exc:
        return [f"{sources_path}: {exc}"]
    if not isinstance(sources, list):
        return [f"{sources_path}: $: must be a list"]
    source_ids = {source.get("source_id") for source in sources if isinstance(source, Mapping)}
    for task in tasks:
        for source_id in task.get("source_ids", []):
            if source_id not in source_ids:
                rendered.append(f"{sources_path}: missing source_id referenced by task: {source_id}")
    return rendered


def _validate_taxonomy_file(tasks: list[Mapping[str, Any]], taxonomy_path: Path) -> list[str]:
    try:
        taxonomy = load_json(taxonomy_path)
    except (OSError, ValueError) as exc:
        return [f"{taxonomy_path}: {exc}"]
    if not isinstance(taxonomy, Mapping):
        return [f"{taxonomy_path}: $: must be an object"]
    defined = set(taxonomy.keys())
    used: set[str] = set()
    for task in tasks:
        for label in task.get("failure_taxonomy", []):
            if isinstance(label, str):
                used.add(label)
    missing = sorted(used.difference(defined))
    return [f"{taxonomy_path}: missing failure taxonomy label: {label}" for label in missing]


def _require_keys(obj: Mapping[str, Any], required: set[str], path: str, issues: list[ValidationIssue]) -> None:
    for key in sorted(required.difference(obj.keys())):
        issues.append(ValidationIssue(f"{path}.{key}", "is required"))


def _validate_nonempty_string(obj: Mapping[str, Any], key: str, path: str, issues: list[ValidationIssue]) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(path, "must be a non-empty string"))


def _validate_string_list(
    obj: Mapping[str, Any],
    key: str,
    path: str,
    issues: list[ValidationIssue],
    *,
    allow_empty: bool = False,
) -> None:
    value = obj.get(key)
    if not isinstance(value, list):
        issues.append(ValidationIssue(path, "must be a list"))
        return
    if not allow_empty and not value:
        issues.append(ValidationIssue(path, "must be non-empty"))
        return
    if not all(isinstance(item, str) and item.strip() for item in value):
        issues.append(ValidationIssue(path, "must contain only non-empty strings"))


def _validate_enum(value: Any, allowed: set[str], path: str, issues: list[ValidationIssue]) -> None:
    if value not in allowed:
        issues.append(ValidationIssue(path, f"must be one of {sorted(allowed)}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate BioResearchAgentBench task packs.")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks.jsonl")
    parser.add_argument("--sources", type=Path, help="Optional sources.json for source ID checks")
    parser.add_argument("--taxonomy", type=Path, help="Optional failure_taxonomy.json for label checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    total, issues = validate_task_pack(args.tasks, sources_path=args.sources, taxonomy_path=args.taxonomy)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"FAILED: {len(issues)} issue(s) across {total} task(s)", file=sys.stderr)
        return 1
    print(f"OK: {total} BRAB task(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
