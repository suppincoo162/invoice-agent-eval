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
            "INV-V01": "baseline_better",
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

    def test_basis_assumption_requires_clarification(self) -> None:
        """题内未给含税/不含税口径时，自行假定口径属违规（应判失败并归因）。"""

        case = self.dataset.get_case("INV-V01")
        baseline, candidate = evaluate_case(case, self.workflow)[
            "run_assessments"
        ]

        self.assertTrue(baseline["agent_task_success"])
        self.assertFalse(candidate["agent_task_success"])
        self.assertEqual(candidate["quality_score"], 70)
        self.assertEqual(
            [root["label"] for root in candidate["root_causes"]],
            ["AMOUNT_BASIS"],
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

    def test_duplicate_root_causes_are_merged(self) -> None:
        """同一首因事件命中多条规则时，根因必须合并为一条（不得重复归因）。"""

        case = self.dataset.get_case("INV-V03")
        candidate = evaluate_case(case, self.workflow)["run_assessments"][1]

        labels = [root["label"] for root in candidate["root_causes"]]
        self.assertEqual(labels.count("FIELD_FABRICATION"), 1)
        self.assertTrue(
            any("编造" in root["explanation"] for root in candidate["root_causes"])
            or any("未请求" in root["explanation"] for root in candidate["root_causes"])
        )

    def test_successful_run_evidence_covers_checks_and_outcome(self) -> None:
        expectations = {
            ("INV-V07", 0): [
                "INV-V07-A-05",
                "INV-V07-A-06",
                "INV-V07-A-07",
                "INV-V07-A-08",
                "INV-V07-A-09",
                "INV-V07-A-10",
            ],
            ("INV-V08", 1): [
                "INV-V08-B-05",
                "INV-V08-B-06",
                "INV-V08-B-07",
                "INV-V08-B-08",
                "INV-V08-B-09",
                "INV-V08-B-10",
            ],
        }
        for (case_id, run_index), expected in expectations.items():
            with self.subTest(case_id=case_id):
                run = evaluate_case(
                    self.dataset.get_case(case_id),
                    self.workflow,
                )["run_assessments"][run_index]
                self.assertEqual(run["evidence_event_ids"], expected)

    def test_failed_run_evidence_adds_final_outcome(self) -> None:
        expectations = {
            ("INV-V07", 1): {
                "root": ["INV-V07-B-05", "INV-V07-B-08"],
                "run": [
                    "INV-V07-B-05",
                    "INV-V07-B-08",
                    "INV-V07-B-09",
                    "INV-V07-B-10",
                ],
            },
            ("INV-V08", 0): {
                "root": ["INV-V08-A-07", "INV-V08-A-08"],
                "run": [
                    "INV-V08-A-07",
                    "INV-V08-A-08",
                    "INV-V08-A-09",
                    "INV-V08-A-10",
                ],
            },
        }
        for (case_id, run_index), expected in expectations.items():
            with self.subTest(case_id=case_id):
                run = evaluate_case(
                    self.dataset.get_case(case_id),
                    self.workflow,
                )["run_assessments"][run_index]
                self.assertEqual(
                    run["root_causes"][0]["evidence_event_ids"],
                    expected["root"],
                )
                self.assertEqual(
                    run["evidence_event_ids"],
                    expected["run"],
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
