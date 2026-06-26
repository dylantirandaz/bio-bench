"""Schema constants for BioResearchAgentBench-v0."""

from __future__ import annotations

import re


BENCHMARK_NAME = "BioResearchAgentBench-v0"

MODULES = {
    "biofigure_claimcheck": "BRAB-FIG",
    "biodatascience_reprobench": "BRAB-DATA",
    "bioimage_artifact_vs_biology": "BRAB-IMG",
    "literature_contradiction_synthesis": "BRAB-LIT",
    "experimental_design_control_critic": "BRAB-CTRL",
}

TASK_ID_RE = re.compile(r"^BRAB-(FIG|DATA|IMG|LIT|CTRL)-\d{3}$")

DIFFICULTIES = {"hard", "expert", "adversarial"}
AMBIGUITIES = {"low", "medium", "high"}
SAFETY_LEVELS = {"safe", "caution", "exclude"}
COMMERCIAL_USE_STATUSES = {"allowed", "likely_allowed", "noncommercial_only", "unclear", "needs_review"}
SOURCE_VALIDATION_STATUSES = {
    "fully_validated",
    "text_validated_only",
    "figure_needs_manual_validation",
    "dataset_needs_manual_validation",
    "license_needs_review",
}

REQUIRED_TASK_KEYS = {
    "benchmark_name",
    "task_id",
    "module",
    "task_type",
    "domain",
    "subdomain",
    "difficulty",
    "ambiguity",
    "safety_level",
    "source_ids",
    "source_metadata",
    "input_artifacts",
    "prompt_to_model",
    "answer_format_required",
    "answer_choices",
    "gold_answer",
    "scoring",
    "failure_taxonomy",
    "why_strong_llms_fail",
    "adversarial_features",
    "expert_review",
}

REQUIRED_SOURCE_METADATA_KEYS = {
    "source_id",
    "title",
    "authors",
    "journal",
    "year",
    "doi",
    "pmid",
    "pmcid",
    "url",
    "license",
    "commercial_use_status",
    "date_accessed",
    "figure_or_dataset_reference",
    "source_validation_status",
}

REQUIRED_INPUT_ARTIFACT_KEYS = {
    "figure_panel",
    "caption_excerpt",
    "paper_excerpt",
    "dataset_description",
    "metadata_summary",
    "image_description",
    "paper_cluster_summary",
    "experimental_scenario",
}

REQUIRED_GOLD_KEYS = {
    "short_answer",
    "label",
    "detailed_rationale",
    "evidence_used",
    "why_other_answers_are_wrong",
    "missing_controls_or_limitations",
    "alternative_explanations",
    "strongest_defensible_conclusion",
    "what_cannot_be_concluded",
    "uncertainty_notes",
}

REQUIRED_SCORING_KEYS = {
    "primary_metric",
    "rubric",
    "automatic_checks_possible",
    "requires_expert_grading",
}

REQUIRED_EXPERT_REVIEW_KEYS = {
    "created_by",
    "needs_expert_review",
    "minimum_reviewers_required",
    "review_priority",
    "known_risks",
}
