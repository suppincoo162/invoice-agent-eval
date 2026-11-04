import unittest
from pathlib import Path

from invoice_eval import (
    evaluate_case,
    find_batch_root_causes,
    find_red_invoice_root_causes,
    find_task_type_root_causes,
    load_dataset,
    load_workflow,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class InvoiceTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")
        cls.validation = load_dataset(DATA_DIR / "04_无标注验证轨迹.jsonl")
        cls.workflow = load_workflow(
            DATA_DIR / "01_竞赛版流程字典.json"
        )

    def test_red_invoice_misclassified_as_blue(self) -> None:
        case = self.training.get_case("INV-T06")
        roots = find_task_type_root_causes(
            case, case.get_run("INV-T06-A")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "INTENT_CLASSIFICATION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T06-A-04",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T06-A-04", "INV-T06-A-07"),
        )

    def test_correct_red_invoice_type_has_no_finding(self) -> None:
        case = self.training.get_case("INV-T06")
        self.assertEqual(
            find_task_type_root_causes(
                case, case.get_run("INV-T06-B")
            ),
            (),
        )

    def test_preview_task_type_drift_is_fault(self) -> None:
        case = self.training.get_case("INV-T06")
        run = case.get_run("INV-T06-B")
        confirmation = run.get_event("INV-T06-B-07")
        preview = confirmation.raw["observed_output"]["preview"]
        original_type = preview["invoice_task_type"]
        try:
            preview["invoice_task_type"] = "BLUE"
            roots = find_task_type_root_causes(case, run)
        finally:
            preview["invoice_task_type"] = original_type

        self.assertEqual(
            [root.label for root in roots],
            ["INTENT_CLASSIFICATION"],
        )
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T06-B-07",
        )

    def test_missing_original_is_correctly_requested(self) -> None:
        case = self.validation.get_case("INV-V03")
        self.assertEqual(
            find_red_invoice_root_causes(
                case, case.get_run("INV-V03-A")
            ),
            (),
        )

    def test_missing_original_without_request_is_fault(self) -> None:
        case = self.validation.get_case("INV-V03")
        roots = find_red_invoice_root_causes(
            case, case.get_run("INV-V03-B")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "FIELD_FABRICATION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-V03-B-05",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-V03-B-05", "INV-V03-B-07"),
        )

    def test_preview_original_invoice_drift_is_fault(self) -> None:
        case = self.training.get_case("INV-T06")
        run = case.get_run("INV-T06-B")
        confirmation = run.get_event("INV-T06-B-07")
        preview = confirmation.raw["observed_output"]["preview"]
        original_id = preview["original_invoice_id"]
        try:
            preview["original_invoice_id"] = None
            roots = find_red_invoice_root_causes(case, run)
        finally:
            preview["original_invoice_id"] = original_id

        self.assertEqual(
            [root.label for root in roots],
            ["FIELD_FABRICATION"],
        )
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T06-B-07",
        )

    def test_complete_batch_has_no_finding(self) -> None:
        case = self.training.get_case("INV-T07")
        self.assertEqual(
            find_batch_root_causes(case, case.get_run("INV-T07-A")),
            (),
        )

    def test_batch_omission_is_fault(self) -> None:
        case = self.training.get_case("INV-T07")
        roots = find_batch_root_causes(
            case, case.get_run("INV-T07-B")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "MULTI_ITEM_OMISSION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T07-B-05",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T07-B-05", "INV-T07-B-07"),
        )

    def test_validation_batch_partial_omission(self) -> None:
        case = self.validation.get_case("INV-V05")
        self.assertEqual(
            find_batch_root_causes(case, case.get_run("INV-V05-A")),
            (),
        )
        roots = find_batch_root_causes(
            case, case.get_run("INV-V05-B")
        )
        self.assertEqual(
            [root.label for root in roots],
            ["MULTI_ITEM_OMISSION"],
        )

    def test_t007_cases_end_to_end(self) -> None:
        expectations = {
            "INV-T06": ("candidate_better", False, True, 70, 100),
            "INV-T07": ("baseline_better", True, False, 100, 70),
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


if __name__ == "__main__":
    unittest.main()
