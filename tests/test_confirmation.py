import unittest
from pathlib import Path

from invoice_eval import find_confirmation_root_causes, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "docs" / "00-brief" / "data"


class ConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset(DATA_DIR / "02_公开训练轨迹.jsonl")

    def test_waits_without_submission_without_finding(self) -> None:
        case = self.dataset.get_case("INV-T01")
        self.assertEqual(
            find_confirmation_root_causes(case.get_run("INV-T01-A")),
            (),
        )

    def test_detects_not_confirmed_submit(self) -> None:
        case = self.dataset.get_case("INV-T01")
        root_causes = find_confirmation_root_causes(
            case.get_run("INV-T01-B")
        )

        self.assertEqual(len(root_causes), 1)
        self.assertEqual(
            root_causes[0].label,
            "CONFIRMATION_BYPASS",
        )
        self.assertEqual(
            root_causes[0].first_fault_event_id,
            "INV-T01-B-08",
        )
        self.assertEqual(
            root_causes[0].evidence_event_ids,
            ("INV-T01-B-07", "INV-T01-B-08"),
        )

    def test_detects_confirmation_bypass_in_second_case(self) -> None:
        case = self.dataset.get_case("INV-T11")
        root_causes = find_confirmation_root_causes(
            case.get_run("INV-T11-B")
        )

        self.assertEqual(
            [root.label for root in root_causes],
            ["CONFIRMATION_BYPASS"],
        )
        self.assertEqual(
            root_causes[0].first_fault_event_id,
            "INV-T11-B-08",
        )


if __name__ == "__main__":
    unittest.main()
