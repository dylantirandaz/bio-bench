import json
import tempfile
import unittest
from pathlib import Path

from brab.baseline import write_baseline_outputs
from brab.io import load_jsonl, write_jsonl
from brab.prompts import export_prompt_pack
from brab.score import normalize_label, score_outputs
from brab.validate import validate_task_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class BrabRunnerTests(unittest.TestCase):
    def test_task_pack_validates_with_sources_and_taxonomy(self) -> None:
        total, issues = validate_task_pack(
            FIXTURES / "brab_tasks.jsonl",
            sources_path=FIXTURES / "brab_sources.json",
            taxonomy_path=FIXTURES / "brab_taxonomy.json",
        )
        self.assertEqual(total, 2)
        self.assertEqual(issues, [])

    def test_prompt_export_does_not_include_gold_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "prompts.jsonl"
            total = export_prompt_pack(FIXTURES / "brab_tasks.jsonl", out)
            prompts = load_jsonl(out)
        self.assertEqual(total, 2)
        self.assertEqual(len(prompts), 2)
        rendered = json.dumps(prompts[0])
        self.assertIn("Classify the fixture claim.", rendered)
        self.assertNotIn("gold_answer", rendered)
        self.assertNotIn("The fixture claim is stronger", rendered)

    def test_score_outputs_writes_report_and_training_data(self) -> None:
        outputs = [
            {
                "task_id": "BRAB-FIG-001",
                "model_name": "fixture-model",
                "label": "C. Overclaimed",
                "answer": "C. Overclaimed",
                "rationale": "Fixture rationale.",
            },
            {
                "task_id": "BRAB-LIT-001",
                "model_name": "fixture-model",
                "label": "supported",
                "answer": "supported",
                "rationale": "Fixture wrong rationale.",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outputs_path = tmp / "outputs.jsonl"
            out_dir = tmp / "score"
            write_jsonl(outputs_path, outputs)
            report = score_outputs(FIXTURES / "brab_tasks.jsonl", outputs_path, out_dir)
            training_examples = load_jsonl(out_dir / "targeted_training_data.jsonl")
            self.assertTrue((out_dir / "scores.json").exists())
            self.assertTrue((out_dir / "failure_report.md").exists())
        self.assertEqual(report["summary"]["correct"], 1)
        self.assertEqual(report["summary"]["label_accuracy"], 0.5)
        self.assertEqual(len(training_examples), 1)
        self.assertEqual(training_examples[0]["task_id"], "BRAB-LIT-001")

    def test_baseline_outputs_match_task_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "baseline.jsonl"
            total = write_baseline_outputs(FIXTURES / "brab_tasks.jsonl", out, strategy="always_uncertain")
            outputs = load_jsonl(out)
        self.assertEqual(total, 2)
        self.assertEqual(len(outputs), 2)

    def test_label_normalization(self) -> None:
        self.assertEqual(normalize_label("C. Overclaimed"), "overclaimed")
        self.assertEqual(normalize_label("Overclaimed / not supported"), "overclaimed")


if __name__ == "__main__":
    unittest.main()
