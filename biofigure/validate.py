"""Validate BioFigure task JSONL files without third-party dependencies."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from biofigure.spec import (
    AMBIGUITIES,
    ANSWER_CHOICES,
    DIFFICULTIES,
    FAILURE_TYPES,
    LICENSES,
    REVIEW_STATUSES,
    REVIEWED_STATUSES,
    SAFETY_LEVELS,
    TASK_TYPES,
)


PRODUCTION_TASK_ID_RE = re.compile(r"^BFC-\d{6}$")
FIXTURE_TASK_ID_RE = re.compile(r"^BFC-FIXTURE-\d{6}$")


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


def load_jsonl(path: Path) -> Iterable[tuple[int, Mapping[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record must be a JSON object")
            yield line_number, record


def validate_task(record: Mapping[str, Any], *, strict_production: bool = False) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    required_top_level = {
        "task_id",
        "source",
        "input",
        "question",
        "answer_choices",
        "gold_answer",
        "expert_rationale",
        "failure_type",
        "task_type",
        "difficulty",
        "ambiguity",
        "review_status",
        "safety_level",
        "review_metadata",
    }
    _require_keys(record, required_top_level, "$", issues)

    task_id = record.get("task_id")
    if not isinstance(task_id, str):
        issues.append(ValidationIssue("$.task_id", "must be a string"))
    elif strict_production:
        if not PRODUCTION_TASK_ID_RE.fullmatch(task_id):
            issues.append(ValidationIssue("$.task_id", "must match BFC-000000 in production"))
    elif not (PRODUCTION_TASK_ID_RE.fullmatch(task_id) or FIXTURE_TASK_ID_RE.fullmatch(task_id)):
        issues.append(ValidationIssue("$.task_id", "must match BFC-000000 or BFC-FIXTURE-000000"))

    source = record.get("source")
    if isinstance(source, Mapping):
        _validate_source(source, issues, strict_production=strict_production)
    else:
        issues.append(ValidationIssue("$.source", "must be an object"))

    task_input = record.get("input")
    if isinstance(task_input, Mapping):
        _validate_input(task_input, issues)
    else:
        issues.append(ValidationIssue("$.input", "must be an object"))

    _validate_nonempty_string(record, "question", "$.question", issues)
    _validate_nonempty_string(record, "expert_rationale", "$.expert_rationale", issues)

    answer_choices = record.get("answer_choices")
    if answer_choices != ANSWER_CHOICES:
        issues.append(ValidationIssue("$.answer_choices", f"must exactly equal {ANSWER_CHOICES!r}"))

    gold_answer = record.get("gold_answer")
    if gold_answer not in ANSWER_CHOICES:
        issues.append(ValidationIssue("$.gold_answer", "must be one of answer_choices"))

    _validate_enum(record, "task_type", TASK_TYPES, "$.task_type", issues)
    _validate_enum(record, "failure_type", FAILURE_TYPES, "$.failure_type", issues)
    _validate_enum(record, "difficulty", DIFFICULTIES, "$.difficulty", issues)
    _validate_enum(record, "ambiguity", AMBIGUITIES, "$.ambiguity", issues)
    _validate_enum(record, "review_status", REVIEW_STATUSES, "$.review_status", issues)
    _validate_enum(record, "safety_level", SAFETY_LEVELS, "$.safety_level", issues)

    review_metadata = record.get("review_metadata")
    if isinstance(review_metadata, Mapping):
        _validate_review_metadata(
            review_metadata,
            issues,
            review_status=record.get("review_status"),
            strict_production=strict_production,
        )
    else:
        issues.append(ValidationIssue("$.review_metadata", "must be an object"))

    if strict_production and record.get("review_status") == "fixture_not_for_training":
        issues.append(ValidationIssue("$.review_status", "fixture records are not production tasks"))

    if strict_production and record.get("safety_level") != "standard":
        issues.append(ValidationIssue("$.safety_level", "production export may include only standard-safe tasks"))

    return issues


def _validate_source(source: Mapping[str, Any], issues: list[ValidationIssue], *, strict_production: bool) -> None:
    required = {
        "source_id",
        "pmcid",
        "doi",
        "license",
        "commercial_use_allowed",
        "paper_title",
        "authors",
        "journal",
        "publication_year",
        "url",
        "date_accessed",
    }
    _require_keys(source, required, "$.source", issues)

    for key in ("source_id", "paper_title", "journal", "url"):
        _validate_nonempty_string(source, key, f"$.source.{key}", issues)

    license_value = source.get("license")
    if license_value not in LICENSES:
        issues.append(ValidationIssue("$.source.license", f"must be one of {sorted(LICENSES)}"))

    commercial_use_allowed = source.get("commercial_use_allowed")
    if not isinstance(commercial_use_allowed, bool):
        issues.append(ValidationIssue("$.source.commercial_use_allowed", "must be a boolean"))

    authors = source.get("authors")
    if not isinstance(authors, list) or not all(isinstance(author, str) and author for author in authors):
        issues.append(ValidationIssue("$.source.authors", "must be a non-empty list of strings"))

    year = source.get("publication_year")
    if not isinstance(year, int) or year < 1900 or year > dt.date.today().year + 1:
        issues.append(ValidationIssue("$.source.publication_year", "must be a plausible integer year"))

    _validate_date(source.get("date_accessed"), "$.source.date_accessed", issues)

    if strict_production:
        pmcid = source.get("pmcid")
        if not isinstance(pmcid, str) or not re.fullmatch(r"PMC\d+", pmcid):
            issues.append(ValidationIssue("$.source.pmcid", "must be a real PMC identifier like PMC1234567"))
        if source.get("license") == "Unknown":
            issues.append(ValidationIssue("$.source.license", "cannot be Unknown in production"))
        if source.get("commercial_use_allowed") is not True:
            issues.append(ValidationIssue("$.source.commercial_use_allowed", "must be true for production exports"))


def _validate_input(task_input: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    required = {
        "figure_id",
        "figure_panel",
        "caption",
        "relevant_excerpt",
        "claim",
        "evidence_assets",
    }
    _require_keys(task_input, required, "$.input", issues)

    for key in ("figure_id", "figure_panel", "caption", "relevant_excerpt", "claim"):
        _validate_nonempty_string(task_input, key, f"$.input.{key}", issues)

    evidence_assets = task_input.get("evidence_assets")
    if not isinstance(evidence_assets, list) or not evidence_assets:
        issues.append(ValidationIssue("$.input.evidence_assets", "must be a non-empty list"))
        return

    for index, asset in enumerate(evidence_assets):
        path = f"$.input.evidence_assets[{index}]"
        if not isinstance(asset, Mapping):
            issues.append(ValidationIssue(path, "must be an object"))
            continue
        _require_keys(asset, {"asset_type", "uri", "sha256"}, path, issues)
        if asset.get("asset_type") not in {"figure_image", "panel_crop", "supplement", "source_pdf", "html_snapshot"}:
            issues.append(ValidationIssue(f"{path}.asset_type", "has an unsupported asset_type"))
        _validate_nonempty_string(asset, "uri", f"{path}.uri", issues)
        sha256 = asset.get("sha256")
        if not isinstance(sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}|PENDING", sha256):
            issues.append(ValidationIssue(f"{path}.sha256", "must be a SHA-256 hex digest or PENDING"))


def _validate_review_metadata(
    metadata: Mapping[str, Any],
    issues: list[ValidationIssue],
    *,
    review_status: Any,
    strict_production: bool,
) -> None:
    required = {
        "created_by",
        "created_at",
        "reviewer_ids",
        "adjudicator_id",
        "review_notes",
    }
    _require_keys(metadata, required, "$.review_metadata", issues)

    _validate_nonempty_string(metadata, "created_by", "$.review_metadata.created_by", issues)
    _validate_date(metadata.get("created_at"), "$.review_metadata.created_at", issues)

    reviewer_ids = metadata.get("reviewer_ids")
    if not isinstance(reviewer_ids, list) or not all(isinstance(item, str) and item for item in reviewer_ids):
        issues.append(ValidationIssue("$.review_metadata.reviewer_ids", "must be a list of reviewer ID strings"))
        reviewer_count = 0
    else:
        reviewer_count = len(reviewer_ids)

    adjudicator_id = metadata.get("adjudicator_id")
    if adjudicator_id is not None and not isinstance(adjudicator_id, str):
        issues.append(ValidationIssue("$.review_metadata.adjudicator_id", "must be null or a string"))

    review_notes = metadata.get("review_notes")
    if not isinstance(review_notes, str):
        issues.append(ValidationIssue("$.review_metadata.review_notes", "must be a string"))

    if review_status in REVIEWED_STATUSES and reviewer_count < 1:
        issues.append(ValidationIssue("$.review_metadata.reviewer_ids", "reviewed tasks need at least one reviewer"))
    if review_status == "two_expert_reviewed" and reviewer_count < 2:
        issues.append(ValidationIssue("$.review_metadata.reviewer_ids", "two_expert_reviewed tasks need two reviewers"))
    if review_status == "adjudicated" and not adjudicator_id:
        issues.append(ValidationIssue("$.review_metadata.adjudicator_id", "adjudicated tasks need an adjudicator"))
    if strict_production and review_status not in REVIEWED_STATUSES:
        issues.append(ValidationIssue("$.review_status", "production tasks must be expert reviewed or adjudicated"))


def _require_keys(
    obj: Mapping[str, Any],
    required: set[str],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    missing = sorted(required.difference(obj.keys()))
    for key in missing:
        issues.append(ValidationIssue(f"{path}.{key}", "is required"))


def _validate_enum(
    obj: Mapping[str, Any],
    key: str,
    allowed: set[str],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    value = obj.get(key)
    if value not in allowed:
        issues.append(ValidationIssue(path, f"must be one of {sorted(allowed)}"))


def _validate_nonempty_string(
    obj: Mapping[str, Any],
    key: str,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(path, "must be a non-empty string"))


def _validate_date(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, str):
        issues.append(ValidationIssue(path, "must be a YYYY-MM-DD string"))
        return
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        issues.append(ValidationIssue(path, "must be a valid YYYY-MM-DD date"))


def validate_files(paths: list[Path], *, strict_production: bool = False) -> tuple[int, list[str]]:
    total_records = 0
    rendered_issues: list[str] = []

    for path in paths:
        try:
            records = list(load_jsonl(path))
        except ValueError as exc:
            rendered_issues.append(str(exc))
            continue

        for line_number, record in records:
            total_records += 1
            issues = validate_task(record, strict_production=strict_production)
            for issue in issues:
                rendered_issues.append(f"{path}:{line_number}: {issue.render()}")

    return total_records, rendered_issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate BioFigure JSONL task files.")
    parser.add_argument("paths", nargs="+", type=Path, help="JSONL task files to validate")
    parser.add_argument(
        "--strict-production",
        action="store_true",
        help="Reject fixtures, unknown licenses, non-commercial licenses, and unreviewed tasks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    total_records, issues = validate_files(args.paths, strict_production=args.strict_production)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"FAILED: {len(issues)} issue(s) across {total_records} record(s)", file=sys.stderr)
        return 1

    print(f"OK: {total_records} record(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
