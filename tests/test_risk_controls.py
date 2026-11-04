import unittest
from pathlib import Path

from invoice_eval import (
    evaluate_case,
    find_cancellation_root_causes,
    find_duplicate_control_root_causes,
    find_submit_timeout_root_causes,
    load_dataset,
    load_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class RiskControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.validation = load_dataset(DATA_DIR / "04_无标注验证轨迹.jsonl")
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )

    def test_duplicate_risk_is_blocked_correctly(self) -> None:
        case = self.training.get_case("INV-T05")
        self.assertEqual(
            find_duplicate_control_root_causes(
                case, case.get_run("INV-T05-A")
            ),
            (),
        )

    def test_duplicate_risk_suppression_is_fault(self) -> None:
        case = self.training.get_case("INV-T05")
        roots = find_duplicate_control_root_causes(
            case, case.get_run("INV-T05-B")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "DUPLICATE_CONTROL")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T05-B-06",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T05-B-06", "INV-T05-B-07"),
        )

    def test_duplicate_combined_validation_scenario(self) -> None:
        case = self.validation.get_case("INV-V02")
        roots = find_duplicate_control_root_causes(
            case, case.get_run("INV-V02-A")
        )

        self.assertEqual(
            [root.label for root in roots],
            ["DUPLICATE_CONTROL"],
        )

    def test_cancel_intent_error(self) -> None:
        case = self.training.get_case("INV-T09")
        roots = find_cancellation_root_causes(
            case, case.get_run("INV-T09-A")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "INTENT_CLASSIFICATION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T09-A-04",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T09-A-04", "INV-T09-A-08"),
        )

    def test_correct_cancel_has_no_finding(self) -> None:
        case = self.training.get_case("INV-T09")
        self.assertEqual(
            find_cancellation_root_causes(
                case, case.get_run("INV-T09-B")
            ),
            (),
        )

    def test_unknown_submit_without_retry_is_not_fault(self) -> None:
        case = self.training.get_case("INV-T08")
        self.assertEqual(
            find_submit_timeout_root_causes(
                case.get_run("INV-T08-A")
            ),
            (),
        )

    def test_unknown_submit_with_unstable_retry_is_fault(self) -> None:
        case = self.training.get_case("INV-T08")
        roots = find_submit_timeout_root_causes(
            case.get_run("INV-T08-B")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "TOOL_ERROR_HANDLING")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T08-B-08",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T08-B-08", "INV-T08-B-09"),
        )

    def test_idempotency_key_alone_does_not_authorize_unknown_retry(
        self,
    ) -> None:
        case = self.training.get_case("INV-T08")
        run = case.get_run("INV-T08-B")
        submit = run.get_event("INV-T08-B-08")
        keys = [
            call["arguments"]["idempotency_key"]
            for call in submit.raw["tool_calls"]
        ]
        try:
            for call in submit.raw["tool_calls"]:
                call["arguments"]["idempotency_key"] = "STABLE-KEY"
            roots = find_submit_timeout_root_causes(run)
        finally:
            for call, key in zip(submit.raw["tool_calls"], keys):
                call["arguments"]["idempotency_key"] = key

        self.assertEqual(
            [root.label for root in roots],
            ["TOOL_ERROR_HANDLING"],
        )

    def test_t006_cases_end_to_end(self) -> None:
        expectations = {
            "INV-T05": ("baseline_better", True, False, 100, 50),
            "INV-T08": ("baseline_better", True, False, 100, 50),
            "INV-T09": ("candidate_better", False, True, 70, 100),
        }
        for case_id, expected in expectations.items():
            with self.subTest(case_id=case_id):
                result = evaluate_case(
                    self.training.get_case(case_id),
                    self.workflow,
                )
                baseline, candidate = result["run_assessments"]
                self.assertEqual(
                    (
                        result["version_comparison"]["direction"],
                        baseline["agent_task_success"],
                        candidate["agent_task_success"],
                        baseline["quality_score"],
                        candidate["quality_score"],
                    ),
                    expected,
                )
                if case_id == "INV-T09":
                    self.assertEqual(
                        [
                            root["label"]
                            for root in baseline["root_causes"]
                        ],
                        ["INTENT_CLASSIFICATION"],
                    )


if __name__ == "__main__":
    unittest.main()
