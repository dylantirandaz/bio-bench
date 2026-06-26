import json
import unittest
from pathlib import Path

from biofigure.validate import validate_files, validate_task


ROOT = Path(__file__).resolve().parents[1]


class ValidateTaskTests(unittest.TestCase):
    def test_fixture_file_validates_in_non_strict_mode(self) -> None:
        total, issues = validate_files([ROOT / "tests" / "fixtures" / "valid_fixture_tasks.jsonl"])
        self.assertEqual(total, 1)
        self.assertEqual(issues, [])

    def test_fixture_file_fails_in_strict_production_mode(self) -> None:
        total, issues = validate_files(
            [ROOT / "tests" / "fixtures" / "valid_fixture_tasks.jsonl"],
            strict_production=True,
        )
        self.assertEqual(total, 1)
        self.assertTrue(any("$.task_id" in issue for issue in issues))
        self.assertTrue(any("$.source.commercial_use_allowed" in issue for issue in issues))

    def test_invalid_gold_answer_is_rejected(self) -> None:
        record = self._fixture_record()
        record["gold_answer"] = "Maybe"
        issues = validate_task(record)
        self.assertTrue(any(issue.path == "$.gold_answer" for issue in issues))

    def test_two_expert_review_requires_two_reviewers(self) -> None:
        record = self._fixture_record()
        record["task_id"] = "BFC-000123"
        record["review_status"] = "two_expert_reviewed"
        record["source"]["pmcid"] = "PMC1234567"
        record["source"]["license"] = "CC BY"
        record["source"]["commercial_use_allowed"] = True
        record["review_metadata"]["reviewer_ids"] = ["expert-1"]
        issues = validate_task(record, strict_production=True)
        self.assertTrue(any("two_expert_reviewed" in issue.message for issue in issues))

    def _fixture_record(self) -> dict:
        path = ROOT / "tests" / "fixtures" / "valid_fixture_tasks.jsonl"
        return json.loads(path.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
