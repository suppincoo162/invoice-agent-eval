import unittest
from pathlib import Path

from invoice_eval import (
    find_buyer_root_causes,
    find_callback_root_causes,
    find_product_root_causes,
    find_submit_argument_root_causes,
    load_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class ExtendedRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")

    def test_missing_buyer_is_correctly_requested(self) -> None:
        case = self.dataset.get_case("INV-T03")
        self.assertEqual(
            find_buyer_root_causes(case, case.get_run("INV-T03-A")),
            (),
        )

    def test_missing_buyer_fabrication(self) -> None:
        case = self.dataset.get_case("INV-T03")
        roots = find_buyer_root_causes(case, case.get_run("INV-T03-B"))

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "FIELD_FABRICATION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T03-B-05",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T03-B-05", "INV-T03-B-07"),
        )

    def test_buyer_disambiguation(self) -> None:
        case = self.dataset.get_case("INV-T04")
        roots = find_buyer_root_causes(case, case.get_run("INV-T04-A"))

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "ENTITY_RESOLUTION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T04-A-05",
        )
        self.assertEqual(
            find_buyer_root_causes(
                case, case.get_run("INV-T04-B")
            ),
            (),
        )

    def test_product_mismatch(self) -> None:
        case = self.dataset.get_case("INV-T12")
        roots = find_product_root_causes(
            case, case.get_run("INV-T12-A")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "PRODUCT_MATCH")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T12-A-05",
        )
        self.assertEqual(
            find_product_root_causes(
                case, case.get_run("INV-T12-B")
            ),
            (),
        )

    def test_failed_callback_reported_as_success(self) -> None:
        case = self.dataset.get_case("INV-T10")
        roots = find_callback_root_causes(case.get_run("INV-T10-B"))

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "CALLBACK_MISINTERPRETATION")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T10-B-09",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T10-B-09", "INV-T10-B-10"),
        )
        self.assertEqual(
            find_callback_root_causes(case.get_run("INV-T10-A")),
            (),
        )

    def test_submit_argument_drift(self) -> None:
        case = self.dataset.get_case("INV-T14")
        roots = find_submit_argument_root_causes(
            case.get_run("INV-T14-B")
        )

        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].label, "TOOL_ARGUMENT_ERROR")
        self.assertEqual(
            roots[0].first_fault_event_id,
            "INV-T14-B-08",
        )
        self.assertEqual(
            roots[0].evidence_event_ids,
            ("INV-T14-B-07", "INV-T14-B-08"),
        )
        self.assertEqual(
            find_submit_argument_root_causes(
                case.get_run("INV-T14-A")
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
