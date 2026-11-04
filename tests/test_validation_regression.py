import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from invoice_eval import evaluate_case, load_dataset, load_workflow
from invoice_eval.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"
VALIDATION_CASES = DATA_DIR / "04_无标注验证轨迹.jsonl"
WORKFLOW_PATH = DATA_DIR / "01_竞赛版流程字典.json"
VALIDATOR_PATH = DATA_DIR / "08_提交格式校验.py"


class ValidationRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(VALIDATION_CASES)
        cls.workflow = load_workflow(WORKFLOW_PATH)

    def test_validation_version_directions(self) -> None:
        expectations = {
            "INV-V01": "equal",
            "INV-V02": "candidate_better",
            "INV-V03": "baseline_better",
            "INV-V04": "candidate_better",
            "INV-V05": "baseline_better",
            "INV-V06": "equal",
            "INV-V07": "baseline_better",
            "INV-V08": "candidate_better",
        }
        for case in self.dataset.cases:
            with self.subTest(case_id=case.case_id):
                result = evaluate_case(case, self.workflow)
                self.assertEqual(
                    result["version_comparison"]["direction"],
                    expectations[case.case_id],
                )

    def test_context_update_uses_latest_amount(self) -> None:
        case = self.dataset.get_case("INV-V04")
        baseline = evaluate_case(case, self.workflow)[
            "run_assessments"
        ][0]
        self.assertFalse(baseline["agent_task_success"])
        self.assertEqual(baseline["quality_score"], 70)
        self.assertEqual(
            [
                root["label"]
                for root in baseline["root_causes"]
            ],
            ["CONTEXT_UPDATE"],
        )
        self.assertEqual(
            baseline["root_causes"][0]["first_fault_event_id"],
            "INV-V04-A-05",
        )

    def test_validation_output_passes_official_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "validation.jsonl"
            exit_code = main(
                [
                    "evaluate",
                    "--cases",
                    str(VALIDATION_CASES),
                    "--output",
                    str(output),
                    "--workflow",
                    str(WORKFLOW_PATH),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                len(output.read_text(encoding="utf-8").splitlines()),
                8,
            )

            checked = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--cases",
                    str(VALIDATION_CASES),
                    "--submission",
                    str(output),
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
