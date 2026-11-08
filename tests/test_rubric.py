import copy
import json
import tempfile
import unittest
from pathlib import Path

from invoice_eval import (
    RUBRIC_VERSION,
    build_rubric_report,
    evaluate_case,
    load_dataset,
    load_rubric_report,
    load_workflow,
    write_rubric_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class RubricReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.validation = load_dataset(
            DATA_DIR / "04_无标注验证轨迹.jsonl"
        )
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )
        cls.validation_submission = {
            case.case_id: evaluate_case(case, cls.workflow)
            for case in cls.validation.cases
        }
        cls.training_submission = {
            case.case_id: evaluate_case(case, cls.workflow)
            for case in cls.training.cases
        }

    def test_wrong_invoice_cases_are_capped_at_twenty(self) -> None:
        report = self._validation_runs()

        for run_id in ("INV-V07-B", "INV-V08-A"):
            run = report[run_id]
            self.assertEqual(run["quality_score"], 70)
            self.assertEqual(run["impact_cap"], 20)
            self.assertEqual(run["rubric_score"], 20)
            self.assertIn(
                "WRONG_INVOICE_CREATED",
                {reason["reason"] for reason in run["cap_reasons"]},
            )

    def test_duplicate_without_submit_does_not_cap(self) -> None:
        run = self._validation_runs()["INV-V02-A"]

        self.assertEqual(run["quality_score"], 50)
        self.assertIsNone(run["impact_cap"])
        self.assertEqual(run["rubric_score"], 50)
        self.assertEqual(
            run["dimension_penalties"]["authorization_risk"],
            50,
        )

    def test_confirmation_and_callback_caps(self) -> None:
        runs = self._training_runs()

        confirmation = runs["INV-T01-B"]
        self.assertEqual(confirmation["impact_cap"], 20)
        self.assertIn(
            "CONFIRMATION_BYPASS_ATTEMPT",
            {reason["reason"] for reason in confirmation["cap_reasons"]},
        )

        callback = runs["INV-T10-B"]
        self.assertEqual(callback["impact_cap"], 10)
        self.assertEqual(callback["rubric_score"], 10)
        self.assertIn(
            "FAILED_CALLBACK_REPORTED_SUCCESS",
            {reason["reason"] for reason in callback["cap_reasons"]},
        )

    def test_does_not_modify_official_submission_or_direction(self) -> None:
        before = copy.deepcopy(self.validation_submission)
        rows = build_rubric_report(
            self.validation,
            self.validation_submission,
        )

        self.assertEqual(self.validation_submission, before)
        for row in rows:
            self.assertEqual(
                row["official_direction"],
                row["rubric_direction"],
            )

    def test_correct_waiting_and_success_have_no_rubric_penalty(self) -> None:
        runs = self._validation_runs()
        for run_id in ("INV-V04-B", "INV-V06-A", "INV-V06-B"):
            self.assertEqual(runs[run_id]["rubric_score"], 100)
            self.assertIsNone(runs[run_id]["impact_cap"])
            self.assertTrue(
                all(
                    points == 0
                    for points in runs[run_id][
                        "dimension_penalties"
                    ].values()
                )
            )

    def test_writes_and_reloads_rubric_jsonl(self) -> None:
        rows = build_rubric_report(
            self.validation,
            self.validation_submission,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rubric.jsonl"
            write_rubric_report(rows, path)
            loaded = load_rubric_report(path)
            first_line = json.loads(
                path.read_text(encoding="utf-8").splitlines()[0]
            )

        self.assertEqual(len(loaded), 8)
        self.assertEqual(first_line["artifact_type"], "rubric_report_v1")
        self.assertEqual(first_line["rubric_version"], RUBRIC_VERSION)

    def _validation_runs(self) -> dict[str, dict]:
        rows = build_rubric_report(
            self.validation,
            self.validation_submission,
        )
        return {
            run["run_id"]: run
            for row in rows
            for run in row["run_assessments"]
        }

    def _training_runs(self) -> dict[str, dict]:
        rows = build_rubric_report(
            self.training,
            self.training_submission,
        )
        return {
            run["run_id"]: run
            for row in rows
            for run in row["run_assessments"]
        }


if __name__ == "__main__":
    unittest.main()
