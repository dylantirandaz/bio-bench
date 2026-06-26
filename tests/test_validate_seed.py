import unittest

from biofigure.validate_seed import validate_seed_dataset


class ValidateSeedDatasetTests(unittest.TestCase):
    def test_valid_seed_dataset_passes(self) -> None:
        data = {
            "dataset_name": "BioFigure-ClaimCheck-1_seed_v0.1",
            "created_at": "2026-06-26",
            "purpose": "Fixture seed dataset.",
            "important_caveats": ["Fixture only."],
            "recommended_next_validation_steps": ["Expert review."],
            "schema_version": "0.1",
            "sources": [
                {
                    "paper_id": "P01",
                    "title": "Fixture paper",
                    "authors_short": "Fixture et al.",
                    "year": 2026,
                    "journal": "Fixture Journal",
                    "doi": "10.0000/fixture",
                    "pmcid": None,
                    "url": "https://example.org/paper",
                    "license": "License pending verification",
                    "source_status": "first_pass",
                    "source_evidence_refs": ["fixture-ref"],
                    "domain_tags": ["cell biology"],
                }
            ],
            "tasks": [
                {
                    "task_id": "P01-T01",
                    "paper_id": "P01",
                    "task_type": "claim_verification",
                    "difficulty": "extreme",
                    "ambiguity_rating": "low",
                    "figure_grounding": "Fixture figure grounding.",
                    "prompt": "Classify the fixture claim.",
                    "answer_format": "multiple_choice_with_required_rationale",
                    "answer_choices": ["Supported", "Overclaimed"],
                    "gold_answer": "Overclaimed",
                    "expert_rationale": "Fixture rationale.",
                    "failure_taxonomy": ["causality_overclaim"],
                    "why_strong_llms_are_likely_to_fail": "Fixture reason.",
                    "validation_status": "first_pass_expert_drafted",
                }
            ],
            "summary_counts": {
                "sources_total": 1,
                "tasks_total": 1,
                "tasks_per_paper": 1,
            },
        }
        self.assertEqual(validate_seed_dataset(data), [])

    def test_task_must_reference_source(self) -> None:
        data = {
            "dataset_name": "BioFigure-ClaimCheck-1_seed_v0.1",
            "created_at": "2026-06-26",
            "purpose": "Fixture seed dataset.",
            "important_caveats": ["Fixture only."],
            "recommended_next_validation_steps": ["Expert review."],
            "schema_version": "0.1",
            "sources": [
                {
                    "paper_id": "P01",
                    "title": "Fixture paper",
                    "authors_short": "Fixture et al.",
                    "year": 2026,
                    "journal": "Fixture Journal",
                    "doi": "10.0000/fixture",
                    "pmcid": None,
                    "url": "https://example.org/paper",
                    "license": "License pending verification",
                    "source_status": "first_pass",
                    "source_evidence_refs": ["fixture-ref"],
                    "domain_tags": ["cell biology"],
                }
            ],
            "tasks": [
                {
                    "task_id": "P02-T01",
                    "paper_id": "P02",
                    "task_type": "claim_verification",
                    "difficulty": "extreme",
                    "ambiguity_rating": "low",
                    "figure_grounding": "Fixture figure grounding.",
                    "prompt": "Classify the fixture claim.",
                    "answer_format": "multiple_choice_with_required_rationale",
                    "answer_choices": ["Supported", "Overclaimed"],
                    "gold_answer": "Overclaimed",
                    "expert_rationale": "Fixture rationale.",
                    "failure_taxonomy": ["causality_overclaim"],
                    "why_strong_llms_are_likely_to_fail": "Fixture reason.",
                    "validation_status": "first_pass_expert_drafted",
                }
            ],
            "summary_counts": {
                "sources_total": 1,
                "tasks_total": 1,
                "tasks_per_paper": 1,
            },
        }
        issues = validate_seed_dataset(data)
        self.assertTrue(any(issue.path.endswith(".paper_id") for issue in issues))


if __name__ == "__main__":
    unittest.main()
