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
    validate_rubric_report,
    write_rubric_report,
)
from invoice_eval.models import Event, Run
from invoice_eval.rubric import _impact_cap_reasons


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
            cap_evidence = {
                event_id
                for reason in run["cap_reasons"]
                for event_id in reason["evidence_event_ids"]
            }
            self.assertIn(
                "INV-V07-B-09"
                if run_id == "INV-V07-B"
                else "INV-V08-A-09",
                cap_evidence,
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

    def test_duplicate_cap_requires_submit_after_risk(self) -> None:
        risk = Event(
            "TEST-06",
            6,
            "VALIDATE_DATA",
            "SUCCEEDED",
            {},
        )
        submit_after = Event(
            "TEST-08",
            8,
            "SUBMIT_INVOICE",
            "SUCCEEDED",
            {},
        )
        run_after = Run(
            "TEST",
            (risk, submit_after),
            {risk.event_id: risk, submit_after.event_id: submit_after},
            {},
        )
        assessment = {
            "business_invoice_created": False,
            "root_causes": [
                {
                    "label": "DUPLICATE_CONTROL",
                    "first_fault_event_id": risk.event_id,
                    "evidence_event_ids": [risk.event_id],
                }
            ],
        }
        reasons = _impact_cap_reasons(
            run_after,
            assessment,
            assessment["root_causes"],
        )
        self.assertIn(
            "DUPLICATE_RISK_SUBMITTED",
            {reason["reason"] for reason in reasons},
        )

        submit_before = Event(
            "TEST-04",
            4,
            "SUBMIT_INVOICE",
            "SUCCEEDED",
            {},
        )
        run_before = Run(
            "TEST",
            (submit_before, risk),
            {submit_before.event_id: submit_before, risk.event_id: risk},
            {},
        )
        reasons = _impact_cap_reasons(
            run_before,
            assessment,
            assessment["root_causes"],
        )
        self.assertNotIn(
            "DUPLICATE_RISK_SUBMITTED",
            {reason["reason"] for reason in reasons},
        )

    def test_multiple_caps_use_minimum(self) -> None:
        events = (
            Event("TEST-05", 5, "COLLECT_INVOICE_DATA", "SUCCEEDED", {}),
            Event("TEST-06", 6, "VALIDATE_DATA", "SUCCEEDED", {}),
            Event("TEST-08", 8, "SUBMIT_INVOICE", "SUCCEEDED", {}),
            Event("TEST-09", 9, "WAIT_INVOICE_CALLBACK", "SUCCEEDED", {}),
            Event("TEST-10", 10, "COMPLETE_TASK", "SUCCEEDED", {}),
        )
        run = Run(
            "TEST",
            events,
            {event.event_id: event for event in events},
            {},
        )
        roots = [
            {
                "label": "DUPLICATE_CONTROL",
                "first_fault_event_id": "TEST-06",
                "evidence_event_ids": ["TEST-06"],
            },
            {
                "label": "AMOUNT_CALCULATION",
                "first_fault_event_id": "TEST-05",
                "evidence_event_ids": ["TEST-05"],
            },
            {
                "label": "CALLBACK_MISINTERPRETATION",
                "first_fault_event_id": "TEST-09",
                "evidence_event_ids": ["TEST-09"],
            },
        ]
        assessment = {
            "business_invoice_created": True,
            "root_causes": roots,
        }
        reasons = _impact_cap_reasons(run, assessment, roots)

        self.assertEqual(min(reason["cap"] for reason in reasons), 10)

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
            source_submission_sha256="test-sha",
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
        self.assertEqual(
            first_line["source_submission_sha256"],
            "test-sha",
        )

    def test_maps_reversed_run_order_by_run_id(self) -> None:
        submission = copy.deepcopy(self.validation_submission)
        runs = submission["INV-V07"]["run_assessments"]
        runs.reverse()
        report = build_rubric_report(self.validation, submission)
        case = next(
            row for row in report if row["case_id"] == "INV-V07"
        )

        self.assertEqual(
            [run["run_id"] for run in case["run_assessments"]],
            ["INV-V07-A", "INV-V07-B"],
        )
        candidate = case["run_assessments"][1]
        self.assertEqual(candidate["impact_cap"], 20)
        self.assertEqual(candidate["rubric_score"], 20)

    def test_preserves_fractional_quality_score(self) -> None:
        submission = copy.deepcopy(self.validation_submission)
        run = submission["INV-V07"]["run_assessments"][0]
        run["quality_score"] = 82.5
        rows = build_rubric_report(self.validation, submission)
        result = next(
            item
            for row in rows
            if row["case_id"] == "INV-V07"
            for item in row["run_assessments"]
            if item["run_id"] == "INV-V07-A"
        )

        self.assertEqual(result["quality_score"], 82.5)
        self.assertEqual(result["rubric_score"], 82.5)

    def test_rejects_malformed_rubric_and_wrong_source_hash(self) -> None:
        rows = build_rubric_report(
            self.validation,
            self.validation_submission,
            source_submission_sha256="source-a",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rubric.jsonl"
            rows[0]["run_assessments"] = rows[0]["run_assessments"][:1]
            write_rubric_report(rows, path)
            with self.assertRaisesRegex(ValueError, "exactly two runs"):
                load_rubric_report(path)

        rows = build_rubric_report(
            self.validation,
            self.validation_submission,
            source_submission_sha256="source-a",
        )
        rubric = {row["case_id"]: row for row in rows}
        with self.assertRaisesRegex(ValueError, "source submission hash"):
            validate_rubric_report(
                self.validation,
                self.validation_submission,
                rubric,
                source_submission_sha256="source-b",
            )

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
