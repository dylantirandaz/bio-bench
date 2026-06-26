"""Shared constants for BioFigure task records."""

ANSWER_CHOICES = [
    "Supported",
    "Contradicted",
    "Overclaimed",
    "Not verifiable from provided evidence",
]

TASK_TYPES = {
    "claim_support",
    "panel_identification",
    "missing_control",
    "causal_vs_correlational",
    "entity_check",
    "alternative_explanation",
    "scientific_caution",
    "limitation_identification",
    "caption_contradiction",
    "evidence_sufficiency",
}

FAILURE_TYPES = {
    "supported_claim",
    "causality_overclaim",
    "wrong_entity",
    "missing_control",
    "figure_misread",
    "unsupported_mechanism",
    "statistical_overclaim",
    "assay_limitation",
    "citation_hallucination",
    "not_enough_evidence_failure",
    "contradicted_by_evidence",
    "ambiguous_evidence",
    "other",
}

DIFFICULTIES = {"easy", "medium", "hard"}
AMBIGUITIES = {"low", "medium", "high"}

REVIEW_STATUSES = {
    "draft",
    "candidate_ai_generated",
    "single_expert_reviewed",
    "two_expert_reviewed",
    "adjudicated",
    "rejected",
    "fixture_not_for_training",
}

SAFETY_LEVELS = {
    "standard",
    "dual_use_review",
    "unsafe_reject",
}

LICENSES = {
    "CC BY",
    "CC BY-SA",
    "CC BY-ND",
    "CC BY-NC",
    "CC BY-NC-SA",
    "CC BY-NC-ND",
    "CC0",
    "Public Domain",
    "Other",
    "Unknown",
}

REVIEWED_STATUSES = {
    "single_expert_reviewed",
    "two_expert_reviewed",
    "adjudicated",
}
