import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from invoice_eval import evaluate_case, load_dataset, load_workflow
from invoice_eval.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"
TRAINING_CASES = DATA_DIR / "02_公开训练轨迹.jsonl"
WORKFLOW_PATH = DATA_DIR / "01_竞赛版流程字典.json"
VALIDATOR_PATH = DATA_DIR / "08_提交格式校验.py"


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(TRAINING_CASES)
        cls.workflow = load_workflow(WORKFLOW_PATH)
        cls.case = cls.dataset.get_case("INV-T01")

    def test_evaluates_inv_t01_end_to_end(self) -> None:
        result = evaluate_case(self.case, self.workflow)
        baseline, candidate = result["run_assessments"]

        self.assertEqual(baseline["run_id"], "INV-T01-A")
        self.assertTrue(baseline["agent_task_success"])
        self.assertFalse(baseline["business_invoice_created"])
        self.assertEqual(baseline["quality_score"], 100)
        self.assertEqual(baseline["root_causes"], [])
        self.assertEqual(baseline["penalty_items"], [])

        self.assertEqual(candidate["run_id"], "INV-T01-B")
        self.assertFalse(candidate["agent_task_success"])
        self.assertFalse(candidate["business_invoice_created"])
        self.assertEqual(candidate["quality_score"], 20)
        self.assertEqual(
            {
                root["label"]: root["first_fault_event_id"]
                for root in candidate["root_causes"]
            },
            {
                "AMOUNT_BASIS": "INV-T01-B-05",
                "CONFIRMATION_BYPASS": "INV-T01-B-08",
            },
        )
        self.assertEqual(
            [
                penalty["points_deducted"]
                for penalty in candidate["penalty_items"]
            ],
            [30, 50],
        )
        self.assertTrue(candidate["improvement_suggestions"])
        self.assertTrue(
            all(
                event_id.startswith("INV-T01-B-")
                for event_id in candidate["evidence_event_ids"]
            )
        )
        self.assertEqual(
            result["version_comparison"]["direction"],
            "baseline_better",
        )
        self.assertEqual(
            result["version_comparison"]["release_recommendation"],
            "defer",
        )

    def test_cli_writes_schema_valid_inv_t01_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "submission.jsonl"
            exit_code = main(
                [
                    "evaluate",
                    "--cases",
                    str(TRAINING_CASES),
                    "--output",
                    str(output),
                    "--workflow",
                    str(WORKFLOW_PATH),
                    "--case-id",
                    "INV-T01",
                ]
            )

            self.assertEqual(exit_code, 0)
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["case_id"], "INV-T01")

            checked = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--cases",
                    str(TRAINING_CASES),
                    "--submission",
                    str(output),
                    "--allow-partial",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                checked.returncode,
                0,
                checked.stdout + checked.stderr,
            )
            self.assertIn("格式检查通过", checked.stdout)


if __name__ == "__main__":
    unittest.main()
